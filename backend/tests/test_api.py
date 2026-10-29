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
