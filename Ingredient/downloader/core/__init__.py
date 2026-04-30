# core/__init__.py
# 核心模块初始化文件

from KitchenBase import DownloadParameters
from .abstract_downloader import SimpleDownloader, BlockDownloader
from .download_strategy import DownloadStrategy
from .abs_block_manager import BlockManager
from .abs_status_manager import TaskStatusManager
from .abs_pointer_manager import PointerManager
from .abs_progress_manager import ProgressManager
from .abs_collection_manager import StockCollectionManager



__all__ = [
    "SimpleDownloader",
    "BlockDownloader",
    "DownloadStrategy",
    "BlockManager",
    "TaskStatusManager",
    "PointerManager",
    "ProgressManager",
    "DownloadParameters"
]