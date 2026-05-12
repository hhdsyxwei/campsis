# dm_stock_filter.py
from typing import Optional
import pandas as pd
from datetime import datetime, timedelta
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

class StockFilterManager:
    def __init__(self, db_conn):
        self.db_conn = db_conn

    def _get_20day_avg_close(self, stock_code: str) -> Optional[float]:
        """
        获取单只股票最近20个交易日的平均收盘价
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Optional[float]: 平均收盘价，如果没有足够数据返回None
        """
        query = """
            SELECT close 
            FROM stock_daily 
            WHERE std_stock_code = %s 
            ORDER BY trade_date DESC 
            LIMIT 20
        """
        try:
            df = pd.read_sql(query, self.db_conn, params=[stock_code])
            if len(df) == 0:
                return None
            
            # 过滤无效数据（NaN或0）
            valid_closes = df['close'].dropna()
            valid_closes = valid_closes[valid_closes > 0]
            
            if len(valid_closes) == 0:
                return None
            
            return valid_closes.mean()
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 20日平均收盘价失败: {str(e)}")
            return None

    def get_filtered_stock_list(self, min_market_cap=50, min_list_days=60):
        """
        获取经过风险过滤的股票列表
        
        Args:
            min_market_cap: 最小流通市值（亿元），默认50亿
            min_list_days: 最小上市天数，默认60天
            
        Returns:
            pd.DataFrame: 包含 stock_code, stock_name, market_cap 的DataFrame
        """
        func_name = "get_filtered_stock_list"
        logger.info(f"[{__name__}.{func_name}] 开始获取过滤后的股票列表")
        
        # 获取股票基础信息和流通股本
        query = """
            SELECT 
                sb.std_stock_code AS stock_code,
                sb.stock_name,
                sb.list_date,
                sb.market,
                cp.liqa_share AS circulating_shares
            FROM stock_basic sb
            LEFT JOIN (
                SELECT std_stock_code, liqa_share 
                FROM company_profit 
                WHERE stat_date = (SELECT MAX(stat_date) FROM company_profit)
            ) cp ON sb.std_stock_code = cp.std_stock_code
            WHERE sb.is_active = 1
              AND sb.market IN ('主板(深A)', '主板(沪A)', '科创板', '创业板')
        """

        try:
            stock_df = pd.read_sql(query, self.db_conn)

            # 1. 过滤ST/*ST股票（名称包含ST）
            stock_df = stock_df[~stock_df['stock_name'].str.contains('ST|\\*ST', na=False)]
            logger.debug(f"[{__name__}.{func_name}] ST股票过滤后剩余: {len(stock_df)} 只")

            # 2. 获取最近20日平均收盘价并计算流通市值
            logger.info(f"[{__name__}.{func_name}] 正在计算 {len(stock_df)} 只股票的20日平均收盘价...")
            
            avg_closes = []
            for _, row in stock_df.iterrows():
                avg_close = self._get_20day_avg_close(row['stock_code'])
                avg_closes.append(avg_close)

            stock_df['avg_close_20d'] = avg_closes

            # 计算流通市值（亿元）= 20日平均收盘价 × 流通股本（股）/ 100000000
            stock_df['market_cap'] = stock_df['avg_close_20d'] * stock_df['circulating_shares'] / 100000000

            # 过滤无效数据
            stock_df = stock_df.dropna(subset=['market_cap', 'avg_close_20d', 'circulating_shares'])
            stock_df = stock_df[stock_df['market_cap'] >= min_market_cap]
            logger.debug(f"[{__name__}.{func_name}] 流通市值过滤后剩余: {len(stock_df)} 只")

            # 3. 过滤上市不满指定天数的次新股
            stock_df['list_date'] = pd.to_datetime(stock_df['list_date'], errors='coerce')
            stock_df = stock_df[stock_df['list_date'] <= (datetime.today() - timedelta(days=min_list_days))]
            logger.debug(f"[{__name__}.{func_name}] 次新股过滤后剩余: {len(stock_df)} 只")
            
            # 重置索引
            stock_df = stock_df.reset_index(drop=True)
            
            logger.info(f"[{__name__}.{func_name}] 基础风险过滤完成，剩余可筛选股票数量：{len(stock_df)} 只")
            return stock_df[['stock_code', 'stock_name', 'market_cap']]
            
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 从数据库获取股票列表失败：{str(e)}", exc_info=True)
            return pd.DataFrame(columns=['stock_code', 'stock_name', 'market_cap'])
