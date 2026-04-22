# common.py
# 通用工具函数

from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


def format_pointer_info(pointer_fields, block_identifier):
    """
    格式化指针信息为友好的字符串
    
    Args:
        pointer_fields: 指针字段元组
        block_identifier: 区块标识元组
        
    Returns:
        str: 格式化后的指针信息
    """
    if not block_identifier:
        return "None"
    
    # 确保字段元组和指针元组长度一致
    if len(pointer_fields) != len(block_identifier):
        # 使用默认字段名
        pointer_dict = {f"field_{i}": value for i, value in enumerate(block_identifier)}
    else:
        # 构建字段到值的映射
        pointer_dict = dict(zip(pointer_fields, block_identifier))
    
    # 构建友好的日志消息
    return ", ".join([f"{k}={v}" for k, v in pointer_dict.items()])


def calculate_percentage(part, total):
    """
    计算百分比
    
    Args:
        part: 部分值
        total: 总值
        
    Returns:
        float: 百分比
    """
    if total == 0:
        return 0.0
    return (part / total) * 100