# block_download_strategy.py
# 区块下载策略

from KitchenBase import DownloadParameters
from ..core.abstract_downloader import BlockDownloader
from ..core.download_strategy import DownloadStrategy
from KitchenBase.download_enums import DlTaskStatus
from KitchenBase.logger_config import get_logger
from pandas import DataFrame as pdDataFrame

# ===================== 全局日志记录器 =====================
logger = get_logger(__name__)

class BlockDownloadStrategy(DownloadStrategy):
    """
    区块下载策略，实现区块下载逻辑
    """
    
    def __init__(self, downloader: BlockDownloader):
        """
        初始化区块下载策略
        
        Args:
            downloader: 下载器实例
        """
        self.downloader = downloader
        self.logger = logger
    
    def execute(self, params: DownloadParameters, **kwargs) -> bool:
        """
        执行区块下载策略
        
        Args:
            params: 下载参数
            **kwargs: 额外参数
            
        Returns:
            bool: 下载是否成功
        """
        self.logger.debug(f"[BlockDownloadStrategy.execute] 方法开始执行 | params: {params}")
        
        download_type = kwargs.get("download_type", "block_resume")
        self.logger.debug(f"[BlockDownloadStrategy.execute] download_type: {download_type}")
        
        # 获取任务类型标识
        task_type = self.downloader.get_task_type()
        task_identifier = f"[{task_type.value}]"
        self.logger.debug(f"[BlockDownloadStrategy.execute] task_type: {task_type}")
        
        if download_type == "block_new":
            # 清空之前的下载进度
            self.downloader.status_manager.set_task_status(task_type, DlTaskStatus.NOT_STARTED)
            self.downloader.pointer_manager.clear_dl_pointer()
            self.logger.info(f"[{self.downloader.get_task_type().value}] 已清空之前的下载进度")
        
        # 检查下载状态
        status = self.downloader.status_manager.get_task_status(task_type)
        self.logger.debug(f"[BlockDownloadStrategy.execute] 当前任务状态: {status}")
        
        if status == DlTaskStatus.COMPLETED:
            self.logger.info(f"{task_identifier} 下载已完成，无需重复执行")
            return True
        elif status == DlTaskStatus.IN_PROGRESS:
            self.logger.info(f"{task_identifier} 下载正在进行，将从断点恢复")
        else:
            self.logger.info(f"{task_identifier} 下载未开始，将从头开始")
            self.downloader.status_manager.set_task_status(task_type, DlTaskStatus.IN_PROGRESS)
        
        # 计算总区块数
        self.logger.debug(f"[BlockDownloadStrategy.execute] 开始计算总区块数 | start_year: {params.start_year}, end_year: {params.end_year}")
        total_blocks = self.downloader.block_manager.get_total_block_count(params, **kwargs)
        self.logger.debug(f"[BlockDownloadStrategy.execute] 总区块数计算完成: {total_blocks}")
        self.logger.info(f"{task_identifier} 总区块数: {total_blocks} (年份范围: {params.start_year}-{params.end_year-1})")

        if total_blocks <= 0:
            self.logger.info(f"{task_identifier} 无数据可下载")
            return True
        
        # 获取下一个下载区块
        self.logger.debug(f"[BlockDownloadStrategy.execute] 获取当前下载指针")
        next_block = self.downloader.pointer_manager.get_dl_pointer()
        self.logger.debug(f"[BlockDownloadStrategy.execute] 当前下载指针: {next_block}")
        
        if not next_block or not self.downloader.pointer_manager.is_dl_pointer_valid(next_block, params):
            next_block = self.downloader.pointer_manager.get_first_blk_pointer(params)
            self.logger.info(f"{task_identifier} 下载指针无效或不存在，使用第一个区块: {next_block}")
        else:
            self.logger.info(f"{task_identifier} 启动后：第一个下载区块: {next_block}")
        
        # 核心下载循环
        completed_blocks = 0
        skipped_blocks = 0
        loop_count = 0
        self.logger.debug(f"[BlockDownloadStrategy.execute] 进入下载循环 | next_block: {next_block}, total_blocks: {total_blocks}")
        
        while next_block and completed_blocks + skipped_blocks < total_blocks:
            loop_count += 1
            self.logger.debug(f"[BlockDownloadStrategy.execute] 循环第 {loop_count} 次 | next_block: {next_block}, completed: {completed_blocks}, skipped: {skipped_blocks}, total: {total_blocks}")
            
            try:
                # 设置下载指针
                self.logger.debug(f"[BlockDownloadStrategy.execute] 设置下载指针: {next_block}")
                self.downloader.pointer_manager.set_dl_pointer(next_block)
                
                # 下载区块
                self.logger.debug(f"[BlockDownloadStrategy.execute] 开始下载区块: {next_block}")
                self.downloader.download_block(next_block, params)
                self.logger.debug(f"[BlockDownloadStrategy.execute] 区块下载完成: {next_block}")

                # 记录进度
                completed_blocks = self.downloader.block_manager.get_completed_block_count(params)
                skipped_blocks = self.downloader.block_manager.get_skipped_block_count(params)
                self.logger.debug(f"[BlockDownloadStrategy.execute] 进度统计 | completed: {completed_blocks}, skipped: {skipped_blocks}")
                
                if total_blocks > 0:
                    progress = self.downloader.progress_calculator.calculate_progress(completed_blocks, skipped_blocks, total_blocks)
                    self.logger.info(f"{task_identifier} 下载进度: {progress:.2f}% ({completed_blocks + skipped_blocks}/{total_blocks}) | 当前区块: {next_block}")

                # 获取下一个区块
                next_block = self.downloader.pointer_manager.get_next_blk_pointer(params, next_block)
                self.logger.debug(f"[BlockDownloadStrategy.execute] 获取下一个区块: {next_block}")
                
            except Exception as e:
                self.logger.error(f"{task_identifier} 下载失败: {str(e)} | 当前区块: {next_block}")
                import traceback
                self.logger.error(f"{task_identifier} 异常堆栈: {traceback.format_exc()}")
                return False

        self.logger.debug(f"[BlockDownloadStrategy.execute] 循环结束 | loop_count: {loop_count}")
        
        # 下载完成
        self.downloader.status_manager.set_task_status(task_type, DlTaskStatus.COMPLETED)
        self.downloader.pointer_manager.clear_dl_pointer()
        self.logger.info(f"{task_identifier} 全部下载完成，已清空下载指针")
        
        # 调用全部区块下载完成钩子
        self.downloader.on_download_completed(params, pdDataFrame(), success=True)
        
        self.logger.debug(f"[BlockDownloadStrategy.execute] 方法执行完成，返回 True")
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