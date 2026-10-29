import pytest
from fastapi.testclient import TestClient

from app.api.sus import sus_score
from app.auth import hash_password, verify_password
from app.config import get_settings
from app.main import app


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)


def _register(c, email, password="mat-khau-du-dai"):
    return c.post("/api/auth/register", json={"email": email, "name": email.split("@")[0], "password": password})


def test_password_hashing():
    h = hash_password("bí mật 123")
    assert h.startswith("scrypt$") and "bí mật" not in h
    assert verify_password("bí mật 123", h) and not verify_password("sai", h)
    assert hash_password("x" * 8) != hash_password("x" * 8)  # có muối


def test_single_user_mode_needs_no_login():
    with TestClient(app) as c:
        assert c.get("/api/auth/me").json() == {"enabled": False, "user": None, "can_register": False}
        assert c.post("/api/sessions", json={}).status_code == 200


def test_accounts_isolate_sessions_and_files(auth_on):
    from .conftest import xlsx_bytes
    with TestClient(app) as a, TestClient(app) as b:
        assert a.get("/api/sessions").status_code == 401  # chưa đăng nhập
        ra = _register(a, "an@vi.du")
        assert ra.status_code == 200 and ra.json()["is_admin"]  # người đầu tiên là quản trị
        assert "oa_session" in a.cookies
        rb = _register(b, "binh@vi.du")
        assert rb.status_code == 200 and not rb.json()["is_admin"]
        assert _register(b, "an@vi.du").status_code == 409

        sid = a.post("/api/sessions", json={"kind": "xlsx"}).json()["id"]
        fid = a.post(f"/api/sessions/{sid}/files", files={"file": ("x.xlsx", xlsx_bytes(), "application/octet-stream")}).json()["id"]
        assert [s["id"] for s in a.get("/api/sessions").json()] == [sid]
        assert b.get("/api/sessions").json() == []
        # Người khác không đọc/sửa/xoá được phiên, tệp của mình (404 như không tồn tại)
        assert b.get(f"/api/sessions/{sid}").status_code == 404
        assert b.get(f"/api/files/{fid}/content").status_code == 404
        assert b.put(f"/api/files/{fid}/cells", json={"sheet": "Doanh thu", "cells": [{"ref": "A1", "value": "x"}]}).status_code == 404
        assert b.delete(f"/api/sessions/{sid}").status_code == 404
        with pytest.raises(Exception):
            with b.websocket_connect(f"/ws/sessions/{sid}") as ws:
                ws.receive_json()

        # Cài đặt AI dùng chung: chỉ quản trị viên được đổi
        assert b.put("/api/settings", json={"pii_masking": True}).status_code == 403
        assert a.put("/api/settings", json={"pii_masking": False}).status_code == 200

        assert b.post("/api/auth/logout").status_code == 204
        assert b.get("/api/sessions").status_code == 401
        assert b.post("/api/auth/login", json={"email": "binh@vi.du", "password": "sai-mat-khau"}).status_code == 401
        assert b.post("/api/auth/login", json={"email": "BINH@vi.du", "password": "mat-khau-du-dai"}).status_code == 200


def test_sus_score_and_summary():
    assert sus_score([5, 1] * 5) == 100 and sus_score([1, 5] * 5) == 0 and sus_score([3] * 10) == 50
    with TestClient(app) as c:
        qs = c.get("/api/sus/questions").json()
        assert len(qs["questions"]) == 10 and len(qs["scale"]) == 5
        assert c.post("/api/sus", json={"answers": [4, 2, 4, 1, 5, 2, 4, 2, 4, 1], "participant": "P01"}).json()["score"] == 82.5
        assert c.post("/api/sus", json={"answers": [3] * 10, "participant": "P02"}).json()["score"] == 50
        assert c.post("/api/sus", json={"answers": [6] * 10}).status_code == 422
        s = c.get("/api/sus/summary").json()
        assert s["n"] >= 2 and s["target"] == 70
        csv = c.get("/api/sus/export.csv")
        assert csv.status_code == 200 and "P01" in csv.text and csv.text.startswith("﻿participant")
