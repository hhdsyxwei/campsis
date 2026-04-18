# block_download_strategy.py
# 区块下载策略

from ..core.download_strategy import DownloadStrategy
from KitchenBase.download_enums import DlTaskStatus

class BlockDownloadStrategy(DownloadStrategy):
    """
    区块下载策略，实现区块下载逻辑
    """
    
    def __init__(self, downloader):
        """
        初始化区块下载策略
        
        Args:
            downloader: 下载器实例
        """
        self.downloader = downloader
    
    def execute(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        执行区块下载策略
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            bool: 下载是否成功
        """
        download_type = kwargs.get("download_type", "block_resume")
        
        if download_type == "block_new":
            # 清空之前的下载进度
            self.downloader.status_manager.set_download_status(DlTaskStatus.NOT_STARTED)
            self.downloader.pointer_manager.clear_dl_pointer()
            self.downloader.logger.info(f"[{self.downloader.get_task_type().value}] 已清空之前的下载进度")
        
        # 获取任务类型标识
        task_type = self.downloader.get_task_type()
        task_identifier = f"[{task_type.value}]"
        
        # 检查下载状态
        status = self.downloader.status_manager.get_download_status()
        if status == DlTaskStatus.COMPLETED:
            self.downloader.logger.info(f"{task_identifier} 下载已完成，无需重复执行")
            return True
        elif status == DlTaskStatus.IN_PROGRESS:
            self.downloader.logger.info(f"{task_identifier} 下载正在进行，将从断点恢复")
        else:
            self.downloader.logger.info(f"{task_identifier} 下载未开始，将从头开始")
            self.downloader.status_manager.set_download_status(DlTaskStatus.IN_PROGRESS)
        
        # 计算总区块数
        total_blocks = self.downloader.block_manager.get_total_block_count(start_year, end_year, **kwargs)
        self.downloader.logger.info(f"{task_identifier} 总区块数: {total_blocks} (年份范围: {start_year}-{end_year-1})")
        
        # 获取下一个下载区块
        next_block = self.downloader.pointer_manager.get_dl_pointer()
        if not next_block or not self.downloader.pointer_manager.is_dl_pointer_valid(next_block, start_year, end_year):
            next_block = self.downloader.pointer_manager.get_first_blk_pointer(start_year, end_year)
            self.downloader.logger.info(f"{task_identifier} 下载指针无效或不存在，使用第一个区块: {next_block}")
        else:
            self.downloader.logger.info(f"{task_identifier} 启动后：第一个下载区块: {next_block}")
        
        # 核心下载循环
        while next_block:
            try:
                # 设置下载指针
                self.downloader.pointer_manager.set_dl_pointer(next_block)
                
                # 下载区块
                self.downloader.download_block(*next_block)

                # 记录进度
                completed_blocks = self.downloader.block_manager.get_completed_block_count(start_year, end_year)
                skipped_blocks = self.downloader.block_manager.get_skipped_block_count(start_year, end_year)
                if total_blocks > 0:
                    progress = self.downloader.progress_calculator.calculate_progress(completed_blocks, skipped_blocks, total_blocks)
                    self.downloader.logger.info(f"{task_identifier} 下载进度: {progress:.2f}% ({completed_blocks + skipped_blocks}/{total_blocks}) | 当前区块: {next_block}")

                # 获取下一个区块
                next_block = self.downloader.pointer_manager.get_next_blk_pointer(start_year, end_year, next_block)
            except Exception as e:
                self.downloader.logger.error(f"{task_identifier} 下载失败: {str(e)} | 当前区块: {next_block}")
                return False

        # 下载完成
        self.downloader.status_manager.set_download_status(DlTaskStatus.COMPLETED)
        self.downloader.pointer_manager.clear_dl_pointer()
        self.downloader.logger.info(f"{task_identifier} 全部下载完成，已清空下载指针")
        return True
    
    def can_handle(self, download_type: str) -> bool:
        """
        判断是否能处理指定类型的下载
        
        Args:
            download_type: 下载类型
            
        Returns:
            bool: 是否能处理
        """
        return download_type in ["block_new", "block_resume"]