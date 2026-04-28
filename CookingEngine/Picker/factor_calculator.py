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
        趋势因子（25）：价在均线上 + 均线向上趋势
        趋势因子的构成：
        1. 价格是否在20日均线以上
        2. 价格是否在60日均线以上
        3. 价格是否在120日均线以上
        4. 均线是否多头排列
        5. 价格变化率
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
            logger.debug(f"获取到价格数据 {stock_code}: {len(price_data)} 条")
            logger.debug(f"价格数据类型: {type(price_data)}")
            if price_data.empty:
                logger.debug(f"价格数据为空 {stock_code}")
                return 0.0

            # 检查 close 列的数据类型
            logger.debug(f"close 列数据类型: {price_data['close'].dtype}")
            logger.debug(f"close 列前5行: {price_data['close'].head()}")

            # 转换为 float 类型
            price_data['close'] = price_data['close'].astype(float)
            logger.debug(f"转换后 close 列数据类型: {price_data['close'].dtype}")

            # 计算移动平均线
            price_data['ma20'] = price_data['close'].rolling(window=20).mean()
            price_data['ma60'] = price_data['close'].rolling(window=60).mean()
            price_data['ma120'] = price_data['close'].rolling(window=120).mean()

            # 检查均线计算结果
            logger.debug(f"ma20 类型: {price_data['ma20'].dtype}, 最后值: {price_data['ma20'].iloc[-1] if len(price_data) > 0 else 'N/A'}")
            logger.debug(f"ma60 类型: {price_data['ma60'].dtype}, 最后值: {price_data['ma60'].iloc[-1] if len(price_data) > 0 else 'N/A'}")
            logger.debug(f"ma120 类型: {price_data['ma120'].dtype}, 最后值: {price_data['ma120'].iloc[-1] if len(price_data) > 0 else 'N/A'}")

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
            logger.debug(f"x 类型: {type(x)}, 长度: {len(x)}")
            logger.debug(f"y 类型: {type(y)}, 长度: {len(y)}")
            logger.debug(f"y 前5值: {y[:5]}")

            slope = np.polyfit(x, y, 1)[0]
            logger.debug(f"slope: {slope}, 类型: {type(slope)}")

            first_close = price_data['close'].iloc[0]
            logger.debug(f"first_close: {first_close}, 类型: {type(first_close)}")

            if first_close == 0:
                logger.debug(f"first_close 为 0，返回 0.0")
                return 0.0

            slope_normalized = (slope / first_close) * 100
            logger.debug(f"slope_normalized: {slope_normalized}, 类型: {type(slope_normalized)}")

            # 综合计算分数
            score = 0.0
            if price_above_ma20:
                score += 20.0
            if price_above_ma60:
                score += 25.0
            if price_above_ma120:
                score += 30.0
            if ma_bullish:
                score += 15.0

            # 趋势斜率贡献
            slope_score = max(0.0, min(10.0, slope_normalized * 2.0))
            score += slope_score

            final_score = min(100, score)
            logger.debug(f"最终分数: {final_score}")
            return final_score

        except Exception as e:
            logger.error(f"计算趋势因子分数失败 {stock_code}: {str(e)}")
            logger.error(f"异常类型: {type(e)}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return 0.0

    def calculate_momentum_score(self, stock_code, start_date, end_date):
        """
        计算动量因子分数
        动量因子（25）：近 20 日涨幅靠前
        动量因子的构成：
        1. 近 20 日涨幅
        2. 近 60 日涨幅
        3. 近 120 日涨幅
        4. 近 240 日涨幅
        5. 与沪深300相比的相对强弱指标
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
            
            # 转换为 float 类型
            price_data['close'] = price_data['close'].astype(float)
            
            # 计算不同时间周期的收益率
            # 1个月收益率
            if len(price_data) >= 20:
                one_month_return = (float(price_data['close'].iloc[-1]) / float(price_data['close'].iloc[-20])) - 1
            else:
                one_month_return = 0.0
            
            # 3个月收益率
            if len(price_data) >= 60:
                three_month_return = (float(price_data['close'].iloc[-1]) / float(price_data['close'].iloc[-60])) - 1
            else:
                three_month_return = 0.0
            
            # 6个月收益率
            if len(price_data) >= 120:
                six_month_return = (float(price_data['close'].iloc[-1]) / float(price_data['close'].iloc[-120])) - 1
            else:
                six_month_return = 0.0
            
            # 12个月收益率
            if len(price_data) >= 240:
                twelve_month_return = (float(price_data['close'].iloc[-1]) / float(price_data['close'].iloc[-240])) - 1
            else:
                twelve_month_return = 0.0
            
            # 计算相对强弱
            # 假设获取沪深300指数作为基准
            benchmark_data = self.data_provider.get_index_data('000300.SH', start_date, end_date)
            if not benchmark_data.empty:
                benchmark_return = (float(benchmark_data['close'].iloc[-1]) / float(benchmark_data['close'].iloc[0])) - 1
                stock_return = (float(price_data['close'].iloc[-1]) / float(price_data['close'].iloc[0])) - 1
                relative_strength = stock_return - benchmark_return
            else:
                relative_strength = 0.0
            
            # 综合计算分数
            score = 0.0
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
        基本面质量因子（25）：量能健康、不暴雷
        基本面质量因子的构成：
        1. 净资产收益率 (ROE)
        2. 资产负债率
        3. 净利润增长率
        4. 营业收入增长率
        5. 毛利率

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
            
            # 安全转换函数：将值转换为 float，处理 None 的情况
            def safe_float(value, default):
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # 计算财务指标，将 Decimal 转换为 float 避免类型冲突
            # 1. 净资产收益率 (ROE)
            roe = safe_float(latest_financial.get('roe'), 0)
            
            # 2. 资产负债率
            debt_to_asset = safe_float(latest_financial.get('debt_to_asset'), 1)
            
            # 3. 净利润增长率
            if len(financial_data) >= 2:
                current_profit = safe_float(latest_financial.get('net_profit'), 0)
                previous_profit = safe_float(financial_data.iloc[-2].get('net_profit'), 1)
                profit_growth = (current_profit / previous_profit) - 1 if previous_profit != 0 else 0.0
            else:
                profit_growth = 0.0
            
            # 4. 营业收入增长率
            if len(financial_data) >= 2:
                current_revenue = safe_float(latest_financial.get('revenue'), 0)
                previous_revenue = safe_float(financial_data.iloc[-2].get('revenue'), 1)
                revenue_growth = (current_revenue / previous_revenue) - 1 if previous_revenue != 0 else 0.0
            else:
                revenue_growth = 0.0
            
            # 5. 毛利率
            gross_margin = safe_float(latest_financial.get('gross_margin'), 0)
            
            # 综合计算分数
            score = 0.0
            
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
        时机因子（25）：RSI 不过热、位置不高
        时机因子的计算依赖以下技术指标：
        1. RSI (相对强弱指数)-14日RSI，通过价格变化的涨跌幅度计算
        2. MACD-12日EMA与26日EMA的差值，再与9日信号线的差值-衡量价格动量和趋势变化
        3. 布林带-20日均线上下各2倍标准差的通道，计算价格在通道中的位置-衡量价格的相对位置和波动性
        4. 成交量变化-5日平均成交量变化率-衡量成交量的变化趋势，反映市场参与度

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