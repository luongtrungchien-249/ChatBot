"""Canary: chung minh tung luat kien truc THUC SU bat duoc vi pham.

Tao file vi pham co y -> chay lint-imports/guard -> luat phai BAO DO -> xoa file.

Vi sao can: mot luat viet sai van chay xanh, no chi don gian khong bat duoc gi, va
ban se khong biet cho toi luc kien truc da vo. Da tung xay ra o ban TypeScript.

Chay: uv run python ops/canary_import_rules.py
"""

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

#: (ten luat, duong dan file canary, noi dung, lenh kiem tra)
CANARIES: list[tuple[str, Path, str, list[str]]] = [
    # Cac tang la goi CAP CAO NHAT, nen canary phai import TUYET DOI. Viet
    # `from ..infra...` trong src/agents/ se leo len tren goc goi va no ngay luc
    # import — luc do canary "do" vi ly do sai, va ta se tuong luat con song.
    (
        "L1: agents khong biet ha tang",
        SRC / "agents" / "_canary_infra.py",
        "from infra.logger import get_logger\n\n__all__ = ['get_logger']\n",
        ["lint-imports"],
    ),
    (
        "L1: agents khong duoc goi tools",
        SRC / "agents" / "_canary_tools.py",
        "from tools.registry import tool_port\n\n__all__ = ['tool_port']\n",
        ["lint-imports"],
    ),
    (
        "L1: agents khong doc config",
        SRC / "agents" / "_canary_config.py",
        "from config import get_settings\n\n__all__ = ['get_settings']\n",
        ["lint-imports"],
    ),
    (
        "L5: moi adapter la mot hop kin",
        SRC / "adapters" / "cli" / "_canary_cross.py",
        "from ..web import normalize\n\n__all__ = ['normalize']\n",
        ["lint-imports"],
    ),
    (
        "L5: adapter khong goi LLM",
        SRC / "adapters" / "cli" / "_canary_llm.py",
        "from llm.models import MODELS\n\n__all__ = ['MODELS']\n",
        ["lint-imports"],
    ),
    (
        "L4: chi memory.repository duoc cham fact_repo",
        SRC / "knowledge" / "_canary_fact.py",
        "from memory.repository import fact_repo\n\n__all__ = ['fact_repo']\n",
        ["lint-imports"],
    ),
    (
        "L4b: khong SQL nao cham memory_fact ngoai repository",
        SRC / "knowledge" / "_canary_sql.py",
        'QUERY = "SELECT * FROM memory_fact"\n',
        ["python", "ops/guard_sql.py"],
    ),
    (
        "L7: chi config duoc doc bien moi truong",
        SRC / "infra" / "_canary_env.py",
        "import os\n\nKEY = os.environ.get('OPENAI_API_KEY')\n",
        ["python", "ops/guard_env.py"],
    ),
]


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        ["uv", "run", *command], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    # Cac file phu tro de canary import duoc.
    (SRC / "memory" / "repository" / "fact_repo.py").touch()
    (SRC / "adapters" / "web" / "normalize.py").touch()

    dead: list[str] = []
    for name, path, content, command in CANARIES:
        path.write_text(content, encoding="utf-8")
        try:
            code, _ = run(command)
        finally:
            path.unlink(missing_ok=True)

        if code == 0:
            dead.append(name)
            print(f"CHET   {name}   <-- luat nay khong bat duoc gi")
        else:
            print(f"SONG   {name}")

    if dead:
        print(f"\n{len(dead)} luat khong bat duoc vi pham nao. Sua truoc khi tin vao chung.")
        return 1

    print(f"\nTat ca {len(CANARIES)} luat deu bat duoc vi pham co y.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
