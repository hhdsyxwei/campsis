# KitchenBase/logger_config.py
import logging
import logging.handlers
import os
import sys
from typing import Optional
from datetime import datetime


class CampsisLogger:
    """
    终极日志配置（单例版）
    ✅ 控制台按级别彩色输出
    ✅ 模块名固定宽度 + 自动省略超长部分
    ✅ 日志按日期自动分割
    ✅ 单例模式，全局只初始化一次
    ✅ 开发/生产环境切换
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if CampsisLogger._initialized:
            return

        # Windows 控制台颜色支持
        if sys.platform.startswith("win"):
            os.system("")

        self._root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._log_dir = os.path.join(self._root_dir, "logs")
        self._env = os.getenv("CAMPSIS_ENV", "dev")

        # ANSI 颜色
        self.RESET = "\033[0m"
        self.RED = "\033[91m"
        self.YELLOW = "\033[93m"
        self.GREEN = "\033[92m"
        self.GRAY = "\033[90m"
        self.BOLD = "\033[1m"

        CampsisLogger._initialized = True

    def _create_log_dir(self):
        os.makedirs(self._log_dir, exist_ok=True)

    def _format_module_name(self, name: str, max_len: int = 20) -> str:
        """
        格式化模块名：固定长度，左对齐，超长中间省略号
        例：KitchenBase.abc.def → KitchenBase...def
        """
        if len(name) <= max_len:
            return name.ljust(max_len)
        
        # 超长：保留开头 + ... + 结尾
        keep = max_len - 3
        left = keep // 2
        right = keep - left
        return f"{name[:left]}...{name[-right:]}"

    def _get_common_formatter(self):
        return logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-20s | %(lineno)4d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def _get_colored_formatter(self):
        class ColorFormatter(logging.Formatter):
            def __init__(self, outer):
                super().__init__(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(lineno)4d | %(message)s",
                    datefmt="%H:%M:%S"
                )
                self.outer = outer

            def format(self, record):
                outer = self.outer
                # 格式化模块名（固定长度 + 对齐 + 超长省略）
                record.name = outer._format_module_name(record.name, 20)
                
                # 日志级别颜色
                if record.levelno >= logging.ERROR:
                    color = outer.RED
                elif record.levelno == logging.WARNING:
                    color = outer.YELLOW
                elif record.levelno == logging.DEBUG:
                    color = outer.GRAY
                else:
                    color = ""

                log_msg = super().format(record)

                # 关键信息加粗
                if any(k in log_msg for k in ["成功", "完成", "启动", "初始化", "失败"]):
                    log_msg = f"{outer.BOLD}{log_msg}{outer.RESET}"

                return f"{color}{log_msg}{outer.RESET}" if color else log_msg

        return ColorFormatter(self)

    def setup(self):
        if hasattr(self, '_setup_done'):
            return
        self._setup_done = True

        self._create_log_dir()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.DEBUG if self._env == "dev" else logging.INFO)

        # 控制台彩色日志
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if self._env == "dev" else logging.INFO)
        console_handler.setFormatter(self._get_colored_formatter())
        root_logger.addHandler(console_handler)

        # ======================
        # ✅ 修复：日志文件始终带 .log
        # ======================
        log_file = os.path.join(self._log_dir, "campsis.log")

        daily_file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_file,  # 这里直接带 .log
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
            delay=True
        )
        daily_file_handler.suffix = "%Y-%m-%d.log"
        daily_file_handler.setFormatter(self._get_common_formatter())
        daily_file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(daily_file_handler)

        logging.getLogger(__name__).info("✅ Campsis 日志系统初始化完成")


# ==========================
# 标准稳定接口
# ==========================
def setup_logging():
    CampsisLogger().setup()

def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or __name__)