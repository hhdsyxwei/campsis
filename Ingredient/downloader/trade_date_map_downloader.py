# trade_date_map_downloader.py
from Ingredient.downloader.core.download_parameters import DownloadParameters
from KitchenBase.download_enums import DlTaskType
from Ingredient.downloader.core.abstract_downloader import SimpleDownloader
from KitchenBase.logger_config import get_logger
import pandas as pd
from datetime import datetime
from typing import Optional
from Ingredient.DataNest import TradeDateMapManager
from KitchenBase.baostock_wrapper import query_trade_dates, login

logger = get_logger(__name__)

class TradeDateMapDownloader(SimpleDownloader):
    """
    交易日数据下载器，基于 SimpleDownloader 实现
    """
    
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识
        """
        return DlTaskType.TRADE_DATE
    
    def validate_parameters(self, params: DownloadParameters, **kwargs) -> bool:
        """
        验证参数有效性
        """
        start_year = params.start_year
        end_year = params.end_year
        if not isinstance(start_year, int) or not isinstance(end_year, int):
            logger.error("年份必须为整数类型")
            return False
        if start_year <= 0 or end_year <= 0:
            logger.error("年份必须为正整数")
            return False
        if start_year >= end_year:
            logger.error(f"年份范围异常：start_year({start_year}) >= end_year({end_year})")
            return False
        return True
    
    def download_raw_data(self, params: DownloadParameters, **kwargs) -> Optional[pd.DataFrame]:
        """
        下载原始数据
        """
        start_year = params.start_year
        end_year = params.end_year
        start_date = f"{start_year}-01-01"
        # 如果最后一年是今年，则 end_date 设为今天
        current_year = datetime.now().year
        if end_year - 1 == current_year:
            end_date = datetime.now().strftime("%Y-%m-%d")
        else:
            end_date = f"{end_year - 1}-12-31"
        
        logger.info(f"交易日数据按年下载范围：{start_year} ~ {end_year-1} 年（{start_date} ~ {end_date}）")
        
        # 避免重复登录（若已登录则复用）
        try:
            # 先尝试获取登录状态（Baostock无直接获取状态接口，用查询兜底）
            test_rs = query_trade_dates(start_date=start_date, end_date=start_date)
            if test_rs.error_code == '0':
                logger.debug("Baostock已登录，复用现有连接")
            else:
                lg = login()
                if lg.error_code != '0':
                    logger.error(f"Baostock登录失败：{lg.error_msg}")
                    return None
        except:
            # 首次登录
            lg = login()
            if lg.error_code != '0':
                logger.error(f"Baostock登录失败：{lg.error_msg}")
                return None
        
        try:
            # 调用接口获取原始数据
            rs = query_trade_dates(start_date=start_date, end_date=end_date)
            if rs.error_code != '0':
                logger.error(f"下载交易日数据失败：{rs.error_msg}")
                return None
            
            # 将返回结果转为DataFrame（适配接口格式变化）
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning(f"{start_date}~{end_date}范围内无交易日数据")
                return None
            
            # 构建DataFrame，字段与Baostock返回一致
            df = pd.DataFrame(data_list, columns=rs.fields)
            logger.info(f"成功下载{len(df)}条原始交易日数据")
            return df
        except Exception as e:
            logger.error(f"下载原始交易日数据异常：{e}", exc_info=True)
            return None
    
    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗数据
        """
        if raw_data is None or raw_data.empty:
            logger.warning("原始数据为空")
            return pd.DataFrame()
        
        try:
            # 复制数据避免修改原数据
            df = raw_data.copy()
            
            # 1. 字段重命名（兼容Baostock字段名可能的变更）
            # 先检查字段是否存在，避免KeyError
            rename_map = {}
            if 'calendar_date' in df.columns:
                rename_map['calendar_date'] = 'calendar_date'
            if 'is_trading_day' in df.columns:
                rename_map['is_trading_day'] = 'is_trading_day'
            df.rename(columns=rename_map, inplace=True)
            
            # 2. 格式转换：calendar_date转为date类型，is_trading_day转为int
            # 处理空值/异常值
            df['calendar_date'] = pd.to_datetime(df['calendar_date'], errors='coerce').dt.date
            df['is_trading_day'] = pd.to_numeric(df['is_trading_day'], errors='coerce').fillna(0).astype(int)
            
            # 3. 空值处理：删除calendar_date为空的行
            df = df.dropna(subset=['calendar_date'])
            
            # 4. 数据校验：is_trading_day仅保留0/1
            df = df[df['is_trading_day'].isin([0, 1])]
            
            # 去重（按calendar_date）
            df = df.drop_duplicates(subset=['calendar_date'], keep='last')
            
            logger.info(f"数据清洗完成，有效数据{len(df)}条（去重后）")
            return df
        except Exception as e:
            logger.error(f"清洗交易日数据异常：{e}", exc_info=True)
            return pd.DataFrame()
    
    def save_data(self, data: pd.DataFrame, params: DownloadParameters, **kwargs) -> bool:
        """
        保存数据到数据库
        """
        if data is None or data.empty:
            logger.warning("数据为空，无需保存")
            return False
        
        try:
            trade_date_manager = TradeDateMapManager(self.db_conn)
            save_result = trade_date_manager.save_trade_date_map(data)
            if save_result:
                logger.info("交易日数据成功保存到数据库")
                return True
            else:
                logger.error("交易日数据保存到数据库失败")
                return False
        except Exception as e:
            logger.error(f"初始化TradeDateMapManager或保存数据异常：{e}", exc_info=True)
            return False

# 保留原有的对外接口函数，以保持兼容性
def download_trade_date_map(
    conn, 
    params: DownloadParameters
) -> bool:
    """
    对外暴露的核心函数：按年下载交易日数据并保存到数据库
    规则：包含 start_year 全年，不包含 end_year
    :param conn: 数据库连接对象
    :param params: 下载参数
    :return: 成功返回True，失败返回False
    """

    downloader = TradeDateMapDownloader(conn)
    return downloader.download(params)
