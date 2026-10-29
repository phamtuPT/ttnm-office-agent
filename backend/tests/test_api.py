import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

from .conftest import xlsx_bytes

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _client():
    return TestClient(app)


def _session(c):
    return c.post("/api/sessions").json()["id"]


def test_upload_outline_and_chat_over_ws():
    with _client() as c:
        sid = _session(c)
        f = c.post(f"/api/sessions/{sid}/files", files={"file": ("dt.xlsx", xlsx_bytes(), XLSX)}).json()
        assert f["kind"] == "xlsx" and f["current_version"] == 1
        assert c.get(f"/api/files/{f['id']}/outline").json()["sheets"][0]["name"] == "Doanh thu"

        with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
            ws.send_json({"type": "chat", "text": "Xin chào"})
            events = []
            while not events or events[-1]["type"] != "turn.end":
                events.append(ws.receive_json())
            types = [e["type"] for e in events]
            assert types[0] == "turn.start" and "tool.start" in types and "message.done" in types
            assert "dt.xlsx" in next(e for e in events if e["type"] == "message.done")["text"]
            assert ws.receive_json()["type"] == "session.title"

        msgs = c.get(f"/api/sessions/{sid}/messages").json()
        assert [m["role"] for m in msgs] == ["user", "model"]
        assert msgs[0]["text"] == "Xin chào"


def test_rejects_bad_uploads():
    with _client() as c:
        sid = _session(c)
        assert c.post(f"/api/sessions/{sid}/files", files={"file": ("a.txt", b"hi", "text/plain")}).status_code == 400
        assert c.post(f"/api/sessions/{sid}/files", files={"file": ("a.xlsx", b"not zip", XLSX)}).status_code == 400

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("[Content_Types].xml", "<x/>")
            z.writestr("xl/vbaProject.bin", b"macro")
        r = c.post(f"/api/sessions/{sid}/files", files={"file": ("m.xlsx", buf.getvalue(), XLSX)})
        assert r.status_code == 400 and "macro" in r.json()["detail"]


def test_path_traversal_name_is_sanitized():
    with _client() as c:
        sid = _session(c)
        f = c.post(f"/api/sessions/{sid}/files", files={"file": ("../../evil.xlsx", xlsx_bytes(), XLSX)}).json()
        assert f["name"] == "evil.xlsx"


def test_undo_without_changes_conflicts():
    with _client() as c:
        sid = _session(c)
        f = c.post(f"/api/sessions/{sid}/files", files={"file": ("x.xlsx", xlsx_bytes(), XLSX)}).json()
        assert c.post(f"/api/files/{f['id']}/undo").status_code == 409


def test_unknown_session_ws_closes():
    with _client() as c:
        with pytest.raises(WebSocketDisconnect) as e:
            with c.websocket_connect("/ws/sessions/khong-co"):
                pass
        assert e.value.code == 4404


def _chat(ws, payload):
    ws.send_json(payload)
    events = []
    while not events or events[-1]["type"] != "turn.end":
        events.append(ws.receive_json())
    return events


def test_settings_never_return_api_keys():
    with _client() as c:
        r = c.put("/api/settings", json={"provider": "gemini", "api_keys": {"gemini": "AIza-bi-mat-123"},
                                         "models": {"gemini": {"agent": "gemini-3.8-flash"}}})
        assert r.status_code == 200 and "AIza-bi-mat-123" not in r.text and r.json()["has_key"]["gemini"] is True
        g = c.get("/api/settings")
        assert "AIza-bi-mat-123" not in g.text and g.json()["provider"] == "gemini"
        assert c.put("/api/settings", json={"provider": "khong-co"}).status_code == 400
        c.put("/api/settings", json={"provider": "mock", "api_keys": {"gemini": ""}})
        assert c.get("/api/settings").json()["provider"] == "mock"


def test_switching_provider_takes_effect_without_restart():
    with _client() as c:
        sid = _session(c)
        c.put("/api/settings", json={"provider": "openai", "api_keys": {"openai": ""}})
        with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
            ws.send_json({"type": "chat", "text": "xin chào"})
            err = ws.receive_json()
            assert err["type"] == "error" and "openai" in err["message"].lower()
            c.put("/api/settings", json={"provider": "mock"})
            assert "message.done" in [e["type"] for e in _chat(ws, {"type": "chat", "text": "xin chào"})]


def test_image_is_saved_as_asset_and_context_mentions_it():
    import base64
    from .conftest import png_bytes
    with _client() as c:
        sid = _session(c)
        with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
            _chat(ws, {"type": "chat", "text": "Chuyển ảnh thành bảng",
                       "images": [{"mime": "image/png", "data": base64.b64encode(png_bytes()).decode()}]})
        assert c.get(f"/api/sessions/{sid}/assets").json() == ["anh-1.jpg"]
        assert c.get(f"/api/sessions/{sid}/assets/anh-1.jpg").status_code == 200
        assert c.get(f"/api/sessions/{sid}/assets/..%2Fapp.db").status_code == 404


def test_turn_metrics_and_undo_last():
    with _client() as c:
        sid = _session(c)
        with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
            _chat(ws, {"type": "chat", "text": "chào"})
        turns = c.get(f"/api/sessions/{sid}/turns").json()
        assert turns[0]["status"] == "done" and turns[0]["steps"] == 2 and turns[0]["duration_ms"] is not None
        assert c.post(f"/api/sessions/{sid}/undo-last").status_code == 409


def test_pages_endpoint_without_libreoffice(monkeypatch):
    from app.preview import render
    from .conftest import pptx_bytes
    monkeypatch.setattr(render, "available", lambda: False)
    with _client() as c:
        sid = _session(c)
        f = c.post(f"/api/sessions/{sid}/files", files={"file": ("s.pptx", pptx_bytes(), "application/octet-stream")}).json()
        assert c.get(f"/api/files/{f['id']}/pages").json() == {"available": False, "pages": 0}
