# 导入所需库
import pandas as pd
import talib as ta
import warnings
from datetime import datetime, timedelta
from Ingredient.DataNest import StockFilterManager
from KitchenBase.logger_config import get_logger

# 关闭无关警告
warnings.filterwarnings('ignore')

# 获取日志记录器
logger = get_logger(__name__)

# ===================== 全局可调整参数（核心！可根据你的需求修改）=====================
# 数据周期参数
END_DATE = datetime.today().strftime('%Y%m%d')  # 数据结束日期（默认今日）
START_DATE = (datetime.today() - timedelta(days=200)).strftime('%Y%m%d')  # 数据开始日期（默认前200天，确保有足够数据计算MA60等指标）

# 风险过滤参数
MIN_MARKET_CAP = 50  # 最小流通市值（单位：亿），排除流动性差的小盘股
MIN_LIST_DAYS = 60  # 上市最少天数，排除次新股

# 1. 平台/箱体突破策略参数
BOX_RANGE_DAYS = 20  # 箱体横盘周期（交易日）
BOX_FLUCTUATION_RATE = 0.15  # 箱体最大波动幅度（15%）
BOX_BREAK_THRESHOLD = 1.03  # 突破箱体上沿的阈值（站稳3%以上，有效突破）
BOX_VOLUME_MULTIPLE = 2  # 突破当日量能放大倍数（2倍于前5日平均）

# 2. 底部反转/超跌反弹策略参数
REVERSE_FALL_DAYS = 60  # 累计跌幅计算周期（前60日）
REVERSE_MAX_FALL_RATE = 0.5  # 最大累计跌幅阈值（50%）
REVERSE_BUILD_DAYS = 20  # 筑底周期（20日）
REVERSE_RISE_THRESHOLD = 0.03  # 反转当日最低涨幅（3%）
REVERSE_VOLUME_MULTIPLE = 2  # 反转当日量能放大倍数（2倍）
REVERSE_RSI_OVERSOLD = 20  # RSI超卖区阈值（20以下）

# 3. 上升趋势回踩企稳策略参数
TREND_MA_DAYS = [5, 10, 20, 60]  # 均线周期（5/10/20/60日）
TREND_PULLBACK_VOLUME_RATIO = 0.8  # 回调缩量阈值（≤前5日平均的80%）
TREND_REBOUND_VOLUME_MULTIPLE = 1.5  # 回升放量阈值（≥前5日平均的1.5倍）

# 4. 多指标共振策略参数
RESONANCE_RSI_LOWER = 50  # RSI最低阈值（≥50，多头区间）
RESONANCE_RSI_UPPER = 70  # RSI最高阈值（≤70，无超买）
# ========================================================================================

# ===================== 基础工具函数（无需修改）=====================
def get_stock_daily_data(db_conn, stock_code):
    """获取单只股票的日线数据，返回处理后的DataFrame
    
    Args:
        db_conn: 数据库连接对象
        stock_code: 股票代码
        
    Returns:
        pd.DataFrame: 包含日线数据的DataFrame，None表示获取失败或数据不足
    """
    from Ingredient.DataNest import DailyDataManager
    
    try:
        logger.debug(f"正在获取股票 {stock_code} 的日线数据...")
        daily_manager = DailyDataManager(db_conn)
        # 从数据库获取日线数据
        df = daily_manager.get_price_data(stock_code, START_DATE, END_DATE)
        
        if df.empty:
            logger.debug(f"股票 {stock_code} 无数据")
            return None
        
        # 按日期升序排序
        df = df.sort_values('date').reset_index(drop=True)
        
        # 过滤停牌/无成交量的数据
        original_count = len(df)
        df = df[df['volume'] > 0].reset_index(drop=True)
        if len(df) < original_count:
            logger.debug(f"股票 {stock_code} 过滤掉 {original_count - len(df)} 条停牌数据")
        
        # 检查数据量是否足够（至少60个交易日，覆盖所有策略的计算周期）
        if len(df) < 60:
            logger.debug(f"股票 {stock_code} 数据量不足：只有 {len(df)} 条，需要至少60条")
            return None
        
        logger.debug(f"股票 {stock_code} 数据获取成功，共 {len(df)} 条有效数据")
        return df
    except Exception as e:
        logger.error(f"获取股票 {stock_code} 数据失败：{str(e)}", exc_info=True)
        return None

def calculate_technical_indicators(df):
    """计算所有技术指标，返回添加了指标的DataFrame"""
    try:
        # 1. 均线（MA）
        for day in TREND_MA_DAYS:
            df[f'ma{day}'] = ta.MA(df['close'], timeperiod=day)
        # 2. MACD
        df['macd_dif'], df['macd_dea'], df['macd_hist'] = ta.MACD(
            df['close'], fastperiod=12, slowperiod=26, signalperiod=9
        )
        # 3. RSI（14日，通用周期）
        df['rsi14'] = ta.RSI(df['close'], timeperiod=14)
        # 4. KDJ
        df['kdj_k'], df['kdj_d'] = ta.STOCH(
            df['high'], df['low'], df['close'],
            fastk_period=9, slowk_period=3, slowd_period=3
        )
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
        # 5. 布林带（20日，通用周期）
        df['boll_upper'], df['boll_mid'], df['boll_lower'] = ta.BBANDS(
            df['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=ta.MA_Type.SMA
        )
        # 6. 前5日平均成交量（用于量能判断）
        df['volume_ma5'] = ta.MA(df['volume'], timeperiod=5)
        # 去除空值
        original_count = len(df)
        df = df.dropna().reset_index(drop=True)
        if len(df) < original_count:
            logger.debug(f"技术指标计算后过滤掉 {original_count - len(df)} 条NaN数据")
        return df
    except Exception as e:
        logger.error(f"计算技术指标失败：{str(e)}", exc_info=True)
        return pd.DataFrame()

def log_filter_reason(stock_code, reason, is_debug=False):
    """记录股票筛选失败的原因
    
    Args:
        stock_code: 股票代码
        reason: 失败原因
        is_debug: 是否为debug级别日志，默认为True
    """
    if is_debug:
        logger.debug(f"股票 {stock_code} 筛选失败：{reason}")
    else:
        logger.info(f"股票 {stock_code} 筛选失败：{reason}")

# ===================== 4大核心筛选策略函数（可单独/组合使用）=====================
def check_box_breakout(df, stock_code=None):
    """检查是否符合平台/箱体突破策略，返回True/False"""
    if len(df) < BOX_RANGE_DAYS + 5:
        if stock_code:
            log_filter_reason(stock_code, f"数据量不足{BOX_RANGE_DAYS + 5}条", is_debug=True)
        return False
    # 取最新的交易日数据
    latest = df.iloc[-1]
    # 取横盘周期内的数据
    box_data = df.iloc[-(BOX_RANGE_DAYS + 1):-1]
    # 计算箱体上下沿
    box_high = box_data['high'].max()
    box_low = box_data['low'].min()
    # 1. 检查箱体波动幅度是否符合要求
    box_fluctuation = (box_high / box_low) - 1
    if box_fluctuation > BOX_FLUCTUATION_RATE:
        if stock_code:
            log_filter_reason(stock_code, f"箱体波动幅度过大：{box_fluctuation:.2%} > {BOX_FLUCTUATION_RATE:.2%}", is_debug=True)
        return False
    # 2. 检查是否有效突破箱体上沿
    if latest['close'] < box_high * BOX_BREAK_THRESHOLD:
        if stock_code:
            log_filter_reason(stock_code, f"未有效突破箱体上沿：{latest['close']:.2f} < {box_high * BOX_BREAK_THRESHOLD:.2f}", is_debug=True)
        return False
    # 3. 检查量能是否放大
    if latest['volume'] < latest['volume_ma5'] * BOX_VOLUME_MULTIPLE:
        if stock_code:
            log_filter_reason(stock_code, f"量能未放大：{latest['volume']} < {latest['volume_ma5'] * BOX_VOLUME_MULTIPLE}", is_debug=True)
        return False
    # 4. 检查是否站稳5、10日均线
    if latest['close'] < latest['ma5'] or latest['close'] < latest['ma10']:
        if stock_code:
            log_filter_reason(stock_code, f"未站稳均线：收盘价{latest['close']:.2f} < MA5{latest['ma5']:.2f} 或 MA10{latest['ma10']:.2f}", is_debug=True)
        return False
    # 所有条件满足
    if stock_code:
        logger.debug(f"股票 {stock_code} 符合箱体突破策略")
    return True

def check_bottom_reverse(df, stock_code=None):
    """检查是否符合底部反转/超跌反弹策略，返回True/False"""
    if len(df) < REVERSE_FALL_DAYS + REVERSE_BUILD_DAYS:
        if stock_code:
            log_filter_reason(stock_code, f"数据量不足{REVERSE_FALL_DAYS + REVERSE_BUILD_DAYS}条", is_debug=True)
        return False
    # 取最新的交易日数据
    latest = df.iloc[-1]
    # 1. 检查累计跌幅是否符合要求
    prev_high = df.iloc[-(REVERSE_FALL_DAYS + REVERSE_BUILD_DAYS):-REVERSE_BUILD_DAYS]['high'].max()
    current_fall_rate = (prev_high - latest['close']) / prev_high
    if current_fall_rate < REVERSE_MAX_FALL_RATE:
        if stock_code:
            log_filter_reason(stock_code, f"累计跌幅不足：{current_fall_rate:.2%} < {REVERSE_MAX_FALL_RATE:.2%}", is_debug=True)
        return False
    # 2. 检查筑底周期内的波动（横盘筑底）
    build_data = df.iloc[-(REVERSE_BUILD_DAYS + 1):-1]
    build_high = build_data['high'].max()
    build_low = build_data['low'].min()
    build_fluctuation = (build_high / build_low) - 1
    if build_fluctuation > 0.2:  # 筑底周期内波动不超过20%
        if stock_code:
            log_filter_reason(stock_code, f"筑底周期波动过大：{build_fluctuation:.2%} > 20%", is_debug=True)
        return False
    # 3. 检查反转当日涨幅
    latest_rise_rate = (latest['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close']
    if latest_rise_rate < REVERSE_RISE_THRESHOLD:
        if stock_code:
            log_filter_reason(stock_code, f"反转当日涨幅不足：{latest_rise_rate:.2%} < {REVERSE_RISE_THRESHOLD:.2%}", is_debug=True)
        return False
    # 4. 检查量能是否放大
    if latest['volume'] < latest['volume_ma5'] * REVERSE_VOLUME_MULTIPLE:
        if stock_code:
            log_filter_reason(stock_code, f"量能未放大：{latest['volume']} < {latest['volume_ma5'] * REVERSE_VOLUME_MULTIPLE}", is_debug=True)
        return False
    # 5. 检查RSI是否从超卖区回升
    if df.iloc[-5]['rsi14'] > REVERSE_RSI_OVERSOLD or latest['rsi14'] < 50:
        if stock_code:
            log_filter_reason(stock_code, f"RSI不符合要求：前5日{df.iloc[-5]['rsi14']:.1f}或当前{latest['rsi14']:.1f}", is_debug=True)
        return False
    # 6. 检查MACD、KDJ是否金叉
    macd_gold_cross = (df.iloc[-2]['macd_dif'] < df.iloc[-2]['macd_dea']) and (latest['macd_dif'] > latest['macd_dea'])
    kdj_gold_cross = (df.iloc[-2]['kdj_k'] < df.iloc[-2]['kdj_d']) and (latest['kdj_k'] > latest['kdj_d'])
    if not (macd_gold_cross and kdj_gold_cross):
        if stock_code:
            log_filter_reason(stock_code, f"MACD或KDJ未金叉：MACD={macd_gold_cross}, KDJ={kdj_gold_cross}", is_debug=True)
        return False
    # 所有条件满足
    if stock_code:
        logger.debug(f"股票 {stock_code} 符合底部反转策略")
    return True

def check_trend_pullback(df, stock_code=None):
    """检查是否符合上升趋势回踩企稳策略，返回True/False"""
    if len(df) < 60:
        if stock_code:
            log_filter_reason(stock_code, "数据量不足60条", is_debug=True)
        return False
    # 取最新的交易日数据
    latest = df.iloc[-1]
    prev_1 = df.iloc[-2]
    prev_2 = df.iloc[-3]
    # 1. 检查均线是否多头排列（5>10>20>60）
    if not (latest['ma5'] > latest['ma10'] > latest['ma20'] > latest['ma60']):
        if stock_code:
            log_filter_reason(stock_code, f"均线非多头排列：MA5{latest['ma5']:.2f} MA10{latest['ma10']:.2f} MA20{latest['ma20']:.2f} MA60{latest['ma60']:.2f}", is_debug=True)
        return False
    # 2. 检查是否回踩关键均线（5/10/20）并企稳
    # 回踩条件：前2日最低价触碰均线，当日收盘价站稳均线
    pullback_ma5 = (prev_2['low'] <= prev_2['ma5']) and (prev_1['low'] <= prev_1['ma5']) and (latest['close'] >= latest['ma5'])
    pullback_ma10 = (prev_2['low'] <= prev_2['ma10']) and (prev_1['low'] <= prev_1['ma10']) and (latest['close'] >= latest['ma10'])
    pullback_ma20 = (prev_2['low'] <= prev_2['ma20']) and (prev_1['low'] <= prev_1['ma20']) and (latest['close'] >= latest['ma20'])
    if not (pullback_ma5 or pullback_ma10 or pullback_ma20):
        if stock_code:
            log_filter_reason(stock_code, "未回踩关键均线", is_debug=True)
        return False
    # 3. 检查回调缩量、回升放量
    callback_volume = (prev_2['volume'] <= prev_2['volume_ma5'] * TREND_PULLBACK_VOLUME_RATIO) and (prev_1['volume'] <= prev_1['volume_ma5'] * TREND_PULLBACK_VOLUME_RATIO)
    rebound_volume = latest['volume'] >= latest['volume_ma5'] * TREND_REBOUND_VOLUME_MULTIPLE
    if not (callback_volume and rebound_volume):
        if stock_code:
            log_filter_reason(stock_code, f"量能不符合要求：回调缩量={callback_volume}, 回升放量={rebound_volume}", is_debug=True)
        return False
    # 4. 检查趋势未破（MACD、RSI仍处于多头区间）
    if latest['macd_dif'] < latest['macd_dea'] or latest['rsi14'] < 50:
        if stock_code:
            log_filter_reason(stock_code, f"趋势已破：MACD DIF{latest['macd_dif']:.2f} < DEA{latest['macd_dea']:.2f} 或 RSI{latest['rsi14']:.1f} < 50", is_debug=True)
        return False
    # 所有条件满足
    if stock_code:
        logger.debug(f"股票 {stock_code} 符合回踩企稳策略")
    return True

def check_multi_indicator_resonance(df, stock_code=None):
    """检查是否符合多指标共振策略，返回True/False"""
    if len(df) < 30:
        if stock_code:
            log_filter_reason(stock_code, "数据量不足30条", is_debug=True)
        return False
    # 取最新的交易日数据
    latest = df.iloc[-1]
    prev_1 = df.iloc[-2]
    # 1. 均线信号：收盘价站稳5、10日均线，5日均线向上拐头
    ma_signal = (latest['close'] >= latest['ma5']) and (latest['close'] >= latest['ma10']) and (latest['ma5'] > prev_1['ma5'])
    # 2. MACD信号：DIF与DEA金叉，DIF>DEA，红柱放大
    macd_signal = (prev_1['macd_dif'] < prev_1['macd_dea']) and (latest['macd_dif'] > latest['macd_dea']) and (latest['macd_hist'] > prev_1['macd_hist'])
    # 3. RSI信号：处于50-70之间，多头区间，无超买
    rsi_signal = (latest['rsi14'] >= RESONANCE_RSI_LOWER) and (latest['rsi14'] <= RESONANCE_RSI_UPPER)
    # 4. KDJ信号：K、D、J金叉，J值≥20
    kdj_signal = (prev_1['kdj_k'] < prev_1['kdj_d']) and (latest['kdj_k'] > latest['kdj_d']) and (latest['kdj_j'] >= 20)
    # 5. 布林带信号：收盘价站稳中轨，向上轨运行
    boll_signal = (latest['close'] >= latest['boll_mid']) and (latest['close'] > prev_1['close'])
    # 统计满足的信号数量（至少4个信号共振）
    signal_count = sum([ma_signal, macd_signal, rsi_signal, kdj_signal, boll_signal])
    if signal_count < 4:
        if stock_code:
            log_filter_reason(stock_code, f"信号共振不足：{signal_count}/5个信号满足", is_debug=True)
        return False
    # 所有条件满足
    if stock_code:
        logger.debug(f"股票 {stock_code} 符合多指标共振策略，满足{signal_count}个信号")
    return True

# ===================== 主筛选函数（核心执行逻辑）=====================
def main_filter(db_conn, strategy_list=['box_breakout', 'bottom_reverse', 'trend_pullback', 'multi_indicator_resonance']):
    """
    主筛选函数，遍历所有股票，应用指定的筛选策略，输出符合条件的股票池
    
    Args:
        db_conn: 数据库连接对象
        strategy_list: 要应用的策略列表，可单独指定，比如只选箱体突破：['box_breakout']
        
    Returns:
        符合条件的股票池DataFrame
    """
    logger.info("=" * 60)
    logger.info("开始执行股票筛选")
    logger.info(f"筛选策略：{strategy_list}")
    logger.info(f"基础过滤条件：流通市值≥{MIN_MARKET_CAP}亿，上市≥{MIN_LIST_DAYS}天")
    
    # 1. 获取股票列表
    filter_manager = StockFilterManager(db_conn)
    stock_list = filter_manager.get_filtered_stock_list(min_market_cap=MIN_MARKET_CAP, min_list_days=MIN_LIST_DAYS)
    if len(stock_list) == 0:
        logger.warning("无符合基础过滤条件的股票，筛选终止")
        return None
    
    logger.info(f"基础过滤完成，待筛选股票数：{len(stock_list)} 只")
    
    # 2. 初始化结果列表和统计信息
    result_list = []
    stats = {
        'total': len(stock_list),
        'no_data': 0,
        'insufficient_data': 0,
        'no_qualified_strategy': 0,
        'qualified': 0
    }
    
    # 3. 遍历所有股票，逐个筛选
    total_count = len(stock_list)
    for idx, row in enumerate(stock_list.itertuples(index=False)):
        stock_code = row.stock_code
        stock_name = row.stock_name
        market_cap = float(row.market_cap) # type: ignore[arg-type]
        
        # 打印进度
        if (idx + 1) % 50 == 0:
            logger.info(f"筛选进度：{idx + 1}/{total_count} 只股票 ({(idx + 1) / total_count * 100:.1f}%)")
        elif (idx + 1) % 10 == 0:
            logger.debug(f"筛选进度：{idx + 1}/{total_count} 只股票")
        
        # 获取日线数据
        df = get_stock_daily_data(db_conn, stock_code)
        if df is None:
            stats['no_data'] += 1
            log_filter_reason(stock_code, "无日线数据", is_debug=True)
            continue
        if len(df) < 60:
            stats['insufficient_data'] += 1
            log_filter_reason(stock_code, f"日线数据不足60条：{len(df)}条", is_debug=True)
            continue
        
        # 计算技术指标
        df = calculate_technical_indicators(df)
        if len(df) < 30:
            stats['insufficient_data'] += 1
            log_filter_reason(stock_code, f"技术指标计算后数据不足30条：{len(df)}条", is_debug=True)
            continue
        
        # 应用筛选策略
        strategy_result = {}
        is_qualified = False
        # 箱体突破策略
        if 'box_breakout' in strategy_list:
            strategy_result['箱体突破'] = check_box_breakout(df, stock_code)
            if strategy_result['箱体突破']:
                is_qualified = True
        # 底部反转策略
        if 'bottom_reverse' in strategy_list:
            strategy_result['底部反转'] = check_bottom_reverse(df, stock_code)
            if strategy_result['底部反转']:
                is_qualified = True
        # 回踩企稳策略
        if 'trend_pullback' in strategy_list:
            strategy_result['回踩企稳'] = check_trend_pullback(df, stock_code)
            if strategy_result['回踩企稳']:
                is_qualified = True
        # 多指标共振策略
        if 'multi_indicator_resonance' in strategy_list:
            strategy_result['多指标共振'] = check_multi_indicator_resonance(df, stock_code)
            if strategy_result['多指标共振']:
                is_qualified = True
        
        # 检查是否符合任何策略
        if not is_qualified:
            stats['no_qualified_strategy'] += 1
            continue
        
        # 符合条件的股票，加入结果列表
        stats['qualified'] += 1
        # 取最新的股价、涨幅等信息
        latest = df.iloc[-1]
        result_list.append({
            '股票代码': stock_code,
            '股票名称': stock_name,
            '流通市值(亿)': round(market_cap, 2),
            '最新收盘价(元)': round(latest['close'], 2),
            '当日涨跌幅(%)': round((latest['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close'] * 100, 2),
            '符合策略': '、'.join([k for k, v in strategy_result.items() if v])
        })
        logger.info(f"✓ 股票 {stock_code}({stock_name}) 符合条件：{strategy_result}")
    
    # 4. 处理结果
    logger.info("=" * 60)
    logger.info("筛选统计：")
    logger.info(f"  总股票数：{stats['total']}")
    logger.info(f"  无数据：{stats['no_data']}")
    logger.info(f"  数据不足：{stats['insufficient_data']}")
    logger.info(f"  不符合策略：{stats['no_qualified_strategy']}")
    logger.info(f"  符合条件：{stats['qualified']}")
    
    if len(result_list) == 0:
        logger.warning("本次筛选无符合条件的股票")
        return None
    
    # 转换为DataFrame
    result_df = pd.DataFrame(result_list)
    # 按流通市值降序排序
    result_df = result_df.sort_values('流通市值(亿)', ascending=False).reset_index(drop=True)
    
    # 5. 保存结果到Excel文件
    try:
        result_df.to_excel('/mnt/技术面筛选股票池.xlsx', index=False)
        logger.info(f"结果已保存到：/mnt/技术面筛选股票池.xlsx")
    except Exception as e:
        logger.error(f"保存Excel文件失败：{str(e)}", exc_info=True)
    
    # 打印结果
    logger.info(f"\n===== 筛选完成！符合条件的股票共 {len(result_df)} 只 =====")
    logger.info("\n" + result_df.to_string(index=False))
    
    return result_df

# ===================== 执行筛选（可修改策略列表）=====================
if __name__ == '__main__':
    # 单独运行时创建数据库连接
    logger.info("=" * 60)
    logger.info("启动股票筛选程序")
    
    try:
        from Ingredient.DataNest import create_database_and_tables
        db_conn = create_database_and_tables()
        
        # 可单独指定筛选策略，比如只筛选箱体突破：strategy_list=['box_breakout']
        # 可选策略：'box_breakout'（箱体突破）、'bottom_reverse'（底部反转）、'trend_pullback'（回踩企稳）、'multi_indicator_resonance'（多指标共振）
        final_result = main_filter(db_conn, strategy_list=['box_breakout', 'bottom_reverse', 'trend_pullback', 'multi_indicator_resonance'])
        
        if final_result is not None:
            logger.info("股票筛选程序执行完成")
        else:
            logger.warning("股票筛选程序执行完成，但未找到符合条件的股票")
            
    except Exception as e:
        logger.error(f"执行筛选失败：{str(e)}", exc_info=True)
        import traceback
        traceback.print_exc()
    finally:
        if 'db_conn' in locals():
            db_conn.close()
            logger.debug("数据库连接已关闭")