# downloader/__init__.py
# 下载器包初始化文件

from .core.abstract_downloader import SimpleDownloader, BlockDownloader

__all__ = [
    "SimpleDownloader",
    "BlockDownloader"
]
