"""Sandbox chạy mã Python phân tích dữ liệu cho tool run_python.

Chạy trong container riêng: không có mạng ra ngoài (mạng nội bộ chỉ nối với backend), user không phải root,
hệ thống tệp chỉ đọc trừ /tmp. Mỗi lần chạy: thư mục tạm mới, tiến trình con có giới hạn CPU/RAM/thời gian/kích thước
tệp. Trả về stdout/stderr và các tệp mới tạo (hình, bảng, tệp Office).
"""
import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

MAX_OUTPUT_FILES = 10
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
MAX_STDOUT = 50_000
MEMORY_BYTES = 1024 * 1024 * 1024
MAX_TIMEOUT = 120

app = FastAPI(title="Office Agent sandbox")


class RunRequest(BaseModel):
    code: str
    files: dict[str, str] = {}  # tên tệp → base64
    timeout: float = 60


class RunResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    outputs: dict[str, str]  # tên tệp → base64
    timed_out: bool = False


def _limits(timeout: float):
    def apply():  # chạy trong tiến trình con trước khi exec (chỉ Linux)
        import resource
        cpu = int(timeout) + 1
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        os.setsid()
    return apply if sys.platform.startswith("linux") else None


def run(req: RunRequest) -> RunResult:
    timeout = min(max(req.timeout, 1), MAX_TIMEOUT)
    with tempfile.TemporaryDirectory(prefix="run-") as tmp:
        work = Path(tmp)
        before: dict[str, int] = {}
        for name, b64 in req.files.items():
            safe = Path(name).name
            if not safe or safe.startswith("."):
                raise HTTPException(400, f"Tên tệp không hợp lệ: {name}")
            (work / safe).write_bytes(base64.b64decode(b64))
            before[safe] = (work / safe).stat().st_mtime_ns
        (work / "_main.py").write_text(req.code, encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(work), "MPLBACKEND": "Agg",
               "PYTHONIOENCODING": "utf-8", "MPLCONFIGDIR": str(work / ".mpl"), "OPENBLAS_NUM_THREADS": "1"}
        timed_out = False
        try:
            p = subprocess.run([sys.executable, "-I", "_main.py"], cwd=work, env=env, capture_output=True,
                               timeout=timeout, preexec_fn=_limits(timeout))
            code, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            timed_out, code = True, -9
            out, err = e.stdout or b"", (e.stderr or b"") + f"\nQuá thời gian {timeout:.0f}s".encode()

        outputs, total = {}, 0
        for f in sorted(work.iterdir(), key=lambda x: x.name):
            if f.name.startswith((".", "_main")) or not f.is_file():
                continue
            if f.name in before and f.stat().st_mtime_ns == before[f.name]:
                continue  # tệp đầu vào không đổi
            size = f.stat().st_size
            if len(outputs) >= MAX_OUTPUT_FILES or total + size > MAX_OUTPUT_BYTES:
                break
            outputs[f.name] = base64.b64encode(f.read_bytes()).decode()
            total += size
        return RunResult(exit_code=code, stdout=out.decode("utf-8", "ignore")[-MAX_STDOUT:],
                         stderr=err.decode("utf-8", "ignore")[-MAX_STDOUT:], outputs=outputs, timed_out=timed_out)


@app.post("/run", response_model=RunResult)
def run_endpoint(req: RunRequest) -> RunResult:
    return run(req)


@app.get("/health")
def health():
    return {"ok": True}
