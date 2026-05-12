# main.py
# ==============================================
# 1. 必须放在所有其他导入 【最前面】
# ==============================================
from KitchenBase.package_manager import PackageManager
from KitchenBase.logger_config import setup_logging,get_logger
setup_logging()
PackageManager.install_missing_requirements()

import os
import sys
import json

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import KitchenBase.baostock_wrapper as bs
from KitchenBase.baostock_wrapper import BaostockErrorCode
from Ingredient.DataNest import create_database_and_tables
from Ingredient.downloader import download_trade_date_map
from KitchenBase.stock_enums import KLinePeriod, MarketType
from CookingEngine.Picker.stock_scorer import score_single_stock
from CookingEngine.Analysis.performance_analyzer import PerformanceAnalyzer
from CookingEngine.Backtest.parallel_runner import ParallelBacktestRunner
from tools.count_code import count_project_code
from Ingredient.downloader.core import DownloadParameters
from Ingredient.downloader import start_new_daily_download
from Ingredient.downloader import start_new_balance_download
from Ingredient.downloader import start_new_profit_download
from Ingredient.downloader import start_new_cash_flow_download
from Ingredient.downloader import start_new_adj_factor_download
from Ingredient.downloader import start_new_xrxd_download
from Ingredient.downloader import start_new_kline_download
from Ingredient.downloader import download_csi300_components
from Ingredient.downloader import download_stock_basic
from CookingEngine.next_day_bullish_strategy import main_filter


os.environ["CAMPSIS_ENV"] = "dev"   # 开发环境
# os.environ["CAMPSIS_ENV"] = "prod" # 生产环境

logger = get_logger(__name__)


logger.debug("这是调试信息（灰色）")
logger.info("这是普通信息（蓝色）")
logger.warning("这是警告（黄色）")
logger.error("这是错误（红色）")
logger.info("初始化成功！【会加粗】")


def get_csi300_stock_codes() -> list:
    """
    获取沪深300成分股股票代码列表（2026年最新调整）
    
    数据来源：中证指数公司官网（截至2025年12月15日调整）
    沪深300指数由沪深两市规模最大、流动性最好的300只股票组成
    
    十大权重股（2026年数据）：
    1. 300750 宁德时代 (~4.38%)
    2. 600519 贵州茅台 (~3.63%)
    3. 300308 中际旭创 (~2.73%)
    4. 601318 中国平安 (~2.56%)
    5. 601899 紫金矿业 (~2.09%)
    6. 600036 招商银行 (~1.97%)
    7. 300502 新易盛 (~1.90%)
    8. 000333 美的集团 (~1.48%)
    9. 600900 长江电力 (~1.33%)
    10. 601166 兴业银行 (~1.28%)
    """
    # 2025年12月15日调样后最新成分股清单（已去重）
    csi300_stocks = [
        # ==================== 十大权重股 ====================
        "300750.SZ",  # 宁德时代 - 电力设备，权重~4.38%
        "600519.SH",  # 贵州茅台 - 食品饮料，权重~3.63%
        "300308.SZ",  # 中际旭创 - 光模块，权重~2.73%
        "601318.SH",  # 中国平安 - 保险，权重~2.56%
        "601899.SH",  # 紫金矿业 - 有色金属，权重~2.09%
        "600036.SH",  # 招商银行 - 银行，权重~1.97%
        "300502.SZ",  # 新易盛   - 光模块，权重~1.90%
        "000333.SZ",  # 美的集团 - 家电，权重~1.48%
        "600900.SH",  # 长江电力 - 公用事业，权重~1.33%
        "601166.SH",  # 兴业银行 - 银行，权重~1.28%
        # ==================== 金融地产 ====================
        "601398.SH",  # 工商银行
        "601988.SH",  # 中国银行
        "601288.SH",  # 农业银行
        "601628.SH",  # 中国人寿
        "600000.SH",  # 浦发银行
        "600016.SH",  # 民生银行
        "601328.SH",  # 交通银行
        "601601.SH",  # 中国太保
        "601336.SH",  # 新华保险
        "000001.SZ",  # 平安银行
        "002142.SZ",  # 宁波银行
        "601939.SH",  # 建设银行
        "601658.SH",  # 邮储银行
        "600030.SH",  # 中信证券
        "300059.SZ",  # 东方财富
        "601688.SH",  # 华泰证券
        "601881.SH",  # 中国银河
        "600837.SH",  # 海通证券
        "601211.SH",  # 国泰君安
        "601788.SH",  # 光大证券
        "600037.SH",  # 中信建投
        "000776.SZ",  # 广发证券
        "002736.SZ",  # 国信证券
        "600999.SH",  # 招商证券
        "601555.SH",  # 东吴证券
        "601009.SH",  # 南京证券
        "000002.SZ",  # 万科A
        "600048.SH",  # 保利发展
        "000031.SZ",  # 大悦城
        # ==================== 消费龙头 ====================
        "000858.SZ",  # 五粮液
        "000568.SZ",  # 泸州老窖
        "600887.SH",  # 伊利股份
        "000651.SZ",  # 格力电器
        "600690.SH",  # 海尔智家
        "603288.SH",  # 海天味业
        "002714.SZ",  # 牧原股份
        "600597.SH",  # 光明乳业
        "000895.SZ",  # 双汇发展
        "002304.SZ",  # 洋河股份
        "600779.SH",  # 水井坊
        "603589.SH",  # 口子窖
        # ==================== 科技龙头 ====================
        "688981.SH",  # 中芯国际 - 半导体
        "002415.SZ",  # 海康威视 - 安防
        "002475.SZ",  # 立讯精密 - 电子制造
        "603986.SH",  # 兆易创新 - 半导体
        "603501.SH",  # 韦尔股份 - 半导体
        "688041.SH",  # 海光信息 - 半导体
        "300760.SZ",  # 迈瑞医疗 - 医疗器械
        "600276.SH",  # 恒瑞医药 - 医药
        "300015.SZ",  # 爱尔眼科 - 医疗服务
        "603259.SH",  # 药明康德 - CRO
        "300122.SZ",  # 智飞生物 - 疫苗
        "300347.SZ",  # 泰格医药 - CRO
        "000538.SZ",  # 云南白药 - 中药
        "600436.SH",  # 片仔癀 - 中药
        "000063.SZ",  # 中兴通讯 - 通信设备
        "002230.SZ",  # 科大讯飞 - AI
        "300896.SZ",  # 爱美客 - 医美
        "300595.SZ",  # 欧普康视 - 医疗器械
        # ==================== 光模块"易中天三兄弟" ====================
        "300308.SZ",  # 中际旭创 - 全球光模块龙头
        "300502.SZ",  # 新易盛   - 产能持续释放
        "300394.SZ",  # 天孚通信 - CPO光引擎领先
        "002281.SZ",  # 光迅科技 - 光模块+光纤一体化
        "000988.SZ",  # 华工科技 - 1.6T光模块
        "600487.SH",  # 亨通光电 - 光通信全产业链
        # ==================== 新能源 ====================
        "002594.SZ",  # 比亚迪 - 新能源汽车
        "601012.SH",  # 隆基绿能 - 光伏
        "300274.SZ",  # 阳光电源 - 逆变器
        "002460.SZ",  # 赣锋锂业 - 锂矿
        "002466.SZ",  # 天齐锂业 - 锂矿
        "603799.SH",  # 华友钴业 - 钴
        "300014.SZ",  # 亿纬锂能 - 电池
        "002202.SZ",  # 金风科技 - 风电
        "600438.SH",  # 通威股份 - 光伏
        "688472.SH",  # 阿特斯 - 光伏
        "688223.SH",  # 晶科能源 - 光伏
        # ==================== 周期资源 ====================
        "601088.SH",  # 中国神华 - 煤炭
        "600309.SH",  # 万华化学 - 化工
        "600585.SH",  # 海螺水泥 - 水泥
        "600028.SH",  # 中国石化 - 石化
        "601857.SH",  # 中国石油 - 石油
        "600547.SH",  # 山东黄金 - 黄金
        "600489.SH",  # 中金黄金 - 黄金
        "600111.SH",  # 北方稀土 - 稀土
        "600259.SH",  # 广晟有色 - 稀土
        "600362.SH",  # 江西铜业 - 铜
        "000629.SZ",  # 攀钢钒钛 - 钒钛
        # ==================== 军工制造 ====================
        "600760.SH",  # 中航沈飞
        "600893.SH",  # 航发动力
        "000768.SZ",  # 中航西飞
        "600372.SH",  # 中航电子
        "601766.SH",  # 中国中车
        "600528.SH",  # 中铁工业
        "601800.SH",  # 中国交建
        "601390.SH",  # 中国中铁
        "601186.SH",  # 中国铁建
        # ==================== 其他核心标的 ====================
        "300033.SZ",  # 同花顺 - 金融软件
        "600570.SH",  # 恒生电子 - 金融软件
        "002027.SZ",  # 分众传媒 - 广告
        "000725.SZ",  # 京东方A - 面板
        "002129.SZ",  # TCL中环 - 光伏
        "600340.SH",  # 华夏幸福 - 地产
        "000938.SZ",  # 紫光国微 - 半导体
        "000963.SZ",  # 华东医药 - 医药
        "002007.SZ",  # 华兰生物 - 疫苗
        "002241.SZ",  # 歌尔股份 - 消费电子
        "002352.SZ",  # 顺丰控股 - 快递
        "002371.SZ",  # 北方华创 - 半导体设备
        "300433.SZ",  # 蓝思科技 - 消费电子
        "300144.SZ",  # 宋城演艺 - 文旅
        "300146.SZ",  # 汤臣倍健 - 保健品
        "300207.SZ",  # 欣旺达 - 电池
        "300601.SZ",  # 康泰生物 - 疫苗
        "300676.SZ",  # 华大基因 - 基因检测
        "600050.SH",  # 中国联通 - 通信
        "600018.SH",  # 上港集团 - 港口
        "601018.SH",  # 宁波港 - 港口
        "601919.SH",  # 中远海控 - 航运
        "600019.SH",  # 宝钢股份 - 钢铁
        "600581.SH",  # 八一钢铁 - 钢铁
        "600282.SH",  # 南钢股份 - 钢铁
        "600919.SH",  # 江苏银行 - 银行
        "600926.SH",  # 杭州银行 - 银行
        "601818.SH",  # 光大银行 - 银行
        "601998.SH",  # 中信银行 - 银行
        "600958.SH",  # 东方证券 - 券商
        "601377.SH",  # 兴业证券 - 券商
        "601006.SH",  # 大秦铁路 - 铁路
        "600029.SH",  # 南方航空 - 航空
        "601866.SH",  # 中远海发 - 航运
        "600031.SH",  # 三一重工 - 机械
        "000157.SZ",  # 中联重科 - 机械
        "000039.SZ",  # 中集集团 - 集装箱
        "600089.SH",  # 特变电工 - 电力设备
        "600406.SH",  # 国电南瑞 - 电力设备
        "600522.SH",  # 中天科技 - 通信
        "002413.SZ",  # 雷科防务 - 军工
        "002555.SZ",  # 三七互娱 - 游戏
        "002624.SZ",  # 完美世界 - 游戏
        "603444.SH",  # 吉比特 - 游戏
        "300413.SZ",  # 芒果超媒 - 媒体
        "300251.SZ",  # 光线传媒 - 影视
        "300803.SZ",  # 指南针 - 金融软件（2025.12调入）
        "600930.SH",  # 华电新能 - 新能源（2025.12调入）
        "002384.SZ",  # 东山精密 - 电子（2025.12调入）
        "002625.SZ",  # 光启技术 - 军工（2025.12调入）
        "300476.SZ",  # 胜宏科技 - 电子（2025.12调入）
        "601456.SH",  # 国联证券 - 券商（2025.12调入）
        "300866.SZ",  # 安克创新 - 消费电子（2025.12调入）
        "603893.SH",  # 瑞芯微 - 半导体（2025.12调入）
        "600010.SH",  # 包钢股份 - 钢铁
        "600104.SH",  # 上汽集团 - 汽车
        "600176.SH",  # 中国巨石 - 建材
        "600183.SH",  # 生益科技 - 电子
        "600208.SH",  # 新湖中宝 - 地产
        "600221.SH",  # 海航控股 - 航空
        "600236.SH",  # 桂冠电力 - 电力
        "600256.SH",  # 广汇能源 - 能源
        "600271.SH",  # 航天信息 - 科技
        "600307.SH",  # 酒钢宏兴 - 钢铁
        "600312.SH",  # 平高电气 - 电力设备
        "600320.SH",  # 振华重工 - 机械
        "600325.SH",  # 华发股份 - 地产
        "600332.SH",  # 白云山 - 医药
        "600350.SH",  # 山东高速 - 公路
        "600352.SH",  # 浙江龙盛 - 化工
        "600369.SH",  # 西南证券 - 券商
        "600373.SH",  # 中文传媒 - 媒体
        "600380.SH",  # 健康元 - 医药
        "600395.SH",  # 盘江股份 - 煤炭
        "600415.SH",  # 小商品城 - 商贸
        "600456.SH",  # 宝钛股份 - 钛材
        "600460.SH",  # 士兰微 - 半导体
        "600497.SH",  # 驰宏锌锗 - 有色
        "600500.SH",  # 中化国际 - 化工
        "600508.SH",  # 上海能源 - 能源
        "600516.SH",  # 方大炭素 - 新材料
        "600521.SH",  # 华海药业 - 医药
        "600535.SH",  # 天士力 - 中药
        "600549.SH",  # 厦门钨业 - 钨
        "600550.SH",  # 保变电气 - 电力设备
        "600563.SH",  # 法拉电子 - 电子
        "600583.SH",  # 海油工程 - 油气
        "600594.SH",  # 益佰制药 - 医药
        "600596.SH",  # 新安股份 - 化工
        "600600.SH",  # 青岛啤酒 - 食品
        "600660.SH",  # 福耀玻璃 - 汽车玻璃
        "600703.SH",  # 三安光电 - LED
        "600741.SH",  # 华域汽车 - 汽车零部件
        "600795.SH",  # 国电电力 - 电力
        "600809.SH",  # 山西汾酒 - 白酒
        "600848.SH",  # 上海临港 - 园区
        "600872.SH",  # 中炬高新 - 食品
        "600966.SH",  # 博汇纸业 - 造纸
        "601009.SH",  # 南京证券 - 券商（已在金融地产）
        "601018.SH",  # 宁波港（已在其他核心标的）
        "601108.SH",  # 财通证券 - 券商
        "601155.SH",  # 新城控股 - 地产
        "601229.SH",  # 上海银行 - 银行
        "601727.SH",  # 上海电气 - 电气设备
        "601877.SH",  # 正泰电器 - 电气设备
        "601901.SH",  # 方正证券 - 券商
        "601933.SH",  # 永辉超市 - 零售
        "601989.SH",  # 中国重工 - 船舶
        "000009.SZ",  # 中国宝安 - 综合
        "000012.SZ",  # 南玻A - 玻璃
        "000021.SZ",  # 深科技 - 电子
        "000025.SZ",  # 特力A - 综合
        "000027.SZ",  # 深圳能源 - 电力
        "000028.SZ",  # 国药一致 - 医药
        "000059.SZ",  # 华锦股份 - 化工
        "000060.SZ",  # 中金岭南 - 有色
        "000069.SZ",  # 华侨城A - 文旅
        "000402.SZ",  # 金融街 - 地产
        "000423.SZ",  # 东阿阿胶 - 中药
        "000625.SZ",  # 长安汽车 - 汽车
        "000681.SZ",  # 视觉中国 - 媒体
        "000708.SZ",  # 中信特钢 - 钢铁
        "000728.SZ",  # 国元证券 - 券商
        "000783.SZ",  # 长江证券 - 券商
        "000786.SZ",  # 北新建材 - 建材
        "002022.SZ",  # 科华生物 - 医药
        "002030.SZ",  # 达安基因 - 医药
        "002038.SZ",  # 双鹭药业 - 医药
        "002146.SZ",  # 荣盛发展 - 地产
        "002203.SZ",  # 海亮股份 - 有色
        "002252.SZ",  # 上海莱士 - 血液制品
        "002310.SZ",  # 东方园林 - 园林
        "002385.SZ",  # 大北农 - 农业
        "002456.SZ",  # 欧菲光 - 电子
        "002601.SZ",  # 龙蟒佰利 - 化工
        "002653.SZ",  # 海思科 - 医药
        "002821.SZ",  # 凯莱英 - CRO
        "002859.SZ",  # 洁美科技 - 电子
        "002867.SZ",  # 周大生 - 珠宝
        "002916.SZ",  # 深南电路 - 电子
        "002938.SZ",  # 鹏鼎控股 - 电子
        "300003.SZ",  # 乐普医疗 - 医疗器械
        "300017.SZ",  # 网宿科技 - CDN
        "300024.SZ",  # 机器人 - 机器人
        "300124.SZ",  # 汇川技术 - 自动化
        "300352.SZ",  # 北信源 - 软件
        "300498.SZ",  # 温氏股份 - 养殖
        "688271.SZ",  # 联影医疗 - 医疗器械
        "688506.SZ",  # 百利天恒 - 医药
        "688396.SH",  # 华润微 - 半导体
        "688303.SH",  # 大全能源 - 光伏
        "688256.SH",  # 寒武纪 - AI芯片
        "688187.SH",  # 时代电气 - 电力设备
    ]
    
    return list(dict.fromkeys(csi300_stocks))


def main():
    # Count project code lines
    count_project_code()

    # 建立与本地数据库的连接
    conn = create_database_and_tables()


    try:
        download_basic_data(conn)
        download_stock_data(conn)
        #run_backtest(conn)
        main_filter(conn)

    except Exception as e:
        # 捕获主流程中的任何异常，并记录详细错误信息
        logger.error(f"主程序执行出错: {e}", exc_info=True)
    finally:
        # 程序结束前，确保关闭数据库连接和 Baostock 登录会话
        conn.close()
        bs.logout()
        logger.info("已断开数据库连接并退出 Baostock。")

def run_backtest(db_conn):

    # 1. Create backtest runner
    runner = ParallelBacktestRunner(db_conn)

    # 2. Configure backtest tasks
    configs = [
        {
            "strategy": {
                "name": "factor_strategy",
                "params": {
                    "trend_weight": 0.25,
                    "momentum_weight": 0.25,
                    "quality_weight": 0.25,
                    "timing_weight": 0.25,
                    "buy_threshold": 0.6,
                    "sell_threshold": 0.4
                }
            },
            "data": {
                "stock_code": "000001.SZ",
                "start_date": "2020-01-01",
                "end_date": "2025-12-31"
            },
            "initial_cash": 1000000
        }
    ]
    
    # 3. Execute backtest
    results = runner.run_batch(configs)

    # 交易净收益列表
    for result in results:
        if 'error' in result:
            logger.error(f"回测出错: {result['error']}")
            continue
        strategy = result['strategy']
        
        # 打印交易记录（成交记录）
        if 'transactions' in result and result['transactions']:
            print(f"\n=== {strategy} 买卖记录 ===")
            txs = result['transactions']
            
            # 解析 Backtrader Transactions 格式
            # 格式: OrderedDict({datetime: [[amount, price, commission, stock_code, total_amount]]})
            for dt, tx_list in txs.items():
                for tx_sub_list in tx_list:
                    if len(tx_sub_list) >= 4:
                        amount = tx_sub_list[0]
                        price = tx_sub_list[1]
                        comm = tx_sub_list[2]
                        tx_type = "买入" if amount > 0 else "卖出"
                        date_str = dt.date().isoformat() if hasattr(dt, 'date') else str(dt)
                        print(f"  {date_str} | {tx_type:4} | 数量: {abs(amount):5} | 价格: {price:8.2f} | 佣金: {comm:6.2f}")
        
        # 打印交易盈亏
        if 'trades' in result and result['trades']:
            print(f"\n=== {strategy} 交易盈亏 ===")
            for trade in result['trades']:
                print(f"  日期: {trade['date']}, 净收益: {trade['net']:.2f}")

            print(f"\n--- {strategy} 统计 ---")
            print(f"  总交易次数: {len(result['trades'])}")
            print(f"  盈利交易: {len([t for t in result['trades'] if t['net'] > 0])}")
            print(f"  亏损交易: {len([t for t in result['trades'] if t['net'] < 0])}")

    # 4. Analyze results
    analyzer = PerformanceAnalyzer()
    analysis = analyzer.compare(results)
    logger.info(json.dumps(analysis, indent=4, ensure_ascii=False))

def download_basic_data(conn):
    """下载基础数据"""
    download_csi300_components(conn)  # 下载沪深300_components(conn, params)

def download_stock_data(conn):

    """主函数，协调整个数据下载流程。"""
    # 1. 登录 Baostock 服务
    lg = bs.login()
    if BaostockErrorCode.IP_BLACKLIST == lg.error_code:
        logger.error("IP已经加入黑名单, 需要去QQ群里求助")
        return

    if BaostockErrorCode.CONNECTION_REFUSED == lg.error_code:
        logger.error("连接被拒绝, 请检查网络设置")
        return

    if BaostockErrorCode.SUCCESS != lg.error_code:
        logger.error(f"Baostock 登录失败: {lg.error_msg}")
        return
    logger.info("Baostock 登录成功。")

    start_year = 2022
    end_year = 2027
    stock_codes = get_csi300_stock_codes()  # 获取沪深300成分股股票代码
    params = DownloadParameters(start_year=start_year, end_year=end_year, stock_codes=stock_codes)

    download_trade_date_map(conn, params)  # 下载交易日映射表，覆盖start_year-end_year年
    # 2. 第一步：同步并更新股票的基础信息表 (stock_basic)
    download_stock_basic(conn, params, [MarketType.INDEX,MarketType.SZ_MAIN_BOARD])  # 下载股票详细信息（行业、上市日期等）
    # 3. 第二步：下载所有活跃股票的日线数据
    # start_date 参数是可选的。如果不提供，download_all_stocks_daily_data 会尝试从 stock_basic 表中获取上市日期。
    start_new_daily_download(conn, params)
    # 4. 第三步：下载行业分类数据
    # start_new_industry_download(conn, 2020, 2025)  # 从头开始下载2020-2025年的行业分类数据
    # continue_download_industry(conn, 2020, 2025)  # 继续下载2020-2025年的行业分类数据
    # 5. 第四步：下载5分钟K线数据（示例）
    # start_new_kline_download(conn, start_year, end_year)  # 下载5分钟K线数据，示例股票代码
    # continue_download_kline(conn, start_year, end_year, KLinePeriod.MIN_5)  # 继续下载2026-2027年的5分钟K线数据
    # 6. 第五步：下载分红送配数据
    # start_new_xrxd_download(conn, start_year, end_year)  # 下载2026-2027年的分 红送配数据  
    # continue_download_xrxd(conn, start_year, end_year)  # 下载2026-2027年的分红送配数据
    # 7. 第六步：下载复权因子数据
    # start_new_adj_factor_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的复权因子数据
    # continue_download_adj_factor(conn, start_year, end_year)  # 继续下载2026-2027年的复权因子数据
    # 8. 第七步：下载股票利润数据
    start_new_profit_download(conn, params)  # 从头开始下载2026-2027年的股票利润数据

    # 9. 第八步：下载公司偿债能力数据
    # start_new_balance_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的公司偿债能力数据
    # continue_download_company_balance(conn, start_year, end_year)  # 继续下载2026-2027年的公司偿债能力数据
    
    # 10. 第九步：下载公司现金流量数据
    # start_new_cash_flow_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的公司现金流量数据
    # continue_download_company_cash_flow(conn, start_year, end_year)  # 继续下载2026-2027年的公司现金流量数据
    # 11. 第十步：为公司股票数据打分
    # score_single_stock(conn, stock_codes[0])

# 程序入口点，当直接运行此脚本时，会执行 main() 函数
if __name__ == '__main__':
    main()