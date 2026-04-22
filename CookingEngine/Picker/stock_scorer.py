# stock_scorer.py
# 股票打分模块

import pandas as pd
from KitchenBase.logger_config import get_logger
from .factor_calculator import FactorCalculator
from CookingEngine.Picker.data_provider import HarvestDataProvider

logger = get_logger(__name__)

class StockScorer:
    """股票打分器，用于计算股票的综合评分"""
    
    def __init__(self, data_provider):
        """
        初始化股票打分器
        
        Args:
            data_provider: 数据提供者实例，用于获取股票数据
        """
        self.data_provider = data_provider
        self.factor_calculator = FactorCalculator(data_provider)
    
    def score_stock(self, stock_code, start_date, end_date, weights=None):
        """
        为指定股票打分
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            weights: 各因子权重字典，默认权重为趋势0.3，动量0.25，质量0.25，时机0.2
            
        Returns:
            dict: 包含各因子分数和综合分数的字典
        """
        try:
            # 默认权重
            if weights is None:
                weights = {
                    'trend': 0.3,
                    'momentum': 0.25,
                    'quality': 0.25,
                    'timing': 0.2
                }
            
            # 计算各因子分数
            trend_score = self.factor_calculator.calculate_trend_score(stock_code, start_date, end_date)
            momentum_score = self.factor_calculator.calculate_momentum_score(stock_code, start_date, end_date)
            quality_score = self.factor_calculator.calculate_quality_score(stock_code, start_date, end_date)
            timing_score = self.factor_calculator.calculate_timing_score(stock_code, start_date, end_date)
            
            # 计算综合分数
            total_score = (
                trend_score * weights['trend'] +
                momentum_score * weights['momentum'] +
                quality_score * weights['quality'] +
                timing_score * weights['timing']
            )
            
            # 构建结果字典
            result = {
                'stock_code': stock_code,
                'total_score': total_score,
                'trend_score': trend_score,
                'momentum_score': momentum_score,
                'quality_score': quality_score,
                'timing_score': timing_score,
                'weights': weights
            }
            
            logger.info(f"股票 {stock_code} 打分完成: 综合分数={total_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"为股票 {stock_code} 打分失败: {str(e)}")
            # 返回默认分数
            return {
                'stock_code': stock_code,
                'total_score': 0.0,
                'trend_score': 0.0,
                'momentum_score': 0.0,
                'quality_score': 0.0,
                'timing_score': 0.0,
                'weights': weights or {}
            }
    
    def score_stocks(self, stock_codes, start_date, end_date, weights=None):
        """
        为多个股票打分
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            weights: 各因子权重字典
            
        Returns:
            pd.DataFrame: 包含各股票分数的DataFrame
        """
        try:
            results = []
            
            for stock_code in stock_codes:
                score_result = self.score_stock(stock_code, start_date, end_date, weights)
                results.append(score_result)
            
            # 转换为DataFrame
            df = pd.DataFrame(results)
            
            # 按综合分数排序
            df = df.sort_values('total_score', ascending=False).reset_index(drop=True)
            
            logger.info(f"完成 {len(stock_codes)} 只股票的打分")
            return df
            
        except Exception as e:
            logger.error(f"为多只股票打分失败: {str(e)}")
            return pd.DataFrame()
    
    def get_top_stocks(self, stock_codes, start_date, end_date, top_n=10, weights=None):
        """
        获取打分最高的前N只股票
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            top_n: 返回前N只股票
            weights: 各因子权重字典
            
        Returns:
            pd.DataFrame: 前N只股票的分数DataFrame
        """
        try:
            scores_df = self.score_stocks(stock_codes, start_date, end_date, weights)
            if scores_df.empty:
                return scores_df
            
            top_stocks = scores_df.head(top_n)
            logger.info(f"获取前 {top_n} 只打分最高的股票")
            return top_stocks
            
        except Exception as e:
            logger.error(f"获取前N只股票失败: {str(e)}")
            return pd.DataFrame()
    
    def save_scores(self, scores_df, file_path):
        """
        保存打分结果到文件
        
        Args:
            scores_df: 打分结果DataFrame
            file_path: 保存路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            scores_df.to_csv(file_path, index=False, encoding='utf-8')
            logger.info(f"打分结果已保存到 {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存打分结果失败: {str(e)}")
            return False

#给股票打分
def score_single_stock(conn, stock_code):
    """
    为单股票打分
    
    Args:
        stock_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        weights: 各因子权重字典
        
    Returns:
        dict: 包含各因子分数和综合分数的字典
    """
    data_provider = HarvestDataProvider(conn)
    stockSccorer = StockScorer(data_provider)
    summary = stockSccorer.score_stock(stock_code, "2025-10-01", "2026-04-15")
    logger.info(summary)