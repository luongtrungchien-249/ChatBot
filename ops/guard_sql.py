"""L4: khong cau SQL nao duoc cham bang memory_fact ngoai memory/repository/.

import-linter so khop DUONG DAN MODULE, khong doc duoc chuoi SQL — hop dong 5 trong
.importlinter chi chan viec IMPORT fact_repo, khong chan ai do viet
'SELECT ... FROM memory_fact' thang trong knowledge/. Day la lop con thieu.

Chay: uv run python ops/guard_sql.py   (bat buoc trong CI)
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"
ALLOWED_PREFIX = ("memory", "repository")
NEEDLE = "memory_fact"


def violations() -> list[str]:
    found: list[str] = []

    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT)
        if relative.parts[: len(ALLOWED_PREFIX)] == ALLOWED_PREFIX:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        # Chi xet CHUOI trong ma nguon. Nhac ten bang trong comment hay docstring la
        # hop le — chay SQL len no thi khong. AST bo comment san, con docstring thi
        # loai o duoi.
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and NEEDLE in node.value
                and id(node) not in docstrings
            ):
                found.append(f"{relative}:{node.lineno}")

    return found


def main() -> int:
    found = violations()
    if found:
        print(f"L4 vi pham: '{NEEDLE}' chi duoc xuat hien trong memory/repository/")
        for line in found:
            print(f"  {line}")
        return 1
    print(f"guard_sql OK - khong co '{NEEDLE}' nao ngoai memory/repository/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
