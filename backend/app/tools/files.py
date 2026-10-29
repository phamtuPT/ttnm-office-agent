from pydantic import BaseModel

from .registry import ToolCtx, tool


class NoArgs(BaseModel):
    pass


@tool("list_files", "Liệt kê các tệp người dùng đã tải lên trong phiên này.", NoArgs)
def list_files(args: NoArgs, ctx: ToolCtx) -> dict:
    return {"files": ctx.files}
