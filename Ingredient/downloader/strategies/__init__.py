# strategies/__init__.py
# 策略模块初始化文件

from .simple_download_strategy import SimpleDownloadStrategy
from .block_download_strategy import BlockDownloadStrategy

__all__ = [
    "SimpleDownloadStrategy",
    "BlockDownloadStrategy"
]