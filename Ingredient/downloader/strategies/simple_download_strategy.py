# simple_download_strategy.py
# 一次性下载策略

from ..core.download_strategy import DownloadStrategy
from ..core.download_parameters import DownloadParameters

class SimpleDownloadStrategy(DownloadStrategy):
    """
    一次性下载策略，实现一次性下载逻辑
    """
    
    def __init__(self, downloader):
        """
        初始化一次性下载策略
        
        Args:
            downloader: 下载器实例
        """
        self.downloader = downloader
    
    def execute(self, params: DownloadParameters, **kwargs) -> bool:
        """
        执行一次性下载策略
        
        Args:
            params: 下载参数
            **kwargs: 额外参数
            
        Returns:
            bool: 下载是否成功
        """
        import time
        
        # 记录开始时间
        start_time = time.time()
        self.downloader.logger.info(f"[{self.downloader.get_task_type().value}] 开始下载任务，年份范围: {params.start_year}-{params.end_year}")
        
        # 验证参数
        if not self.downloader.validate_parameters(params, **kwargs):
            self.downloader.logger.info(f"[{self.downloader.get_task_type().value}] 参数验证失败")
            return False
        
        # 下载原始数据
        raw_data = self.downloader.download_raw_data(params, **kwargs)
        if raw_data is None:
            self.downloader.logger.info(f"[{self.downloader.get_task_type().value}] 原始数据下载失败")
            return False
        
        # 清洗数据
        cleaned_data = self.downloader.clean_data(raw_data)
        if cleaned_data.empty:
            self.downloader.logger.info(f"[{self.downloader.get_task_type().value}] 数据清洗后为空")
            return False
        
        # 保存数据
        save_result = self.downloader.save_data(cleaned_data, params, **kwargs)

        # 调用下载完成钩子
        self.downloader.on_download_completed(params, cleaned_data, success=save_result, **kwargs)

        # 记录结束时间和总耗时
        end_time = time.time()
        total_time = end_time - start_time
        self.downloader.logger.info(f"[{self.downloader.get_task_type().value}] 下载任务完成，耗时: {total_time:.2f}秒")

        return save_result
    
    def can_handle(self, download_type: str) -> bool:
        """
        判断是否能处理指定类型的下载
        
        Args:
            download_type: 下载类型
            
        Returns:
            bool: 是否能处理
        """
        return download_type == "simple"