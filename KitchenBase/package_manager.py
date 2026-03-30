# KitchenBase/package_manager.py
import ast
import os
import subprocess
import sys
import pkgutil
import tokenize
import importlib.util
from typing import List, Set, Dict, Iterable

from KitchenBase.logger_config import get_logger
from KitchenBase.download_utils import get_project_root

logger = get_logger(__name__)

class PackageManager:
    """
    KitchenBase 基础工具层 - 项目包管理类（AST增强版）
    功能增强：
    1) AST 稳健提取 import
    2) import名 -> pip包名自动映射（cv2/yaml/bs4 等）
    3) 对“看起来已可导入”的模块进行二次校验，减少误报
    4) pip 安装前去重、排序、日志更清晰
    """

    # ===== 常见 import 名到 pip 发行名映射（可按项目持续扩充）=====
    IMPORT_TO_PIP_MAP: Dict[str, str] = {
        "cv2": "opencv-python",
        "yaml": "pyyaml",
        "PIL".lower(): "pillow",
        "bs4": "beautifulsoup4",
        "sklearn": "scikit-learn",
        "Crypto".lower(): "pycryptodome",
        "dateutil": "python-dateutil",
        "fitz": "pymupdf",
        "OpenSSL".lower(): "pyopenssl",
        "lxml": "lxml",
        "dns": "dnspython",
        "setuptools": "setuptools",
        "wheel": "wheel",
    }

    # 某些“import 名 != 分发名”的已知兜底（已安装分发名时视为满足）
    # 例如 import PIL 时，只要装了 pillow 就算满足
    IMPORT_SATISFY_BY_DIST: Dict[str, Set[str]] = {
        "pil": {"pillow"},
        "cv2": {"opencv-python", "opencv-contrib-python", "opencv-python-headless"},
        "yaml": {"pyyaml"},
        "bs4": {"beautifulsoup4"},
        "sklearn": {"scikit-learn"},
        "crypto": {"pycryptodome", "pycrypto"},
        "dateutil": {"python-dateutil"},
        "fitz": {"pymupdf"},
        "openssl": {"pyopenssl"},
        "dns": {"dnspython"},
    }

    # 内部模块（按项目实际情况维护）
    INTERNAL_MODULES = {"kitchenbase", "ingredient", "tests"}

    # 标准库（可扩充）
    BUILTIN_MODULES = {
        "sys", "os", "time", "datetime", "json", "re", "math",
        "typing", "logging", "configparser", "subprocess", "pkgutil",
        "importlib", "abc", "enum", "pathlib", "shutil", "random",
        "threading", "queue", "io", "base64", "hashlib", "functools",
        "builtins", "traceback", "warnings", "string", "collections",
        "argparse", "socket", "csv", "tempfile", "unittest", "tokenize",
        "ast", "itertools", "contextlib", "dataclasses", "typing_extensions"
    }

    @staticmethod
    def pip_install_packages(
        packages: List[str],
        upgrade: bool = False,
        quiet: bool = True,
        timeout: int = 120
    ) -> bool:
        if not packages:
            logger.info("✅ 无需要安装的包")
            return True

        # 去重+排序，保证稳定输出
        packages = sorted(set(packages))

        cmd = [sys.executable, "-m", "pip", "install"]
        if upgrade:
            cmd.append("--upgrade")
        if quiet:
            cmd.append("-q")
        cmd.extend(packages)

        logger.info(f"📦 准备安装依赖: {', '.join(packages)}")
        logger.debug(f"执行命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            logger.info("✅ 安装成功")
            if result.stdout.strip():
                logger.debug(result.stdout.strip())
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"❌ 安装超时（>{timeout}s）")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 安装失败: {(e.stderr or '').strip()}")
            return False
        except Exception as e:
            logger.error(f"❌ 执行异常: {str(e)}")
            return False

    @staticmethod
    def _read_source_with_fallback(file_path: str) -> str:
        with tokenize.open(file_path) as f:
            return f.read()

    @staticmethod
    def _extract_imports_from_ast(source: str, file_path: str = "") -> Set[str]:
        imported: Set[str] = set()
        try:
            tree = ast.parse(source, filename=file_path or "<unknown>")
        except SyntaxError as e:
            logger.warning(f"语法解析失败 {file_path}: {e}")
            return imported

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0].strip().lower()
                    if top_pkg and top_pkg.isidentifier() and not top_pkg.startswith("_"):
                        imported.add(top_pkg)

            elif isinstance(node, ast.ImportFrom):
                # 相对导入一般是项目内部模块
                if getattr(node, "level", 0) and node.level > 0:
                    continue
                if node.module:
                    top_pkg = node.module.split(".")[0].strip().lower()
                    if top_pkg and top_pkg.isidentifier() and not top_pkg.startswith("_"):
                        imported.add(top_pkg)

        return imported

    @staticmethod
    def _get_installed_distributions() -> Set[str]:
        """
        获取已安装分发包名（pip层面的发行名），优先 importlib.metadata。
        """
        dist_names: Set[str] = set()
        try:
            from importlib.metadata import distributions  # py3.8+
            for d in distributions():
                name = (d.metadata.get("Name") or "").strip().lower()
                if name:
                    dist_names.add(name)
        except Exception:
            # 回退方案（兼容旧环境）
            dist_names = {pkg.name.lower() for pkg in pkgutil.iter_modules()}
        return dist_names

    @staticmethod
    def _is_importable(module_name: str) -> bool:
        """
        不执行导入，仅用 find_spec 判断是否可解析，降低副作用。
        """
        try:
            return importlib.util.find_spec(module_name) is not None
        except Exception:
            return False

    @classmethod
    def _to_pip_name(cls, import_name: str) -> str:
        return cls.IMPORT_TO_PIP_MAP.get(import_name.lower(), import_name.lower())

    @classmethod
    def _is_satisfied(
        cls,
        import_name: str,
        installed_dists: Set[str],
    ) -> bool:
        name = import_name.lower()

        # 1) 标准库/内部模块直接视为满足
        if name in cls.BUILTIN_MODULES or name in cls.INTERNAL_MODULES:
            return True

        # 2) import 名可直接解析，也视为满足（本地包/editable 安装等场景）
        if cls._is_importable(name):
            return True

        # 3) 分发名直接匹配
        pip_name = cls._to_pip_name(name)
        if pip_name in installed_dists:
            return True

        # 4) 兜底映射匹配
        alias_dists = cls.IMPORT_SATISFY_BY_DIST.get(name, set())
        if any(d in installed_dists for d in alias_dists):
            return True

        return False

    @classmethod
    def _collect_imports_from_project(cls, project_path: str) -> Set[str]:
        imports: Set[str] = set()

        for root, _, files in os.walk(project_path):
            if "__pycache__" in root:
                continue

            for file in files:
                if not file.endswith(".py"):
                    continue

                file_path = os.path.join(root, file)
                try:
                    source = cls._read_source_with_fallback(file_path)
                    imports.update(cls._extract_imports_from_ast(source, file_path))
                except UnicodeDecodeError:
                    logger.warning(f"文件编码错误 {file_path}: 跳过")
                except Exception as e:
                    logger.warning(f"读取/解析失败 {file_path}: {str(e)}")

        return imports

    @staticmethod
    def generate_requirements(project_path: str = "./") -> List[str]:
        """
        扫描项目 import，返回“缺失依赖对应的 pip 包名列表”
        """
        imported_modules = cls_imports = PackageManager._collect_imports_from_project(project_path)
        installed_dists = PackageManager._get_installed_distributions()

        logger.debug(f"扫描到的导入模块: {sorted(imported_modules)}")
        logger.debug(f"已安装分发包: {sorted(installed_dists)}")

        missing_pip_packages: Set[str] = set()

        for mod in imported_modules:
            if not PackageManager._is_satisfied(mod, installed_dists):
                missing_pip_packages.add(PackageManager._to_pip_name(mod))

        # 避免把内部名透出为 pip 包
        missing_pip_packages = {
            p for p in missing_pip_packages
            if p not in PackageManager.INTERNAL_MODULES
            and p not in PackageManager.BUILTIN_MODULES
        }

        return sorted(missing_pip_packages)

    @staticmethod
    def install_missing_requirements() -> bool:
        project_path = get_project_root()
        logger.debug(f"项目根目录: {project_path}")

        logger.info("正在扫描项目缺失依赖（包含 tests 目录）...")
        missing = PackageManager.generate_requirements(project_path)
        logger.debug(f"扫描完成，缺失依赖列表: {missing}")

        if not missing:
            logger.info("✅ 所有依赖已安装，无需操作")
            return True

        logger.info(f"发现缺失依赖: {', '.join(missing)}")
        return PackageManager.pip_install_packages(missing)