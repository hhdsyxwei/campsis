#logger_config.py
import logging
import logging.handlers
import os
import sys
from typing import Optional, Dict, List
from datetime import datetime


class CampsisLogger:
    """
    终极日志配置（支持包/模块级级别控制，对齐Java日志框架）
    ✅ 控制台按级别彩色输出
    ✅ 模块名固定宽度 + 自动省略超长部分
    ✅ 日志按日期自动分割
    ✅ 单例模式，全局只初始化一次
    ✅ 开发/生产环境切换
    ✅ 【新增】包/模块级日志级别控制（如 KitchenBase=INFO, KitchenBase.package_manager=DEBUG）
    """
    _instance = None
    _initialized = False

    # ====================== 核心新增：包/模块级级别配置（对齐Java） ======================
    # 格式：{包/模块名: 日志级别}，支持层级继承（如 KitchenBase 控制所有子模块）
    # 优先级：精确匹配 > 父级匹配 > 默认级别
    LOG_LEVEL_CONFIG: Dict[str, int] = {
        # 包级别控制（如 KitchenBase 所有子模块默认 INFO）
        "KitchenBase": logging.ERROR,
        "Ingredient": logging.CRITICAL + 1,
        # 模块级别控制（覆盖父级，PackageManager 模块单独设为 DEBUG）
        "KitchenBase.package_manager": logging.DEBUG,

        #暂时关闭Picker模块志输出
        "CookingEngine.Picker": logging.DEBUG,
        "Ingredient.downloader.TradeDateMapDownloader": logging.DEBUG,
        # 测试包单独控制
        "tests": logging.ERROR,
        # 第三方包控制（如屏蔽 pandas 日志）
        "pandas": logging.CRITICAL + 1,
        # 默认级别（未匹配的所有模块）
        "": logging.DEBUG if os.getenv("CAMPSIS_ENV", "dev") == "dev" else logging.INFO
    }

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

    # ====================== 核心新增：层级匹配日志级别（对齐Java逻辑） ======================
    def _get_level_for_name(self, name: str) -> int:
        """
        按包/模块名层级匹配级别（如 KitchenBase.package_manager → 先匹配精确名，再匹配 KitchenBase，最后默认）
        :param name: Logger名称（包/模块/类名）
        :return: 匹配到的日志级别
        """
        # 1. 精确匹配（如 KitchenBase.package_manager.PackageManager）
        if name in self.LOG_LEVEL_CONFIG:
            return self.LOG_LEVEL_CONFIG[name]
        
        # 2. 层级匹配父包（如 KitchenBase.package_manager → 匹配 KitchenBase）
        parts = name.split(".")
        for i in range(len(parts)-1, 0, -1):
            parent_name = ".".join(parts[:i])
            if parent_name in self.LOG_LEVEL_CONFIG:
                return self.LOG_LEVEL_CONFIG[parent_name]
        
        # 3. 使用默认级别
        return self.LOG_LEVEL_CONFIG[""]

    # ====================== 新增：批量应用包/模块级级别配置 ======================
    def _apply_module_levels(self):
        """遍历所有已存在的Logger，应用级别配置；同时监听新Logger的创建"""
        # 1. 为已存在的Logger设置级别
        for logger_name in logging.Logger.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            logger.setLevel(self._get_level_for_name(logger_name))
        
        # 2. 重写Logger的getLogger方法，确保新创建的Logger自动应用级别
        original_getLogger = logging.getLogger
        def wrapped_getLogger(name: Optional[str] = None):
            logger = original_getLogger(name)
            if name:  # 根Logger（name=None）使用默认级别
                logger.setLevel(self._get_level_for_name(name))
            return logger
        logging.getLogger = wrapped_getLogger

    def setup(self):
        if hasattr(self, '_setup_done'):
            return
        self._setup_done = True

        self._create_log_dir()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        # 根Logger设为最低级别（让子模块级别控制生效）
        root_logger.setLevel(logging.DEBUG)

        # 控制台彩色日志
        console_handler = logging.StreamHandler()
        # 控制台Handler设为最低级别（子模块级别过滤日志）
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(self._get_colored_formatter())
        root_logger.addHandler(console_handler)

        # 日志文件配置
        log_file = os.path.join(self._log_dir, "campsis.log")
        daily_file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_file,
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

        # ====================== 关键：应用包/模块级级别配置 ======================
        self._apply_module_levels()

        logging.getLogger(__name__).info("✅ Campsis 日志系统初始化完成（支持包/模块级级别控制）")

    # ====================== 新增：动态修改包/模块级别（运行时生效） ======================
    def set_module_level(self, module_name: str, level: int) -> None:
        """
        动态设置包/模块的日志级别（对齐Java的 LoggerContext 修改级别）
        :param module_name: 包/模块名（如 "KitchenBase"、"KitchenBase.package_manager"）
        :param level: 日志级别（logging.DEBUG/INFO等）
        """
        self.LOG_LEVEL_CONFIG[module_name] = level
        # 立即应用到已存在的Logger
        logger = logging.getLogger(module_name)
        logger.setLevel(level)
        # 递归应用到子模块（如修改 KitchenBase → 所有 KitchenBase.xxx 都生效，除非有精确配置）
        for logger_name in logging.Logger.manager.loggerDict:
            if logger_name.startswith(f"{module_name}.") and logger_name not in self.LOG_LEVEL_CONFIG:
                logging.getLogger(logger_name).setLevel(level)
        logging.getLogger(__name__).info(f"🔧 已设置 {module_name} 日志级别为 {logging.getLevelName(level)}")


# ==========================
# 标准稳定接口
# ==========================
def setup_logging():
    CampsisLogger().setup()

def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or __name__)

# ==========================
# 便捷工具函数（对齐Java日志配置习惯）
# ==========================
def set_log_level(module_name: str, level_str: str) -> None:
    """
    按字符串设置级别（更贴近Java配置方式，如 "DEBUG"/"INFO"）
    :param module_name: 包/模块名
    :param level_str: 级别字符串（DEBUG/INFO/WARNING/ERROR/CRITICAL）
    """
    level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "OFF": logging.CRITICAL + 1  # 完全屏蔽，对齐Java的 OFF 级别
    }
    level = level_mapping.get(level_str.upper(), logging.INFO)
    CampsisLogger().set_module_level(module_name, level)