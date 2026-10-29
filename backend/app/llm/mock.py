"""LLM giả: không gọi mạng, không tốn tiền.

- Không truyền script: chế độ "echo" để TV4 làm giao diện — gọi list_files rồi nhắc lại câu người dùng.
- Truyền script: dùng trong test, mỗi phần tử là một lượt trả lời của model:
      {"text": "Xong"}  hoặc  {"tool_calls": [{"name": "excel_write_cells", "args": {...}}]}
"""
from .base import LLMProvider, OnText, ToolCall, TurnResult


class MockProvider(LLMProvider):
    def __init__(self, script: list[dict] | None = None):
        self.script = list(script) if script is not None else None

    async def stream_turn(self, history, system, tools, on_text: OnText) -> TurnResult:
        step = self.script.pop(0) if self.script is not None else self._echo(history)
        text = step.get("text", "")
        for i, word in enumerate(text.split(" ") if text else []):
            await on_text(word if i == 0 else " " + word)
        calls = [ToolCall(f"call_{i}", c["name"], c.get("args", {})) for i, c in enumerate(step.get("tool_calls", []))]
        raw = {"role": "model", "text": text, "tool_calls": [c.__dict__ for c in calls]}
        return TurnResult(text, calls, raw, "STOP")

    @staticmethod
    def _echo(history: list[dict]) -> dict:
        last = history[-1]
        if last["role"] == "user":
            return {"tool_calls": [{"name": "list_files", "args": {}}]}
        files = [f["name"] for f in last["results"][0]["result"].get("files", [])]
        said = next(h["text"] for h in reversed(history) if h["role"] == "user").split("\n\n")[-1]
        return {"text": f"(mock) Bạn vừa nói: “{said}”. Tệp trong phiên: {', '.join(files) or 'chưa có'}."}

    def user_message(self, text, images):
        return {"role": "user", "text": text, "images": len(images)}

    def model_text_message(self, text):
        return {"role": "model", "text": text, "tool_calls": []}

    def tool_results_message(self, results):
        return {"role": "tool", "results": [{"name": c.name, "result": r} for c, r in results]}

    async def quick(self, prompt: str) -> str:
        return prompt.strip().splitlines()[-1][:40]

    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        return "(mock) văn bản chép từ giọng nói"
