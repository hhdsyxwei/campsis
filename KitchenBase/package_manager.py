import os
import subprocess
import sys
import pkgutil
from typing import List, Set
from logger_config import get_logger
from KitchenBase.download_utils import get_project_root

logger = get_logger(__name__)


class PackageManager:
    """
    KitchenBase 基础工具层 - 项目包管理类
    功能：自动扫描缺失依赖 → 直接安装缺失依赖
    """

    @staticmethod
    def pip_install_packages(
        packages: List[str],
        upgrade: bool = False,
        quiet: bool = True,
        timeout: int = 60
    ) -> bool:
        """
        通过 pip 安装指定包列表
        :param packages: 包列表，如 ["pytest>=7.0", "pandas"]
        """
        if not packages:
            logger.info("✅ 无需要安装的包")
            return True

        cmd = [sys.executable, "-m", "pip", "install"]

        if upgrade:
            cmd.append("--upgrade")
        if quiet:
            cmd.append("-q")

        cmd.extend(["--timeout", str(timeout)])
        cmd.extend(packages)

        try:
            logger.debug(f"开始执行pip安装: {' '.join(packages)}")
            subprocess.run(
                cmd, check=True, capture_output=True, text=True, encoding="utf-8"
            )
            logger.info(f"✅ 安装成功: {', '.join(packages)}")
            return True

        except subprocess.CalledProcessError as e:
            err_msg = f"❌ 安装失败: {e.stderr.strip()}"
            logger.error(err_msg)
            return False

        except Exception as e:
            err_msg = f"❌ 执行异常: {str(e)}"
            logger.error(err_msg)
            return False

    @staticmethod
    def generate_requirements(project_path: str = "./") -> List[str]:
        """
        【不生成文件！】
        扫描项目代码 import，返回【缺失/未安装】的依赖包列表
        """
        imported_packages = set()
        installed_packages = {pkg.name.lower() for pkg in pkgutil.iter_modules()}

        # 扫描项目所有 .py 文件
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith(".py") and not file.startswith("test_"):
                    try:
                        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith("import ") or line.startswith("from "):
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        pkg = parts[1].split(".")[0]
                                        if pkg.isidentifier() and not pkg.startswith("_"):
                                            imported_packages.add(pkg.lower())
                    except Exception as e:
                        logger.warning(f"读取文件失败 {file}: {str(e)}")
                        continue

        # ====================== 【完整版】内置标准库过滤 ======================
        BUILTIN_MODULES = {
            "sys", "os", "time", "datetime", "json", "re", "math",
            "typing", "logging", "configparser", "subprocess", "pkgutil",
            "importlib", "abc", "enum", "pathlib", "shutil", "random",
            "threading", "queue", "io", "base64", "hashlib", "functools",
            "__main__", "utils", "config", "logger_config", "builtins",
            "traceback", "warnings", "string", "collections", "argparse"
        }

        # 过滤：只保留未安装的第三方包
        missing = [
            pkg for pkg in imported_packages
            if pkg not in installed_packages
            and pkg not in BUILTIN_MODULES
        ]
        return sorted(list(set(missing)))

    @staticmethod
    def install_missing_requirements() -> bool:
        """
        【一键自动安装所有缺失依赖】
        扫描 → 获取缺失 → 自动安装
        """
        project_path = get_project_root()
        logger.debug(f"🔍 项目根目录: {project_path}")

        logger.info("🔍 正在扫描项目缺失依赖...")
        missing = PackageManager.generate_requirements(project_path)
        logger.debug(f"🔍 扫描完成，缺失依赖列表: {missing}")

        if not missing:
            logger.info("✅ 所有依赖已安装，无需操作")
            return True

        logger.info(f"📦 发现缺失依赖: {', '.join(missing)}")
        return PackageManager.pip_install_packages(missing)