# main.py
import pymysql
import baostock as bs
import time
from Ingredient.data_manager import create_database_and_tables
from Ingredient.kline_5min_downloader import KLine5MinDownloader
from KitchenBase.download_utils import logger
from Ingredient.stock_basic_downloader import refresh_stock_code_list,download_stock_details
from Ingredient.daily_data_downloader import download_all_stocks_daily_data
from Ingredient.trade_date_map_downloader import download_trade_date_map

def main():


    """主函数，协调整个数据下载流程。"""
    # 1. 登录 Baostock 服务
    lg = bs.login()
    if lg.error_code != '0':
        logger.error(f"Baostock 登录失败: {lg.error_msg}")
        return
    logger.info("Baostock 登录成功。")

    # 2. 建立与本地数据库的连接
    conn = create_database_and_tables()

    try:
        download_trade_date_map(conn, 2023, 2027)  # 下载交易日映射表，覆盖2023-2027年
        # 3. 第一步：同步并更新股票的基础信息表 (stock_basic)
        refresh_stock_code_list(conn)
        download_stock_details(conn)  # 下载股票详细信息（行业、上市日期等），支持断点续传

        # 4. 第二步：下载所有活跃股票的日线数据
        # start_date 参数是可选的。如果不提供，download_all_stocks_daily_data 会尝试从 stock_basic 表中获取上市日期。
        #download_all_stocks_daily_data(conn, start_date="2023-01-01", end_date="2026-03-17") 

        # 5. 第三步：下载5分钟K线数据（示例）
        # 这里我们以 "sh.600000" 为例，实际使用中可以循环所有股票代码进行下载
        #bs_client = bs  # 已登录的 Baostock 客户端
        kline_downloader = KLine5MinDownloader()
        kline_downloader.download(conn, "sh.600000", "2023-01-01", "2023-12-31", bs)

    except Exception as e:
        # 捕获主流程中的任何异常，并记录详细错误信息
        logger.error(f"主程序执行出错: {e}", exc_info=True)
    finally:
        # 程序结束前，确保关闭数据库连接和 Baostock 登录会话
        conn.close()
        bs.logout()
        logger.info("已断开数据库连接并退出 Baostock。")

# 程序入口点，当直接运行此脚本时，会执行 main() 函数
if __name__ == '__main__':
    main()