# parallel_runner.py
# Parallel backtest runner for multiple strategies

import backtrader as bt
import traceback

from CookingEngine.Backtest.data_adapter import BacktraderDataAdapter
from CookingEngine.Strategies.strategy_factory import StrategyFactory
from KitchenBase.logger_config import get_logger
from CookingEngine.Strategies.factors import FactorStrategy
from CookingEngine.Strategies import strategy_registry

logger = get_logger(__name__)


class ParallelBacktestRunner:
    def __init__(self, db_conn, max_workers=4):
        self.db_conn = db_conn
        self.max_workers = max_workers
        self.data_adapter = BacktraderDataAdapter(db_conn)
        self.strategy_factory = StrategyFactory(db_conn)
        logger.info(f"ParallelBacktestRunner initialized with {max_workers} workers")

    def run_single(self, config):
        try:
            strategy_name = config["strategy"]["name"]
            strategy_params = config["strategy"].get("params", {})
            stock_code = config["data"].get("stock_code", "000001.SZ")
            start_date = config["data"]["start_date"]
            end_date = config["data"]["end_date"]
            initial_cash = config.get("initial_cash", 1000000)

            logger.info(f"Running backtest for {strategy_name} on {stock_code}")

            strategy_class = strategy_registry.get(strategy_name)
            if not strategy_class:
                raise ValueError(f"Strategy '{strategy_name}' not found")

            data = self.data_adapter.get_stock_data(stock_code, start_date, end_date)

            if data is None:
                logger.error(f"No data found for {stock_code}")
                return {"strategy": strategy_name, "error": f"No data found for {stock_code}"}

            cerebro = bt.Cerebro()

            cerebro.addstrategy(
                strategy_class,
                data_provider=self.strategy_factory.data_provider,
                factor_calculator=self.strategy_factory.factor_calculator,
                **strategy_params
            )

            cerebro.adddata(data, name=stock_code)
            cerebro.broker.setcash(initial_cash)
            cerebro.broker.setcommission(commission=0.0003)

            cerebro.addanalyzer(bt.analyzers.SharpeRatio, riskfreerate=0.03)
            cerebro.addanalyzer(bt.analyzers.DrawDown)
            cerebro.addanalyzer(bt.analyzers.Returns)
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer)
            #cerebro.addanalyzer(bt.analyzers.Position)    # 持仓信息
            cerebro.addanalyzer(bt.analyzers.Transactions)  # 交易记录。只包含已成交的委托记录
            #cerebro.addanalyzer(bt.analyzers.AnnualReturn)        # 年化收益率分析
            #cerebro.addanalyzer(bt.analyzers.Calmar)        # Calmar Ratio分析

            results = cerebro.run()
            strategy_results = results[0]
            analyzers = strategy_results.analyzers

            sharpe = analyzers.sharperatio.get_analysis()
            dd = analyzers.drawdown.get_analysis()
            ret = analyzers.returns.get_analysis()
            ta = analyzers.tradeanalyzer.get_analysis()
            transactions = analyzers.transactions.get_analysis()

            metrics = {
                "final_value": cerebro.broker.getvalue(),
                "total_return": strategy_results.get_total_return(),
                "sharpe_ratio": sharpe.get("sharperatio", 0) or 0,
                "max_drawdown": dd.get("max", {}).get("drawdown", 0) / 100 if dd.get("max") else 0,
                "trade_count": len(strategy_results.trades)
            }

            logger.info(f"Backtest completed for {strategy_name}: {metrics}")

            return {
                "strategy": strategy_name,
                "params": strategy_params,
                "metrics": metrics,
                "trades": strategy_results.trades,
                "transactions": transactions
            }

        except Exception as e:
            logger.error(f"Error running backtest: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return {"strategy": config["strategy"]["name"], "error": str(e), "traceback": traceback.format_exc()}

    def run_batch(self, configs):
        results = []
        logger.info(f"Starting batch backtest with {len(configs)} strategies")

        for i, config in enumerate(configs):
            try:
                result = self.run_single(config)
                results.append(result)
                logger.info(f"Completed task {i+1}/{len(configs)}: {result.get('strategy', 'Unknown')}")
            except Exception as e:
                logger.error(f"Task {i+1} failed: {str(e)}")
                logger.error(f"Traceback:\n{traceback.format_exc()}")
                results.append({"error": str(e), "traceback": traceback.format_exc()})

        logger.info(f"Batch backtest completed. Total: {len(results)} strategies")
        return results

    def run_strategies(self, strategy_names, start_date, end_date, stock_code="000001.SZ"):
        configs = []
        for strategy_name in strategy_names:
            config = {
                "strategy": {"name": strategy_name, "params": {}},
                "data": {
                    "stock_code": stock_code,
                    "start_date": start_date,
                    "end_date": end_date
                },
                "initial_cash": 1000000
            }
            configs.append(config)
        return self.run_batch(configs)
