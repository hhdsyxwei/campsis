# 测试模块导入
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('.'))

print("Python路径:", sys.path)
print("当前目录:", os.getcwd())

# 测试导入
print("\n测试导入 Ingredient...")
try:
    from Ingredient.DataNest import create_database_and_tables
    print("[OK] 成功导入 Ingredient.DataNest")
except Exception as e:
    print("[ERROR] 导入失败:", e)

print("\n测试导入 CookingEngine...")
try:
    from CookingEngine.Picker import HarvestDataProvider
    print("[OK] 成功导入 CookingEngine.Picker")
except Exception as e:
    print("[ERROR] 导入失败:", e)

print("\n测试导入 KitchenBase...")
try:
    from KitchenBase.logger_config import setup_logging
    print("[OK] 成功导入 KitchenBase.logger_config")
except Exception as e:
    print("[ERROR] 导入失败:", e)
