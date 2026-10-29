"""LLM giả: không gọi mạng, không tốn tiền.

- Không truyền script: chế độ "echo" để làm giao diện — gọi list_files rồi nhắc lại câu người dùng.
- Truyền script: dùng trong test, mỗi phần tử là một lượt trả lời của model:
      {"text": "Xong"}  hoặc  {"tool_calls": [{"name": "excel_write_cells", "args": {...}}]}
"""
from .base import LLMProvider, OnText, ToolCall, TurnResult


class MockProvider(LLMProvider):
    fmt = "mock"
    name = "mock"
    model = "mock"

    def __init__(self, script: list[dict] | None = None):
        self.script = list(script) if script is not None else None
        self.seen_systems: list[str] = []  # cho test kiểm tra system prompt

    async def stream_turn(self, history, system, tools, on_text: OnText) -> TurnResult:
        self.seen_systems.append(system)
        step = self.script.pop(0) if self.script is not None else self._echo(history)
        text = step.get("text", "")
        for i, word in enumerate(text.split(" ") if text else []):
            await on_text(word if i == 0 else " " + word)
        calls = [ToolCall(f"call_{i}", c["name"], c.get("args", {})) for i, c in enumerate(step.get("tool_calls", []))]
        raw = {"role": "model", "text": text, "tool_calls": [c.__dict__ for c in calls]}
        return TurnResult(text, calls, raw, "STOP", {"input_tokens": 10, "output_tokens": len(text.split())})

    @staticmethod
    def _echo(history: list[dict]) -> dict:
        """Kịch bản giả theo từ khoá để thử giao diện: "tạo bảng", "hoàn tác", còn lại thì liệt kê tệp."""
        user_i = max(i for i, h in enumerate(history) if h["role"] == "user")
        said = history[user_i]["text"].split("\n\n")[-1]
        step = sum(1 for h in history[user_i:] if h["role"] == "tool")
        low = said.lower()
        if "tạo bảng" in low:
            name = f"mock-doanh-thu-{user_i}.xlsx"
            plan = [
                {"text": "① Tạo bảng → ② Thêm biểu đồ cột → ③ Báo lại", "tool_calls": [{"name": "excel_create_workbook", "args": {
                    "file": name, "sheets": [{"name": "Doanh thu", "rows": [["Tháng", "Doanh thu"]]
                                              + [[m, 100 + m * 10] for m in range(1, 13)] + [["Tổng", "=SUM(B2:B13)"]]}]}}]},
                {"tool_calls": [{"name": "excel_add_chart", "args": {
                    "file": name, "sheet": "Doanh thu", "chart_type": "column", "data_range": "B1:B13",
                    "categories_range": "A2:A13", "title": "Doanh thu theo tháng", "anchor": "D2"}}]},
                {"text": f"(mock) Đã tạo {name}: 12 tháng, dòng tổng ở B14 và biểu đồ cột tại D2."},
            ]
            return plan[min(step, 2)]
        if "hoàn tác" in low:
            if step == 0:
                return {"tool_calls": [{"name": "undo_last_request", "args": {}}]}
            r = history[-1]["results"][0]["result"]
            return {"text": "(mock) Đã hoàn tác yêu cầu trước. Bấm Làm lại nếu muốn khôi phục." if r["ok"]
                    else f"(mock) Không hoàn tác được: {r['error']}"}
        if step == 0:
            return {"tool_calls": [{"name": "list_files", "args": {}}]}
        files = [f["name"] for f in history[-1]["results"][0]["result"].get("files", [])]
        return {"text": f"(mock) Bạn vừa nói: “{said}”. Tệp trong phiên: {', '.join(files) or 'chưa có'}. "
                        "Thử gõ “tạo bảng” hoặc “hoàn tác”."}

    def user_message(self, text, images):
        return {"role": "user", "text": text, "images": len(images)}

    def model_text_message(self, text):
        return {"role": "model", "text": text, "tool_calls": []}

    def tool_results_message(self, results):
        return {"role": "tool", "results": [{"name": c.name, "result": r, "images": len(imgs)} for c, r, imgs in results]}

    async def quick(self, prompt: str) -> str:
        return prompt.strip().splitlines()[-1][:40]

    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        return "(mock) văn bản chép từ giọng nói"
