# factor_calculator.py
# 因子计算模块

import pandas as pd
import numpy as np
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

class FactorCalculator:
    """因子计算器，用于计算各种选股因子"""
    
    def __init__(self, data_provider):
        """
        初始化因子计算器
        
        Args:
            data_provider: 数据提供者实例，用于获取股票数据
        """
        self.data_provider = data_provider
    
    def calculate_trend_score(self, stock_code, start_date, end_date):
        """
        计算趋势因子分数
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            float: 趋势因子分数 (0-100)
        """
        try:
            # 获取股票价格数据
            price_data = self.data_provider.get_price_data(stock_code, start_date, end_date)
            if price_data.empty:
                return 0.0
            
            # 计算移动平均线
            price_data['ma20'] = price_data['close'].rolling(window=20).mean()
            price_data['ma60'] = price_data['close'].rolling(window=60).mean()
            price_data['ma120'] = price_data['close'].rolling(window=120).mean()
            
            # 计算趋势强度
            # 1. 价格是否在均线上方
            price_above_ma20 = price_data['close'].iloc[-1] > price_data['ma20'].iloc[-1]
            price_above_ma60 = price_data['close'].iloc[-1] > price_data['ma60'].iloc[-1]
            price_above_ma120 = price_data['close'].iloc[-1] > price_data['ma120'].iloc[-1]
            
            # 2. 均线是否呈多头排列
            ma_bullish = price_data['ma20'].iloc[-1] > price_data['ma60'].iloc[-1] > price_data['ma120'].iloc[-1]
            
            # 3. 计算价格趋势斜率
            x = np.arange(len(price_data))
            y = price_data['close'].values
            slope = np.polyfit(x, y, 1)[0]
            slope_normalized = (slope / price_data['close'].iloc[0]) * 100
            
            # 综合计算分数
            score = 0
            if price_above_ma20:
                score += 20
            if price_above_ma60:
                score += 25
            if price_above_ma120:
                score += 30
            if ma_bullish:
                score += 15
            
            # 趋势斜率贡献
            slope_score = max(0, min(10, slope_normalized * 2))
            score += slope_score
            
            return min(100, score)
            
        except Exception as e:
            logger.error(f"计算趋势因子分数失败 {stock_code}: {str(e)}")
            return 0.0
    
    def calculate_momentum_score(self, stock_code, start_date, end_date):
        """
        计算动量因子分数
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            float: 动量因子分数 (0-100)
        """
        try:
            # 获取股票价格数据
            price_data = self.data_provider.get_price_data(stock_code, start_date, end_date)
            if price_data.empty:
                return 0.0
            
            # 计算不同时间周期的收益率
            # 1个月收益率
            if len(price_data) >= 20:
                one_month_return = (price_data['close'].iloc[-1] / price_data['close'].iloc[-20]) - 1
            else:
                one_month_return = 0
            
            # 3个月收益率
            if len(price_data) >= 60:
                three_month_return = (price_data['close'].iloc[-1] / price_data['close'].iloc[-60]) - 1
            else:
                three_month_return = 0
            
            # 6个月收益率
            if len(price_data) >= 120:
                six_month_return = (price_data['close'].iloc[-1] / price_data['close'].iloc[-120]) - 1
            else:
                six_month_return = 0
            
            # 12个月收益率
            if len(price_data) >= 240:
                twelve_month_return = (price_data['close'].iloc[-1] / price_data['close'].iloc[-240]) - 1
            else:
                twelve_month_return = 0
            
            # 计算相对强弱
            # 假设获取沪深300指数作为基准
            benchmark_data = self.data_provider.get_index_data('000300.SH', start_date, end_date)
            if not benchmark_data.empty:
                benchmark_return = (benchmark_data['close'].iloc[-1] / benchmark_data['close'].iloc[0]) - 1
                stock_return = (price_data['close'].iloc[-1] / price_data['close'].iloc[0]) - 1
                relative_strength = stock_return - benchmark_return
            else:
                relative_strength = 0
            
            # 综合计算分数
            score = 0
            score += one_month_return * 100 * 0.2
            score += three_month_return * 100 * 0.3
            score += six_month_return * 100 * 0.3
            score += twelve_month_return * 100 * 0.2
            
            # 相对强弱贡献
            score += relative_strength * 100 * 0.2
            
            # 归一化到0-100
            score = max(0, min(100, score))
            
            return score
            
        except Exception as e:
            logger.error(f"计算动量因子分数失败 {stock_code}: {str(e)}")
            return 0.0
    
    def calculate_quality_score(self, stock_code, start_date, end_date):
        """
        计算质量因子分数
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            float: 质量因子分数 (0-100)
        """
        try:
            # 获取财务数据
            financial_data = self.data_provider.get_financial_data(stock_code, start_date, end_date)
            if financial_data.empty:
                return 0.0
            
            # 获取最新财务数据
            latest_financial = financial_data.iloc[-1]
            
            # 计算财务指标
            # 1. 净资产收益率 (ROE)
            roe = latest_financial.get('roe', 0)
            
            # 2. 资产负债率
            debt_to_asset = latest_financial.get('debt_to_asset', 1)
            
            # 3. 净利润增长率
            if len(financial_data) >= 2:
                profit_growth = (latest_financial.get('net_profit', 0) / financial_data.iloc[-2].get('net_profit', 1)) - 1
            else:
                profit_growth = 0
            
            # 4. 营业收入增长率
            if len(financial_data) >= 2:
                revenue_growth = (latest_financial.get('revenue', 0) / financial_data.iloc[-2].get('revenue', 1)) - 1
            else:
                revenue_growth = 0
            
            # 5. 毛利率
            gross_margin = latest_financial.get('gross_margin', 0)
            
            # 综合计算分数
            score = 0
            
            # ROE贡献 (0-30分)
            roe_score = min(30, roe * 2)
            score += roe_score
            
            # 资产负债率贡献 (0-20分) - 越低越好
            debt_score = max(0, 20 - debt_to_asset * 20)
            score += debt_score
            
            # 净利润增长率贡献 (0-20分)
            profit_growth_score = min(20, profit_growth * 100 * 0.2)
            score += profit_growth_score
            
            # 营业收入增长率贡献 (0-15分)
            revenue_growth_score = min(15, revenue_growth * 100 * 0.15)
            score += revenue_growth_score
            
            # 毛利率贡献 (0-15分)
            gross_margin_score = min(15, gross_margin * 1.5)
            score += gross_margin_score
            
            # 归一化到0-100
            score = max(0, min(100, score))
            
            return score
            
        except Exception as e:
            logger.error(f"计算质量因子分数失败 {stock_code}: {str(e)}")
            return 0.0
    
    def calculate_timing_score(self, stock_code, start_date, end_date):
        """
        计算时机因子分数
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            float: 时机因子分数 (0-100)
        """
        try:
            # 获取股票价格数据
            price_data = self.data_provider.get_price_data(stock_code, start_date, end_date)
            if price_data.empty:
                return 0.0
            
            # 计算技术指标
            # 1. RSI (相对强弱指数)
            delta = price_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # 2. MACD
            exp1 = price_data['close'].ewm(span=12, adjust=False).mean()
            exp2 = price_data['close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            macd_hist = macd - signal
            
            # 3. 布林带
            ma20 = price_data['close'].rolling(window=20).mean()
            std20 = price_data['close'].rolling(window=20).std()
            upper_band = ma20 + (std20 * 2)
            lower_band = ma20 - (std20 * 2)
            bollinger_position = (price_data['close'] - lower_band) / (upper_band - lower_band)
            
            # 4. 成交量变化
            volume_change = price_data['volume'].pct_change().rolling(window=5).mean()
            
            # 综合计算分数
            score = 0
            
            # RSI贡献 (0-30分) - 中性区域最好
            latest_rsi = rsi.iloc[-1]
            if 30 <= latest_rsi <= 70:
                score += 30 - abs(latest_rsi - 50) / 2
            
            # MACD贡献 (0-25分)
            latest_macd_hist = macd_hist.iloc[-1]
            if latest_macd_hist > 0:
                score += min(25, latest_macd_hist * 1000)
            
            # 布林带贡献 (0-25分) - 中间位置最好
            latest_bollinger = bollinger_position.iloc[-1]
            if 0.3 <= latest_bollinger <= 0.7:
                score += 25 - abs(latest_bollinger - 0.5) * 50
            
            # 成交量贡献 (0-20分)
            latest_volume_change = volume_change.iloc[-1]
            if latest_volume_change > 0:
                score += min(20, latest_volume_change * 100)
            
            # 归一化到0-100
            score = max(0, min(100, score))
            
            return score
            
        except Exception as e:
            logger.error(f"计算时机因子分数失败 {stock_code}: {str(e)}")
            return 0.0