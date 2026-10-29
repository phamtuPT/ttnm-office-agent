"""Đăng ký tool cho agent.

Mỗi tool = một hàm đồng bộ `handler(args, ctx) -> dict` + một Pydantic model mô tả tham số.
Description của tool và của từng Field là thứ LLM đọc để chọn tool → viết rõ, bằng tiếng Việt.

    class Args(BaseModel):
        file: str = Field(description="Tên tệp .xlsx trong phiên")

    @tool("excel_inspect", "Xem cấu trúc workbook ...", Args)
    def excel_inspect(args: Args, ctx: ToolCtx) -> dict: ...

Lỗi người dùng/LLM có thể sửa được thì raise ToolError — thông báo sẽ được trả lại cho LLM.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel


class ToolError(Exception):
    pass


class Selection(BaseModel):
    """Vùng người dùng đã chọn trên giao diện. Tool ghi chỉ được sửa trong vùng này."""

    file: str
    sheet: str | None = None
    range: str | None = None  # Excel, ví dụ "B2:D10"
    paragraphs: list[int] | None = None  # Word, chỉ số đoạn
    slides: list[int] | None = None  # PowerPoint, chỉ số slide (từ 0)


@dataclass
class ToolCtx:
    path: Path | None  # bản làm việc của tệp mà tool thao tác (None nếu tool không gắn với tệp)
    selection: Selection | None  # chỉ có khi selection thuộc đúng tệp này
    files: list[dict] = field(default_factory=list)


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[BaseModel, ToolCtx], dict]
    kind: str | None = None  # xlsx | docx | pptx — tool có tham số `file` phải đúng loại này
    writes: bool = False
    destructive: bool = False  # cần người dùng xác nhận trước khi chạy


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, args_model: type[BaseModel], *, kind: str | None = None,
         writes: bool = False, destructive: bool = False):
    def deco(fn):
        REGISTRY[name] = Tool(name, description, args_model, fn, kind, writes, destructive)
        return fn
    return deco


def declarations() -> list[dict]:
    """Khai báo trung lập với provider: {name, description, parameters (JSON Schema)}."""
    return [{"name": t.name, "description": t.description,
             "parameters": _clean_schema(t.args_model.model_json_schema())}
            for t in REGISTRY.values()]


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
