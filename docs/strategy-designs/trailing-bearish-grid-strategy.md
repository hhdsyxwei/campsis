# Trailing-Bearish-Grid 策略设计文档

## 一、策略概述和适用场景

### 1.1 策略名称
**Trailing-Bearish-Grid**（动态基准空头网格策略）

### 1.2 核心机制
在下降通道中，建立动态移动的基准价（P_base），当价格反弹超过基准价一定幅度时卖出，当价格回落低于卖出价一定幅度时买入回补，通过"卖出-买入"闭环锁定波动收益。

### 1.3 核心特点
- ✅ **动态基准价**：基准价随下降通道自动下移
- ✅ **连续网格交易**：反弹时可连续卖出多个网格
- ✅ **底仓保护**：始终保留 50% 底仓不卖出
- ✅ **收益锁定**：每轮交易通过闭环锁定确定收益

### 1.4 适用场景
| 适合 | 不适合 |
|------|--------|
| ✅ 股票处于明确下降通道 | ❌ 单边下跌无反弹 |
| ✅ 有一定的波动幅度（日波动 > 2%） | ❌ 横盘震荡 |
| ✅ 长期持有，通过波动降低成本 | ❌ 快速 V 型反转 |
| ✅ 熊市防御性投资 | ❌ 牛市追涨 |

### 1.5 交易原则
1. 初始状态：50% 底仓（锚定股数 N）+ 50% 现金
2. 基准价始终跟随下降通道，不会悬在高位
3. 每笔交易都必须有买入回补，形成闭环
4. 底仓永远不低于初始的 50%

---

## 二、核心参数定义

### 2.1 基本参数

| 参数 | 符号 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| 初始底仓比例 | `initial_position_ratio` | float | 0.5 | 50% 资金作为底仓 |
| 网格卖出间距 | `grid_up_ratio` | float | 0.03 (3%) | 上网格间距 U% |
| 网格买入间距 | `grid_down_ratio` | float | 0.05 (5%) | 下网格间距 D% |
| 每格卖出比例 | `grid_sell_ratio` | float | 0.1 (10%) | 每次卖出底仓的 Q% |
| 基准价下移阈值 | `base_shift_threshold` | float | 0.02 (2%) | 基准价下移 2% 触发阈值 |
| 底仓保护线 | `min_position_ratio` | float | 0.5 | 剩余底仓不低于初始 50% |

### 2.2 扩展参数

| 参数 | 符号 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| 最大网格数量 | `max_grid_count` | int | 5 | 最多支持的网格数 |
| 最大单日波动 | `max_daily_volatility` | float | 0.08 (8%) | 异常行情过滤 |
| 成交量过滤开关 | `volume_filter` | bool | False | 是否启用成交量确认 |
| 止损线 | `stop_loss_line` | float | 0.20 (20%) | 极端止损阈值 |

---

## 三、交易逻辑详解

### 3.1 基准价（P_base）管理

#### 3.1.1 初始化
```python
# 策略启动日
p_base = closing_price  # 收盘价作为初始基准价
initial_shares = int(total_capital * initial_position_ratio / closing_price)
```

#### 3.1.2 动态下移规则（每日收盘后）
```python
# 每日检查基准价是否需要下移
if today_low < p_base * (1 - base_shift_threshold):
    # 跌破基准价 2%，更新为当日最低价
    p_base = today_low
    logger.info(f"基准价下移: {p_base:.2f}")
```

#### 3.1.3 基准价特点
- 只会下移，不会上移
- 始终紧跟下降通道的重心
- 确保网格不会悬在高位失效

---

### 3.2 卖出逻辑（高抛）

#### 3.2.1 卖出触发价计算（连续多格）
```python
# 第 1 次卖出
sell_price_1 = p_base * (1 + grid_up_ratio)

# 第 2 次卖出（基于上一次卖出价）
sell_price_2 = sell_price_1 * (1 + grid_up_ratio)

# 第 N 次卖出
sell_price_N = sell_price_N-1 * (1 + grid_up_ratio)
```

#### 3.2.2 卖出执行条件
```python
# 卖出触发条件
current_price >= calculated_sell_price  # 价格达到卖出价

# 数量计算
sell_shares = int(initial_shares * grid_sell_ratio)  # 固定数量

# 底仓保护检查
remaining_position = current_position - total_sold_shares
min_allowed = int(initial_shares * min_position_ratio)
if remaining_position - sell_shares < min_allowed:
    # 剩余底仓不足，暂停卖出
    return False, 0
```

#### 3.2.3 卖出流程
```
Step 1: 计算下一格卖出价
Step 2: 检查当前价格是否达到卖出价
Step 3: 检查底仓保护条件
Step 4: 计算卖出数量
Step 5: 执行卖出，记录卖出信息
Step 6: 等待继续卖出或买入回补
```

---

### 3.3 买入逻辑（低吸回补）

#### 3.3.1 买入触发价计算
```python
# 对应每一次卖出，独立计算买入价
buy_price_1 = sell_price_1 * (1 - grid_down_ratio)
buy_price_2 = sell_price_2 * (1 - grid_down_ratio)
...
buy_price_N = sell_price_N * (1 - grid_down_ratio)
```

#### 3.3.2 买入执行条件
```python
# 按卖出价从高到低检查
for sell_record in sold_grids_sorted_by_price_desc:
    if not sell_record.filled and current_price <= sell_record.buy_price:
        # 价格达到买入价
        # 检查现金是否充足
        required_cash = sell_record.shares * current_price
        if cash >= required_cash:
            # 执行买入
            buy_shares = sell_record.shares
            execute_buy(buy_shares)
            sell_record.filled = True
            # 计算单轮收益
            profit = (sell_record.sell_price - current_price) * buy_shares
            total_profit += profit
            return True, buy_shares, profit
```

#### 3.3.3 买入原则
1. 优先回补：按卖出价从高到低依次回补
2. 数量固定：与对应的卖出数量完全相等
3. 现金检查：确保有足够现金买入
4. 闭环完成：每一轮卖出买入都形成闭环

---

### 3.4 闭环与重置

#### 3.4.1 单轮闭环完成
```python
# 当某一轮卖出-买入配对完成后
if all_grids_filled:
    # 计算累计收益
    round_profit = sum(sell_amount - buy_amount for each grid)
    total_profit += round_profit
    
    # 记录完成日志
    logger.info(f"网格完成 #{round_count}: 收益 {round_profit:.2f} 元")
    
    # 重置网格状态
    sold_grids.clear()
    round_count += 1
```

#### 3.4.2 状态重置
- 清空所有卖出网格记录
- 重置网格计数器
- 等待下一轮卖出信号

---

## 四、状态变量设计

### 4.1 核心状态变量

| 变量名 | 类型 | 初始值 | 说明 |
|--------|------|--------|------|
| `initial_shares` | int | 计算 | 初始底仓股数 |
| `current_position` | int | initial_shares | 当前持仓股数 |
| `p_base` | float | 收盘价 | 动态基准价 |
| `sold_grids` | List[Dict] | [] | 已卖出网格记录 |
| `round_count` | int | 0 | 完成的网格轮数 |
| `total_profit` | float | 0 | 累计收益（已实现） |
| `last_price` | float | 0 | 上一次价格（用于计算基准价下移） |

### 4.2 网格记录结构

```python
sold_grid_record = {
    'round_id': int,           # 网格轮次 ID
    'grid_level': int,         # 网格层级（第几次卖出）
    'sell_price': float,       # 卖出价格
    'sell_shares': int,        # 卖出数量
    'buy_price': float,        # 对应的买入价格
    'filled': bool,            # 是否已回补
    'buy_price_actual': float  # 实际买入价格（回补后填充）
}
```

### 4.3 派生变量

```python
# 已卖出股数
total_sold_shares = sum(grid['sell_shares'] for grid in sold_grids)

# 剩余底仓
remaining_position = current_position - total_sold_shares

# 下一格卖出价
next_sell_price = calculate_next_sell_price(sold_grids, p_base)

# 下一格买入价（对应最低未回补的网格）
next_buy_price = calculate_next_buy_price(sold_grids)
```

---

## 五、示例交易流程

### 5.1 基础参数设置
```
初始资金：100,000 元
初始股价：10.00 元
初始底仓：50,000 元 = 5,000 股
U = 3%, D = 5%, Q = 10%
```

### 5.2 完整交易流程示例

#### Phase 1: 启动初始化（Day 1）
```
股价：10.00 元
P_base：10.00 元（收盘价）
底仓：5,000 股
现金：50,000 元
状态：等待卖出信号
```

#### Phase 2: 连续卖出（Day 5-6）
```
Day 5: 股价反弹到 10.35 元
├── 计算第 1 格卖出价：10.00 × 1.03 = 10.30 元
├── 检查条件：
│   ✅ 10.35 ≥ 10.30（价格达标）
│   ✅ 5000 - 500 = 4500 ≥ 2500（底仓保护）
├── 执行：卖出 500 股 @ 10.35 元
├── 持仓：5000 → 4500 股
├── 现金：50,000 + 5,175 = 55,175 元
└── 记录第 1 格：sell=10.35, buy=9.83, shares=500

Day 6: 股价继续反弹到 10.68 元
├── 计算第 2 格卖出价：10.35 × 1.03 = 10.66 元
├── 检查条件：
│   ✅ 10.68 ≥ 10.66（价格达标）
│   ✅ 4500 - 500 = 4000 ≥ 2500（底仓保护）
├── 执行：卖出 500 股 @ 10.68 元
├── 持仓：4500 → 4000 股
├── 现金：55,175 + 5,340 = 60,515 元
└── 记录第 2 格：sell=10.68, buy=10.15, shares=500
```

#### Phase 3: 连续回补（Day 8-10）
```
Day 8: 股价回落到 10.10 元
├── 检查第 2 格买入：10.10 ≤ 10.15 ✅
├── 执行：买入 500 股 @ 10.10 元
├── 持仓：4000 → 4500 股
├── 现金：60,515 - 5,050 = 55,465 元
├── 第 2 格收益：(10.68 - 10.10) × 500 = 290 元
└── 记录第 2 格：filled=True, profit=290

Day 10: 股价继续回落到 9.80 元
├── 检查第 1 格买入：9.80 ≤ 9.83 ✅
├── 执行：买入 500 股 @ 9.80 元
├── 持仓：4500 → 5000 股（完全回补！）
├── 现金：55,465 - 4,900 = 50,565 元
├── 第 1 格收益：(10.35 - 9.80) × 500 = 275 元
└── 第 1 轮完成，总收益：290 + 275 = 565 元
```

#### Phase 4: 基准价更新（Day 11）
```
Day 11: 盘中低点 9.75 元
├── 检查基准价下移：9.75 < 10.00 × 0.98 = 9.80 ✅
├── 更新 P_base = 9.75 元
├── 新卖出价：9.75 × 1.03 = 10.04 元
└── 网格重新定位到下降通道
```

### 5.3 交易记录明细表

| 日期 | 操作 | 价格 | 股数 | 现金变化 | 持仓 | 累计收益 |
|------|------|------|------|----------|------|----------|
| Day 1 | - | 10.00 | 5,000 | 50,000 | 5,000 | 0 |
| Day 5 | **卖出** | 10.35 | 500 | +5,175 | 4,500 | 0 |
| Day 6 | **卖出** | 10.68 | 500 | +5,340 | 4,000 | 0 |
| Day 8 | **买入** | 10.10 | 500 | -5,050 | 4,500 | 290 |
| Day 10 | **买入** | 9.80 | 500 | -4,900 | 5,000 | 565 |
| ... | ... | ... | ... | ... | ... | ... |

---

## 六、代码实现要点

### 6.1 类结构设计

```python
class TrailingBearishGrid(BaseStrategy):
    """
    Trailing-Bearish-Grid: 动态基准空头网格策略
    
    核心机制：
    1. 基准价动态下移，跟随下降通道
    2. 连续网格卖出，基于上一次卖出价计算
    3. 底仓保护，剩余持仓不低于初始 50%
    4. 闭环回补，锁定每轮收益
    """
    
    # 参数定义
    params = (
        ('initial_position_ratio', 0.5),    # 初始底仓比例
        ('grid_up_ratio', 0.03),            # 网格卖出间距 U%
        ('grid_down_ratio', 0.05),          # 网格买入间距 D%
        ('grid_sell_ratio', 0.1),           # 每格卖出比例 Q%
        ('base_shift_threshold', 0.02),     # 基准价下移阈值
        ('min_position_ratio', 0.5),        # 底仓保护线
        ('max_grid_count', 5),              # 最大网格数
    )
```

### 6.2 核心方法实现

#### 6.2.1 初始化方法
```python
def __init__(self, data_provider, factor_calculator, **kwargs):
    super().__init__(data_provider, factor_calculator, **kwargs)
    
    # 计算初始底仓
    initial_value = self.broker.getvalue()
    initial_capital = initial_value * self.params.initial_position_ratio
    self.initial_shares = int(initial_capital / self.data.close[0])
    
    # 初始化状态
    self.current_position = self.initial_shares
    self.p_base = self.data.close[0]
    self.sold_grids = []
    self.round_count = 0
    self.total_profit = 0
```

#### 6.2.2 基准价更新方法
```python
def update_base_price(self):
    """每日收盘后更新基准价"""
    today_low = self.data.low[0]
    threshold = self.p_base * (1 - self.params.base_shift_threshold)
    
    if today_low < threshold:
        self.p_base = today_low
        logger.info(f"[P_BASE] 基准价下移至 {self.p_base:.2f}")
```

#### 6.2.3 卖出检查方法
```python
def check_sell_signals(self):
    """检查连续卖出条件"""
    current_price = self.data.close[0]
    
    # 计算下一格卖出价
    if len(self.sold_grids) == 0:
        next_sell_price = self.p_base * (1 + self.params.grid_up_ratio)
    else:
        last_grid = self.sold_grids[-1]
        next_sell_price = last_grid['sell_price'] * (1 + self.params.grid_up_ratio)
    
    # 检查卖出触发
    if current_price < next_sell_price:
        return False, None
    
    # 检查底仓保护
    total_sold = sum(g['sell_shares'] for g in self.sold_grids)
    remaining = self.current_position - total_sold
    min_allowed = int(self.initial_shares * self.params.min_position_ratio)
    
    if remaining <= min_allowed:
        logger.warning("[SELL] 底仓不足，暂停卖出")
        return False, None
    
    # 检查最大网格数
    if len(self.sold_grids) >= self.params.max_grid_count:
        logger.warning("[SELL] 已达最大网格数")
        return False, None
    
    # 计算卖出数量
    sell_shares = int(self.initial_shares * self.params.grid_sell_ratio)
    actual_shares = min(sell_shares, remaining - min_allowed)
    
    if actual_shares <= 0:
        return False, None
    
    return True, {
        'sell_price': next_sell_price,
        'sell_shares': actual_shares,
        'buy_price': next_sell_price * (1 - self.params.grid_down_ratio)
    }
```

#### 6.2.4 买入检查方法
```python
def check_buy_signals(self):
    """检查连续买入条件"""
    current_price = self.data.close[0]
    
    # 按卖出价从高到低检查
    unsold_grids = [g for g in self.sold_grids if not g['filled']]
    unsold_grids.sort(key=lambda x: x['sell_price'], reverse=True)
    
    for grid in unsold_grids:
        if current_price <= grid['buy_price']:
            # 检查现金充足
            required_cash = grid['sell_shares'] * current_price
            if self.broker.get_cash() < required_cash:
                logger.warning(f"[BUY] 现金不足，需要 {required_cash:.2f}")
                continue
            
            return True, grid
    
    return False, None
```

#### 6.2.5 闭环完成方法
```python
def close_grid_round(self, grid):
    """完成一轮网格交易"""
    # 标记已回补
    grid['filled'] = True
    grid['buy_price_actual'] = self.data.close[0]
    
    # 计算收益
    profit = (grid['sell_price'] - grid['buy_price_actual']) * grid['sell_shares']
    self.total_profit += profit
    
    # 检查是否所有网格都已回补
    if all(g['filled'] for g in self.sold_grids):
        self.round_count += 1
        logger.info(f"[ROUND] 第 {self.round_count} 轮完成，本轮收益 {profit:.2f} 元")
        # 重置网格
        self.sold_grids = []
```

### 6.3 主循环实现

```python
def next(self):
    """主交易循环"""
    # 1. 基准价更新（每日收盘后）
    self.update_base_price()
    
    # 2. 检查买入条件（优先回补）
    buy_signal, buy_grid = self.check_buy_signals()
    if buy_signal:
        self.execute_buy(buy_grid)
        self.close_grid_round(buy_grid)
        return
    
    # 3. 检查卖出条件
    sell_signal, sell_info = self.check_sell_signals()
    if sell_signal:
        self.execute_sell(sell_info)
        return
    
    # 4. 记录状态
    self.log_grid_status()
```

### 6.4 日志记录实现

```python
def log_grid_status(self):
    """记录网格状态"""
    logger.info(f"""
    [GRID STATUS]
    P_base: {self.p_base:.2f}
    Position: {self.current_position} shares
    Sold Grids: {len(self.sold_grids)}
    Total Profit: {self.total_profit:.2f}
    Round Count: {self.round_count}
    """)
```

---

## 七、风险控制说明

### 7.1 底仓保护机制
- 剩余持仓始终不低于初始底仓的 50%
- 防止过度卖出导致"卖飞"
- 确保长期持有基础

### 7.2 现金保护机制
- 买入前检查现金是否充足
- 避免因资金不足导致回补失败
- 防止强制平仓

### 7.3 异常行情保护
- 单日大幅波动时暂停交易
- 触发极端止损线时强制平仓
- 防止在异常行情中亏损扩大

### 7.4 网格数量限制
- 设置最大网格数（如 5 格）
- 防止在单边行情中过度暴露
- 控制最大亏损敞口

---

## 八、参数调优建议

### 8.1 保守配置（低风险）
```python
grid_up_ratio = 0.04      # 4% 卖出间距
grid_down_ratio = 0.06    # 6% 买入间距
grid_sell_ratio = 0.08    # 8% 每格
max_grid_count = 3        # 最多 3 格
```

### 8.2 平衡配置（推荐）
```python
grid_up_ratio = 0.03      # 3% 卖出间距
grid_down_ratio = 0.05    # 5% 买入间距
grid_sell_ratio = 0.10    # 10% 每格
max_grid_count = 5        # 最多 5 格
```

### 8.3 激进配置（高收益）
```python
grid_up_ratio = 0.02      # 2% 卖出间距
grid_down_ratio = 0.04    # 4% 买入间距
grid_sell_ratio = 0.12    # 12% 每格
max_grid_count = 7        # 最多 7 格
```

---

## 九、注意事项

### 9.1 适用前提
- 必须在下降通道中使用
- 需要股价有足够的波动性
- 长期持有才能体现价值

### 9.2 潜在风险
- 单边下跌可能导致止损
- 震荡市中收益有限
- 强势反弹中可能踏空

### 9.3 使用建议
- 先在模拟盘测试
- 选择波动较大的股票
- 定期检查策略表现
- 根据市场调整参数

---

**文档版本**：v1.0  
**创建日期**：2026-06-21  
**适用框架**：backtrader