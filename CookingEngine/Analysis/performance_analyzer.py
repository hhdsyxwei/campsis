# performance_analyzer.py
# Performance analysis for Backtrader strategies

import pandas as pd
import numpy as np
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


class PerformanceAnalyzer:
    def __init__(self, risk_free_rate=0.03):
        self.risk_free_rate = risk_free_rate
        logger.info(f"PerformanceAnalyzer initialized with risk_free_rate: {risk_free_rate}")

    def analyze(self, backtest_results):
        try:
            if "error" in backtest_results:
                return {
                    "strategy": backtest_results.get("strategy", "Unknown"),
                    "error": backtest_results["error"]
                }

            metrics = backtest_results.get("metrics", {})
            trades = backtest_results.get("trades", [])

            annual_return = self._calculate_annual_return(metrics)
            sharpe_ratio = metrics.get("sharpe_ratio", 0)
            max_drawdown = metrics.get("max_drawdown", 0)
            win_rate = self._calculate_win_rate(trades)
            profit_factor = self._calculate_profit_factor(trades)
            calmar_ratio = self._calculate_calmar_ratio(annual_return, max_drawdown)

            analysis = {
                "strategy": backtest_results.get("strategy", "Unknown"),
                "params": backtest_results.get("params", {}),
                "metrics": {
                    "final_value": metrics.get("final_value", 0),
                    "total_return": metrics.get("total_return", 0),
                    "annual_return": annual_return,
                    "sharpe_ratio": sharpe_ratio,
                    "max_drawdown": max_drawdown,
                    "calmar_ratio": calmar_ratio,
                    "win_rate": win_rate,
                    "profit_factor": profit_factor,
                    "trade_count": metrics.get("trade_count", 0)
                }
            }

            logger.info(f"Analyzed performance for {analysis['strategy']}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing performance: {str(e)}")
            return {"error": str(e)}

    def _calculate_annual_return(self, metrics):
        total_return = metrics.get("total_return", 0)
        return (1 + total_return) - 1

    def _calculate_win_rate(self, trades):
        if not trades:
            return 0
        winning_trades = [t for t in trades if t["net"] > 0]
        return len(winning_trades) / len(trades)

    def _calculate_profit_factor(self, trades):
        if not trades:
            return 0
        gross_profit = sum(t["net"] for t in trades if t["net"] > 0)
        gross_loss = abs(sum(t["net"] for t in trades if t["net"] < 0))
        return gross_profit / gross_loss if gross_loss > 0 else 0

    def _calculate_calmar_ratio(self, annual_return, max_drawdown):
        return annual_return / max_drawdown if max_drawdown > 0 else 0

    def compare(self, results_list):
        analyses = []
        for result in results_list:
            analysis = self.analyze(result)
            if "error" not in analysis:
                analyses.append(analysis)

        if not analyses:
            return {"error": "No valid results to compare"}

        comparison_data = []
        for analysis in analyses:
            metrics = analysis["metrics"]
            comparison_data.append({
                "strategy": analysis["strategy"],
                "annual_return": metrics["annual_return"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "calmar_ratio": metrics["calmar_ratio"],
                "win_rate": metrics["win_rate"],
                "profit_factor": metrics["profit_factor"],
                "trade_count": metrics["trade_count"]
            })

        df = pd.DataFrame(comparison_data)

        if not df.empty:
            df["rank_return"] = df["annual_return"].rank(ascending=False)
            df["rank_sharpe"] = df["sharpe_ratio"].rank(ascending=False)
            df["rank_calmar"] = df["calmar_ratio"].rank(ascending=False)
            df["overall_rank"] = (df["rank_return"] + df["rank_sharpe"] + df["rank_calmar"]) / 3

        logger.info(f"Compared {len(analyses)} strategies")

        best_return = df.loc[df["annual_return"].idxmax()]["strategy"] if not df.empty else None
        best_sharpe = df.loc[df["sharpe_ratio"].idxmax()]["strategy"] if not df.empty else None
        best_calmar = df.loc[df["calmar_ratio"].idxmax()]["strategy"] if not df.empty else None

        return {
            "strategies": analyses,
            "comparison_matrix": df.to_dict("records") if not df.empty else [],
            "best_by_return": best_return,
            "best_by_sharpe": best_sharpe,
            "best_by_calmar": best_calmar
        }
