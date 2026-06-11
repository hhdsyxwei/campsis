# dm_backtest.py
import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


class BacktestResultManager:
    def __init__(self, connection):
        self.conn = connection

    def create_run(self, stock_code, start_date, end_date, initial_cash,
                   run_name=None, commission_rate=0.0003, risk_free_rate=0.03):
        run_id = uuid.uuid4().hex
        sql = """
        INSERT INTO backtest_run
        (run_id, run_name, stock_code, start_date, end_date, initial_cash,
         commission_rate, risk_free_rate, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'running')
        """
        with self.conn.cursor() as cursor:
            cursor.execute(sql, (
                run_id, run_name, stock_code, start_date, end_date,
                initial_cash, commission_rate, risk_free_rate
            ))
        self.conn.commit()
        logger.info(f"创建回测记录: run_id={run_id}, stock_code={stock_code}")
        return run_id

    def mark_run_success(self, run_id):
        self._update_run_status(run_id, "success", None)

    def mark_run_failed(self, run_id, error_message):
        self._update_run_status(run_id, "failed", error_message)

    def _update_run_status(self, run_id, status, error_message):
        sql = """
        UPDATE backtest_run
        SET status = %s, error_message = %s, finished_at = CURRENT_TIMESTAMP
        WHERE run_id = %s
        """
        with self.conn.cursor() as cursor:
            cursor.execute(sql, (status, error_message, run_id))
        self.conn.commit()

    def save_results(self, run_id, stock_code, results, analysis):
        try:
            with self.conn.cursor() as cursor:
                for result in results:
                    if result.get("error"):
                        continue

                    strategy_name = result.get("strategy")
                    analysis_item = self._find_analysis_item(analysis, strategy_name)
                    self._save_strategy_result(cursor, run_id, result, analysis_item)
                    self._save_transactions(cursor, run_id, strategy_name, stock_code, result.get("transactions", {}))
                    self._save_closed_trades(cursor, run_id, strategy_name, stock_code, result.get("trades", []))
            self.conn.commit()
            logger.info(f"回测结果保存完成: run_id={run_id}")
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"回测结果保存失败: run_id={run_id}, error={str(e)}", exc_info=True)
            return False

    def _save_strategy_result(self, cursor, run_id, result, analysis_item):
        metrics = (analysis_item or {}).get("metrics", result.get("metrics", {}))
        strategy_name = result.get("strategy")
        params = result.get("params", {})
        sql = """
        INSERT INTO backtest_strategy_result
        (run_id, strategy_name, strategy_params_json, final_value, total_return,
         annual_return, sharpe_ratio, max_drawdown, calmar_ratio, win_rate,
         profit_factor, trade_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            strategy_params_json = VALUES(strategy_params_json),
            final_value = VALUES(final_value),
            total_return = VALUES(total_return),
            annual_return = VALUES(annual_return),
            sharpe_ratio = VALUES(sharpe_ratio),
            max_drawdown = VALUES(max_drawdown),
            calmar_ratio = VALUES(calmar_ratio),
            win_rate = VALUES(win_rate),
            profit_factor = VALUES(profit_factor),
            trade_count = VALUES(trade_count)
        """
        cursor.execute(sql, (
            run_id,
            strategy_name,
            self._to_json(params),
            self._num(metrics.get("final_value")),
            self._num(metrics.get("total_return")),
            self._num(metrics.get("annual_return", metrics.get("total_return"))),
            self._num(metrics.get("sharpe_ratio")),
            self._num(metrics.get("max_drawdown")),
            self._num(metrics.get("calmar_ratio")),
            self._num(metrics.get("win_rate")),
            self._num(metrics.get("profit_factor")),
            int(metrics.get("trade_count") or 0)
        ))

    def _save_transactions(self, cursor, run_id, strategy_name, stock_code, transactions):
        if not transactions:
            return

        sql = """
        INSERT INTO backtest_order_transaction
        (run_id, strategy_name, stock_code, trade_date, side, quantity, price,
         commission, amount, raw_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        records = []
        for dt, tx_list in transactions.items():
            trade_date = self._date_str(dt)
            for tx in tx_list:
                if len(tx) < 3:
                    continue
                quantity = int(tx[0])
                price = self._num(tx[1])
                commission = self._num(tx[2])
                side = "buy" if quantity > 0 else "sell"
                amount = abs(quantity) * float(price or 0)
                records.append((
                    run_id, strategy_name, stock_code, trade_date, side,
                    abs(quantity), price, commission, amount, self._to_json(tx)
                ))

        if records:
            cursor.executemany(sql, records)

    def _save_closed_trades(self, cursor, run_id, strategy_name, stock_code, trades):
        if not trades:
            return

        sql = """
        INSERT INTO backtest_closed_trade
        (run_id, strategy_name, stock_code, close_date, gross_pnl, net_pnl, size, raw_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        records = []
        for trade in trades:
            records.append((
                run_id,
                strategy_name,
                stock_code,
                self._date_str(trade.get("date")),
                self._num(trade.get("gross")),
                self._num(trade.get("net")),
                int(trade.get("size") or 0),
                self._to_json(trade)
            ))

        cursor.executemany(sql, records)

    def _find_analysis_item(self, analysis, strategy_name):
        for item in analysis.get("strategies", []):
            if item.get("strategy") == strategy_name:
                return item
        return None

    def _to_json(self, value):
        return json.dumps(value, ensure_ascii=False, default=self._json_default)

    def _json_default(self, value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return str(value)

    def _date_str(self, value):
        if hasattr(value, "date"):
            value = value.date()
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _num(self, value):
        if value is None:
            return None
        return float(value)
