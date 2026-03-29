import os
import subprocess
import sys
import pkgutil
from typing import List, Set
from KitchenBase.logger_config import get_logger
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
        修复：包含 tests 目录，不排除 test_ 开头的文件
        """
        imported_packages = set()
        # 获取当前环境已安装的所有包（转小写避免大小写问题）
        installed_packages = {pkg.name.lower() for pkg in pkgutil.iter_modules()}

        # 扫描项目所有 .py 文件（包含 tests 目录，不排除 test_ 开头的文件）
        for root, _, files in os.walk(project_path):
            # 保留所有目录（包括 tests），仅排除无用的编译目录
            if "__pycache__" in root:
                continue
            for file in files:
                # 只过滤 .pyc 等非源码文件，不再排除 test_ 开头的文件
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                # 匹配 import/from 语句，提取顶层包名
                                if line.startswith("import ") or line.startswith("from "):
                                    # 处理多行导入（如 from xxx import yyy as zzz）
                                    line = line.split("#")[0]  # 去掉注释
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        # 提取顶层包名（如 from pandas.core import xxx → pandas）
                                        pkg = parts[1].split(".")[0]
                                        if pkg.isidentifier() and not pkg.startswith("_"):
                                            imported_packages.add(pkg.lower())
                    except UnicodeDecodeError:
                        logger.warning(f"文件编码错误 {file_path}: 跳过（非UTF-8编码）")
                    except Exception as e:
                        logger.warning(f"读取文件失败 {file_path}: {str(e)}")
                        continue

        logger.debug(f"扫描到的导入包: {imported_packages}")
        logger.debug(f"已安装的包: {installed_packages}")

        # ====================== 精简版内置标准库过滤（仅保留Python官方内置库） ======================
        # 移除自定义模块（如 utils/config），避免误过滤
        BUILTIN_MODULES = {
            "sys", "os", "time", "datetime", "json", "re", "math",
            "typing", "logging", "configparser", "subprocess", "pkgutil",
            "importlib", "abc", "enum", "pathlib", "shutil", "random",
            "threading", "queue", "io", "base64", "hashlib", "functools",
            "builtins", "traceback", "warnings", "string", "collections",
            "argparse", "socket", "csv", "tempfile", "enum", "datetime",
            "unittest"  # 加入unittest（Python内置测试库），避免被误判为缺失
        }

        # 过滤逻辑：只保留「非内置库 + 未安装」的第三方包
        missing = [
            pkg for pkg in imported_packages
            if pkg not in installed_packages
            and pkg not in BUILTIN_MODULES
            # 排除项目内部模块（根据你的项目结构调整，如 kitchenbase/ingredient）
            and pkg not in {"kitchenbase", "ingredient"}
        ]
        # 去重并排序，保证结果稳定
        return sorted(list(set(missing)))

    @staticmethod
    def install_missing_requirements() -> bool:
        """
        【一键自动安装所有缺失依赖】
        扫描 → 获取缺失 → 自动安装
        """
        project_path = get_project_root()
        logger.debug(f"🔍 项目根目录: {project_path}")

        logger.info("🔍 正在扫描项目缺失依赖（包含tests目录）...")
        missing = PackageManager.generate_requirements(project_path)
        logger.debug(f"🔍 扫描完成，缺失依赖列表: {missing}")

        if not missing:
            logger.info("✅ 所有依赖已安装，无需操作")
            return True

        logger.info(f"📦 发现缺失依赖: {', '.join(missing)}")
        return PackageManager.pip_install_packages(missing)