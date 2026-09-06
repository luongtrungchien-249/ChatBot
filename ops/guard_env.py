"""L7: chi config/ duoc cham bien moi truong.

import-linter so khop IMPORT MODULE, con `os.environ` la truy cap THUOC TINH —
no khong bat duoc. Day la lop bu, giong ops/guard_sql.py bu cho nua con lai cua L4.

Chay: uv run python ops/guard_env.py   (bat buoc trong CI)

Vi sao luat nay quan trong: config doc mot lan luc khoi dong qua schema, thieu bien
thi process khong khoi dong duoc. Mot cho khac len doc os.environ truc tiep la mot
cho co the chay duoc o may ban va chet o production luc 2 gio sang.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"
ALLOWED = {"config"}
FORBIDDEN_CALLS = {"getenv"}
FORBIDDEN_ATTRS = {"environ"}


def violations() -> list[str]:
    found: list[str] = []

    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT)
        if relative.parts and relative.parts[0] in ALLOWED:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            # os.environ / os.environ.get(...)
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                value = node.value
                if isinstance(value, ast.Name) and value.id == "os":
                    found.append(f"{relative}:{node.lineno}: os.{node.attr}")
            # os.getenv(...)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                func = node.func
                if (
                    func.attr in FORBIDDEN_CALLS
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "os"
                ):
                    found.append(f"{relative}:{node.lineno}: os.{func.attr}()")

    return found


def main() -> int:
    found = violations()
    if found:
        print("L7 vi pham: chi config/ duoc doc bien moi truong")
        for line in found:
            print(f"  {line}")
        return 1
    print("guard_env OK - khong co cho nao ngoai config/ doc bien moi truong")
    return 0


if __name__ == "__main__":
    sys.exit(main())
