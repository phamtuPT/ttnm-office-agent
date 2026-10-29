"""Đăng ký tool cho agent.

Mỗi tool = một hàm `handler(args, ctx) -> dict` + một Pydantic model mô tả tham số.
Description của tool và của từng Field là thứ LLM đọc để chọn tool → viết rõ, bằng tiếng Việt.

    class Args(BaseModel):
        file: str = Field(description="Tên tệp .xlsx trong phiên")

    @tool("excel_inspect", "Xem cấu trúc workbook ...", Args, kind="xlsx")
    def excel_inspect(args: Args, ctx: ToolCtx) -> dict: ...

Cờ của tool:
  writes       sửa tệp có sẵn — handler ghi vào ctx.path (tệp tạm), executor lo sao lưu/ghi nguyên tử
  creates      tạo tệp mới tên args.file — handler ghi vào ctx.path (tệp tạm)
  destructive  cần người dùng xác nhận trước khi chạy
  inline       chạy trong event loop, được dùng ctx.db (tool hệ thống như hoàn tác)

Lỗi LLM có thể tự sửa được → raise ToolError, thông báo được trả lại cho LLM.
Muốn gửi ảnh cho LLM (ví dụ ảnh render trang) → trả về key "_images": [(bytes, mime), ...].
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel


class ToolError(Exception):
    pass


class Selection(BaseModel):
    """Vùng người dùng đã chọn trên giao diện. Tool ghi chỉ được sửa trong vùng này.

    Ngoại lệ: chọn đúng MỘT ô Excel chỉ là điểm neo (vị trí con trỏ / chỗ bắt đầu điền dữ liệu), giống bấm vào một ô
    trong Excel — không giới hạn vùng sửa. Chỉ khi kéo chọn từ hai ô trở lên mới khoá phạm vi sửa.
    """

    file: str
    sheet: str | None = None
    range: str | None = None  # Excel, ví dụ "B2:D10"
    paragraphs: list[int] | None = None  # Word, chỉ số đoạn
    slides: list[int] | None = None  # PowerPoint, chỉ số slide (từ 0)

    @property
    def is_anchor(self) -> bool:
        if not self.range or self.paragraphs is not None or self.slides is not None:
            return False
        start, _, end = self.range.replace("$", "").upper().partition(":")
        return not end or start == end


@dataclass
class ToolCtx:
    path: Path | None  # tệp tool thao tác (với tool ghi/tạo: tệp tạm)
    selection: Selection | None  # chỉ có khi selection thuộc đúng tệp này
    files: list[dict] = field(default_factory=list)
    assets_dir: Path | None = None  # ảnh người dùng gửi kèm
    session_id: str = ""
    turn_id: str | None = None
    db: Any = None  # chỉ dùng trong tool inline


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[BaseModel, ToolCtx], dict]
    kind: str | None = None  # xlsx | docx | pptx — tool có tham số `file` phải đúng loại này
    writes: bool = False
    creates: bool = False
    destructive: bool = False
    inline: bool = False
    # Điều kiện để model thấy tool (ví dụ máy có LibreOffice / sandbox). Không đạt → không khai báo cho model, tiết
    # kiệm bước và tránh model gọi rồi nhận lỗi "chưa cài".
    available: Callable[[], bool] | None = None


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, args_model: type[BaseModel], *, kind: str | None = None,
         writes: bool = False, creates: bool = False, destructive: bool = False, inline: bool = False,
         available: Callable[[], bool] | None = None):
    def deco(fn):
        REGISTRY[name] = Tool(name, description, args_model, fn, kind, writes, creates, destructive, inline, available)
        return fn
    return deco


def declarations() -> list[dict]:
    """Khai báo trung lập với provider: {name, description, parameters (JSON Schema)}."""
    return [{"name": t.name, "description": t.description,
             "parameters": _clean_schema(t.args_model.model_json_schema())}
            for t in REGISTRY.values() if t.available is None or t.available()]


def _clean_schema(schema: dict) -> dict:
    """Inline $defs và bỏ `title` để schema gọn, tránh phần JSON Schema mà LLM hỗ trợ kém."""
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(dict(defs[node["$ref"].split("/")[-1]]))
            return {k: walk(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)
