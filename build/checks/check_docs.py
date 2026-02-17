#!/usr/bin/env python3
"""
文档一致性检查脚本.

检查内容：
- Python 文件的 docstrings（Google 风格）。
- 函数必须有 Args/Returns/Raises 部分（如适用）。

使用方法：
    python check_docs.py                    # 检查 git 暂存区文件
    python check_docs.py --all             # 检查所有 Python 文件
    python check_docs.py file1.py file2.py # 检查指定文件

退出码：
    0 - 检查通过
    1 - 检查失败（有错误或警告）
"""

import argparse
import ast
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def get_project_root() -> Path:
    """获取项目根目录（使用 git）。.

    Returns:
        项目根目录的 Path 对象。

    Raises:
        RuntimeError: 如果不在 git 仓库中。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("无法获取 git 项目根目录") from exc


class DocstringChecker:
    """检查 Python 文件的 docstrings。."""

    def __init__(self, file_path: Path):
        """初始化检查器。.

        Args:
            file_path: 要检查的 Python 文件路径。
        """
        self.file_path = file_path
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def check(self) -> Tuple[List[str], List[str]]:
        """运行所有检查。.

        Returns:
            包含两个列表的元组：(errors, warnings)。
        """
        try:
            content = self.file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except SyntaxError as exc:
            self.errors.append(f"语法错误: {exc}")
            return self.errors, self.warnings
        except Exception as exc:
            self.errors.append(f"无法读取文件: {exc}")
            return self.errors, self.warnings

        self._check_module_docstring(tree)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._check_class_docstring(node)
            elif isinstance(node, ast.FunctionDef):
                self._check_function_docstring(node)
            elif isinstance(node, ast.AsyncFunctionDef):
                self._check_function_docstring(node)

        return self.errors, self.warnings

    def _check_module_docstring(self, tree: ast.Module):
        """检查模块级 docstring。."""
        if ast.get_docstring(tree):
            return
        if self.file_path.name == "__init__.py":
            return
        self.warnings.append("缺少模块级 docstring")

    def _check_class_docstring(self, node: ast.ClassDef):
        """检查类 docstring。."""
        docstring = ast.get_docstring(node)
        if not docstring:
            self.warnings.append(f"类 '{node.name}' 缺少 docstring")
            return
        if len(docstring.strip()) < 10:
            self.warnings.append(f"类 '{node.name}' 的 docstring 过于简短")

    def _check_function_docstring(self, node):
        """检查函数 docstring（Google 风格）。.

        Args:
            node: ast.FunctionDef 或 ast.AsyncFunctionDef 节点。
        """
        if node.name.startswith("_"):
            return

        docstring = ast.get_docstring(node)
        if not docstring:
            self.warnings.append(f"函数 '{node.name}' 缺少 docstring")
            return

        has_args = "Args:" in docstring
        has_returns = "Returns:" in docstring
        has_raises = "Raises:" in docstring

        args = [arg.arg for arg in node.args.args if arg.arg != "self"]
        has_return = node.returns is not None or not self._is_none_return(node)

        if args and not has_args:
            self.warnings.append(f"函数 '{node.name}' 有参数但缺少 'Args:' 部分")

        if has_return and not has_returns:
            self.warnings.append(f"函数 '{node.name}' 有返回值但缺少 'Returns:' 部分")

        if self._has_raise_statement(node) and not has_raises:
            self.warnings.append(f"函数 '{node.name}' 会抛出异常但缺少 'Raises:' 部分")

    def _is_none_return(self, node) -> bool:
        """检查函数是否返回 None（简化检查）。."""
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value is not None:
                return False
        return True

    def _has_raise_statement(self, node) -> bool:
        """检查函数体中是否有 raise 语句。."""
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                return True
        return False


def get_staged_files(project_root: Path) -> List[Path]:
    """获取 git 暂存区的 Python 文件。.

    Args:
        project_root: 项目根目录。

    Returns:
        暂存区 Python 文件的 Path 列表。
    """
    files = []
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line and line.endswith(".py"):
                    path = project_root / line
                    if path.exists():
                        files.append(path)
    except Exception:
        pass
    return files


def get_all_python_files(project_root: Path) -> List[Path]:
    """获取项目中所有的 Python 文件（排除 .git 和隐藏目录）。.

    Args:
        project_root: 项目根目录。

    Returns:
        所有 Python 文件的 Path 列表。
    """
    files = []
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    path = project_root / line
                    if path.exists():
                        files.append(path)
    except Exception:
        pass
    return files


def resolve_paths(paths: List[str], project_root: Path) -> List[Path]:
    """解析文件路径为绝对路径。.

    Args:
        paths: 文件路径列表。
        project_root: 项目根目录。

    Returns:
        绝对 Path 列表。
    """
    resolved = []
    for p in paths:
        path = Path(p)
        if path.is_absolute():
            resolved.append(path)
        else:
            resolved.append((project_root / path).resolve())
    return resolved


def check_files(files: List[Path], project_root: Path) -> Tuple[List[str], List[str]]:
    """检查文件列表并返回结果。.

    Args:
        files: 要检查的文件列表。
        project_root: 项目根目录（用于计算相对路径）。

    Returns:
        包含两个列表的元组：(errors, warnings)。
    """
    all_errors = []
    all_warnings = []

    print("🔍 检查 docstrings...")
    for file_path in files:
        if not file_path.exists():
            print(f"   ⚠️  跳过不存在的文件: {file_path}")
            continue

        checker = DocstringChecker(file_path)
        errors, warnings = checker.check()

        if errors or warnings:
            try:
                rel_path = file_path.relative_to(project_root)
            except ValueError:
                rel_path = file_path
            print(f"\n   📄 {rel_path}")
            for err in errors:
                print(f"      ❌ {err}")
                all_errors.append(f"{rel_path}: {err}")
            for warn in warnings:
                print(f"      ⚠️  {warn}")
                all_warnings.append(f"{rel_path}: {warn}")

    return all_errors, all_warnings


def print_results(all_errors: List[str], all_warnings: List[str]) -> int:
    """打印检查结果。.

    Args:
        all_errors: 错误列表。
        all_warnings: 警告列表。

    Returns:
        退出码，0 表示成功，1 表示有警告或错误。
    """
    if not all_errors and not all_warnings:
        print("   ✅ 所有文件检查通过！")
        return 0

    print("\n" + "=" * 50)
    print("📊 检查结果汇总")
    print("=" * 50)

    if all_errors:
        print(f"   ❌ 错误: {len(all_errors)} 个")
    if all_warnings:
        print(f"   ⚠️  警告: {len(all_warnings)} 个")

    print("\n💡 请修复上述问题后重新提交。")
    return 1


def main() -> int:
    """主函数。.

    Returns:
        退出码，0 表示成功，1 表示有错误。
    """
    parser = argparse.ArgumentParser(
        description="检查 Python 文件的 docstrings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    %(prog)s                    # 检查 git 暂存区的 Python 文件
    %(prog)s --all             # 检查项目中所有 Python 文件
    %(prog)s file1.py file2.py # 检查指定文件
        """,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="检查所有 Python 文件（而非仅暂存区）",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="指定要检查的文件（覆盖 --all）",
    )

    args = parser.parse_args()

    try:
        project_root = get_project_root()
    except RuntimeError as exc:
        print(f"❌ 错误: {exc}")
        return 1

    # 确定要检查的文件
    if args.files:
        files = resolve_paths(args.files, project_root)
    elif args.all:
        files = get_all_python_files(project_root)
        print(f"📋 检查项目中所有 Python 文件 ({len(files)} 个)\n")
    else:
        files = get_staged_files(project_root)
        if files:
            print(f"📋 检查 git 暂存区的 Python 文件 ({len(files)} 个)\n")

    if not files:
        print("✅ 未检测到需要检查的 Python 文件。")
        return 0

    all_errors, all_warnings = check_files(files, project_root)
    return print_results(all_errors, all_warnings)


if __name__ == "__main__":
    sys.exit(main())
