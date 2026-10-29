"""PostgreSQL chạy tại chỗ cho máy không có Docker — dùng bản PostgreSQL đóng gói sẵn trong gói pgserver
(requirements-dev.txt), không cần cài đặt hệ thống.

    python scripts/dev_postgres.py            # khởi động; lần đầu tự tạo cụm và CSDL office_agent
    python scripts/dev_postgres.py stop
    python scripts/dev_postgres.py status

Dữ liệu nằm ở storage/pgdata. Chỉ nghe trên localhost (IPv4 + IPv6) và không đặt mật khẩu → chỉ dùng để phát triển.
Đặt trong backend/.env:  DATABASE_URL=postgresql://office@localhost:5432/office_agent
"""
import argparse
import subprocess
import sys
from pathlib import Path

from pgserver._commands import POSTGRES_BIN_PATH

ROOT = Path(__file__).resolve().parent.parent
USER, DB = "office", "office_agent"


def _bin(name: str) -> str:
    return str(POSTGRES_BIN_PATH / (name + (".exe" if sys.platform == "win32" else "")))


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", nargs="?", default="start", choices=["start", "stop", "status"])
    ap.add_argument("--port", type=int, default=5432)
    ap.add_argument("--data", type=Path, default=ROOT / "storage" / "pgdata")
    a = ap.parse_args()
    data = a.data.resolve()

    if a.action == "stop":
        print(_run(_bin("pg_ctl"), "-D", str(data), "stop", "-m", "fast", check=False).stdout.strip())
        return
    running = data.exists() and _run(_bin("pg_ctl"), "-D", str(data), "status", check=False).returncode == 0
    if a.action == "status":
        print("đang chạy" if running else "đã dừng")
        return

    if not (data / "PG_VERSION").exists():
        data.mkdir(parents=True, exist_ok=True)
        _run(_bin("initdb"), "-D", str(data), "-U", USER, "--auth=trust", "--encoding=UTF8", "--no-locale")
        print(f"Đã tạo cụm PostgreSQL ở {data}")
    if not running:
        # Không bắt stdout/stderr: tiến trình postgres kế thừa ống dẫn và giữ nó mở → subprocess chờ mãi (Windows)
        subprocess.run([_bin("pg_ctl"), "-D", str(data), "-l", str(data / "server.log"), "-w", "start",
                        "-o", f"-p {a.port} -c listen_addresses=localhost"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    exists = _run(_bin("psql"), "-h", "127.0.0.1", "-p", str(a.port), "-U", USER, "-d", "postgres", "-tAc",
                  f"SELECT 1 FROM pg_database WHERE datname = '{DB}'").stdout.strip()
    if not exists:
        _run(_bin("createdb"), "-h", "127.0.0.1", "-p", str(a.port), "-U", USER, DB)
        print(f"Đã tạo CSDL {DB}")
    print(f"PostgreSQL đang chạy. DATABASE_URL=postgresql://{USER}@localhost:{a.port}/{DB}")


if __name__ == "__main__":
    main()
