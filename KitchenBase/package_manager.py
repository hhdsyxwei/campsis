# KitchenBase/package_manager.py
import ast
import os
import subprocess
import sys
import pkgutil
import tokenize
import importlib.util
from typing import List, Set, Dict, Iterable
import re  # 新增：导入正则模块

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
        "pil": "pillow",  # 修复：直接写小写键名，删除无效lower()
        "bs4": "beautifulsoup4",
        "sklearn": "scikit-learn",
        "crypto": "pycryptodome",  # 修复：直接写小写键名
        "dateutil": "python-dateutil",
        "fitz": "pymupdf",
        "openssl": "pyopenssl",  # 修复：直接写小写键名
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
    INTERNAL_MODULES = {"kitchenbase", "ingredient", "cookingengine", "tests"}

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

        # 修复：过滤非法包名（仅允许字母/数字/-/_）+ 处理首尾空格
        valid_packages = []
        for pkg in packages:
            pkg_clean = pkg.strip()
            if re.match(r"^[a-zA-Z0-9_\-]+$", pkg_clean):
                valid_packages.append(pkg_clean)
            else:
                logger.error(f"非法包名，跳过: {pkg}")
        if not valid_packages:
            logger.error("❌ 无合法包名可安装")
            return False

        # 去重+排序
        valid_packages = sorted(set(valid_packages))

        cmd = [sys.executable, "-m", "pip", "install"]
        if upgrade:
            cmd.append("--upgrade")
        if quiet:
            cmd.append("-q")
        cmd.extend(valid_packages)  # 仅拼接合法包名

        logger.info(f"📦 准备安装依赖: {', '.join(valid_packages)}")
        logger.debug(f"执行命令: {' '.join(cmd)}")

        # 补全：原遗漏的subprocess执行逻辑
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
        """修复：补充文件读取异常捕获"""
        try:
            with tokenize.open(file_path) as f:
                return f.read()
        except (PermissionError, FileNotFoundError, UnicodeDecodeError) as e:
            logger.warning(f"读取文件失败 {file_path}: {str(e)}")
            return ""

    @staticmethod
    def _extract_imports_from_ast(source: str, file_path: str = "") -> Set[str]:
        imported: Set[str] = set()
        try:
            tree = ast.parse(source, filename=file_path or "<unknown>")
        except SyntaxError as e:
            logger.warning(f"语法解析失败 {file_path}: {e}")
            return imported

        def _add_import(name: str):
            """递归添加所有父级包（如 a.b.c → a、a.b、a.b.c），保证分级判定"""
            parts = name.split(".")
            for i in range(1, len(parts)+1):
                full_pkg = ".".join(parts[:i]).strip().lower()
                if full_pkg and full_pkg.isidentifier() and not full_pkg.startswith("_"):
                    imported.add(full_pkg)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _add_import(alias.name)  # 完整导入名（如 baostock、pymysql）

            elif isinstance(node, ast.ImportFrom):
                # 相对导入（如 from . import xxx）直接判定为内部模块，跳过
                if getattr(node, "level", 0) > 0:
                    continue
                if node.module:
                    _add_import(node.module)  # 完整模块路径（如 KitchenBase.stock_enums）

        return imported

    @staticmethod
    def _get_installed_distributions() -> Set[str]:
        """
        修复：仅使用 importlib.metadata（强制 Python 3.8+），或兼容旧版本的 pip list 解析
        """
        dist_names: Set[str] = set()
        try:
            # 方案1：Python 3.8+ 推荐
            from importlib.metadata import distributions
            for d in distributions():
                name = d.name.lower().strip()
                if name:
                    dist_names.add(name)
        except Exception:  # 修复：恢复兜底捕获，避免非ImportError中断
            # 方案2：兼容 Python 3.7-，通过 pip list 解析（更可靠）
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "list", "--format=freeze"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                for line in result.stdout.splitlines():
                    if "==" in line:
                        pkg_name = line.split("==")[0].lower().strip()
                        dist_names.add(pkg_name)
            except Exception as e:
                logger.error(f"获取已安装包失败: {e}")
                # 修复：改为返回空集而非raise，避免整个流程崩溃
                logger.warning("降级使用pkgutil.iter_modules()获取模块名（精度降低）")
                dist_names = {pkg.name.lower() for pkg in pkgutil.iter_modules()}
        return dist_names

    @staticmethod
    def _is_importable(module_name: str) -> bool:
        """
        修复：捕获全量异常，避免流程中断
        """
        if module_name in PackageManager.BUILTIN_MODULES:
            return True  # 标准库直接返回True，避免检查
    
        try:
            # 使用 sys.path 仅检查存在性，不加载模块
            spec = importlib.util.find_spec(module_name)
            return spec is not None and spec.origin is not None
        except Exception as e:  # 修复：捕获所有异常
            # 仅捕获已知的“模块不存在/语法错误/系统错误”
            logger.warning(f"检查模块 {module_name} 可导入性失败: {str(e)}")
            return False

    @classmethod
    def _to_pip_name(cls, import_name: str) -> str:
        return cls.IMPORT_TO_PIP_MAP.get(import_name.lower(), import_name.lower())

    @staticmethod
    def _is_satisfied(
        import_name: str,
        installed_dists: Set[str],
    ) -> bool:
        name = import_name.lower()

        # 1) 标准库/内部模块直接视为满足
        if name in PackageManager.BUILTIN_MODULES or name in PackageManager.INTERNAL_MODULES:
            return True

        # 2) import 名可直接解析，也视为满足（本地包/editable 安装等场景）
        if PackageManager._is_importable(name):
            return True

        # 3) 分发名直接匹配
        pip_name = PackageManager._to_pip_name(name)
        if pip_name in installed_dists:
            return True

        # 4) 兜底映射匹配
        alias_dists = PackageManager.IMPORT_SATISFY_BY_DIST.get(name, set())
        if any(d in installed_dists for d in alias_dists):
            return True

        return False

    @staticmethod
    def _collect_imports_from_project(project_path: str) -> Set[str]:
        imports: Set[str] = set()
        # 新增：定义需要排除的目录（可配置化）
        EXCLUDE_DIRS = {"__pycache__", "venv", "env", "build", "dist", "logs", "tests/.pytest_cache"}
        
        for root, dirs, files in os.walk(project_path):
            # 过滤排除目录（修改dirs原地生效，os.walk会跳过子目录）
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            # 过滤非.py文件
            py_files = [f for f in files if f.endswith(".py") and not f.startswith(".")]
            for file in py_files:
                file_path = os.path.join(root, file)
                try:
                    source = PackageManager._read_source_with_fallback(file_path)
                    imports.update(PackageManager._extract_imports_from_ast(source, file_path))
                except Exception as e:
                    logger.warning(f"读取/解析失败 {file_path}: {str(e)}")
    
        return imports

    @staticmethod
    def generate_requirements(project_path: str = "./") -> List[str]:
        """
        扫描项目 import，返回“缺失依赖对应的 pip 包名列表”
        """
        imported_modules = PackageManager._collect_imports_from_project(project_path)
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