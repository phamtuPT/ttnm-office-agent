"""Bộ đánh giá tự động theo mục 8 của đề xuất.

Chạy mỗi yêu cầu mẫu trong eval/cases.json trên một phiên mới với nhà cung cấp/model đang cấu hình, tự đồng ý
mọi xác nhận, rồi chấm đạt/không đạt bằng các kiểm tra trên tệp kết quả. Xuất CSV từng lần chạy + tóm tắt chỉ số:
tỉ lệ hoàn thành, độ chính xác gọi tool, toàn vẹn tệp, độ trễ (token đầu, tổng), số bước.

    cd backend
    python -m eval.run_eval --provider gemini --repeat 3
    python -m eval.run_eval --provider ollama --model qwen3 --only xlsx

Nhóm mở rộng lên ~100 yêu cầu bằng cách thêm vào cases.json (và bộ tạo tệp đầu vào bên dưới nếu cần).
"""
import argparse
import asyncio
import csv
import io
import json
import os

import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _setup_env(storage: Path) -> None:
    # Phải đặt trước khi import app (config được cache)
    os.environ["STORAGE_DIR"] = str(storage)
    os.environ["DATABASE_URL"] = f"sqlite:///{storage}/eval.db"


# ---------- Tệp đầu vào mẫu ----------

def make_inputs() -> dict:
    import openpyxl
    from docx import Document
    from pptx import Presentation

    def xlsx_loi_nhuan():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Lợi nhuận"
        ws.append(["Chi nhánh", "Q1", "Q2", "Q3"])
        for row in [["Hà Nội", 120, -15, 80], ["Đà Nẵng", -40, 35, 60], ["TP.HCM", 200, 180, -20],
                    ["Cần Thơ", 30, -5, 45], ["Hải Phòng", 75, 90, 110]]:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        return "loi-nhuan.xlsx", buf.getvalue()

    def docx_hop_dong():
        doc = Document()
        doc.add_heading("HỢP ĐỒNG DỊCH VỤ", 1)
        for t in ["Hợp đồng ký ngày 15/01/2026 giữa công ty A và khách hàng B.",
                  "Giá trị hợp đồng: 120.000.000 đồng, khách hàng thanh toán trong vòng một thời gian hợp lý.",
                  "Bên cung cấp có trách nhiệm hỗ trợ khách hàng khi cần.",
                  "Hợp đồng có hiệu lực kể từ ngày ký."]:
            doc.add_paragraph(t)
        buf = io.BytesIO()
        doc.save(buf)
        return "hop-dong.docx", buf.getvalue()

    def pptx_gioi_thieu():
        prs = Presentation()
        for title, body in [("Máy lọc nước X", "Nhỏ gọn, tiết kiệm điện"),
                            ("Lợi ích", "Nước sạch, tiết kiệm chi phí, dễ lắp đặt")]:
            s = prs.slides.add_slide(prs.slide_layouts[1])
            s.shapes.title.text = title
            s.placeholders[1].text = body
        buf = io.BytesIO()
        prs.save(buf)
        return "gioi-thieu.pptx", buf.getvalue()

    return {"xlsx_loi_nhuan": xlsx_loi_nhuan, "docx_hop_dong": docx_hop_dong, "pptx_gioi_thieu": pptx_gioi_thieu}


# ---------- Kiểm tra ----------

def check(c: dict, ctx: dict) -> tuple[bool, str]:
    import openpyxl
    from docx import Document
    from docx.oxml.ns import qn
    from openpyxl.utils.cell import range_boundaries
    from pptx import Presentation

    files: dict = ctx["files"]  # tên → đường dẫn bản hiện tại
    created = [n for n in files if n not in ctx["input_names"]]

    def path(name=None, kind=None):
        if name:
            return files.get(name)
        cands = [n for n in created if n.endswith("." + kind)] or [n for n in files if n.endswith("." + kind)]
        return files[cands[0]] if cands else None

    t = c["type"]
    if t == "file_created":
        return any(n.endswith("." + c["kind"]) for n in created), f"tệp mới: {created}"
    if t == "file_changed":
        return ctx["versions"].get(c["file"], 1) > 1, f"phiên bản {ctx['versions'].get(c['file'])}"
    if t == "has_redo":
        return ctx["latest"].get(c["file"], 1) > ctx["versions"].get(c["file"], 1),             f"hiện tại v{ctx['versions'].get(c['file'])}, mới nhất v{ctx['latest'].get(c['file'])}"
    if t == "no_file_changed":
        return all(v == 1 for v in ctx["versions"].values()) and not created, str(ctx["versions"])
    if t == "reply_asks_question":
        return "?" in ctx["reply"], ctx["reply"][:120]

    if t.startswith("xlsx"):
        p = path(c.get("file"), "xlsx")
        if p is None:
            return False, "không có tệp xlsx"
        wb = openpyxl.load_workbook(p)
        sheets = [wb[c["sheet"]]] if c.get("sheet") else wb.worksheets
        cells = [cell for ws in sheets for row in ws.iter_rows() for cell in row]
        if t == "xlsx_any_formula":
            return any(isinstance(x.value, str) and x.value.startswith("=") and c["contains"] in x.value.upper()
                       for x in cells), ""
        if t == "xlsx_chart_count":
            n = sum(len(ws._charts) for ws in wb.worksheets)
            return n >= c["min"], f"{n} biểu đồ"
        if t == "xlsx_contains_text":
            return any(isinstance(x.value, str) and c["text"].lower() in x.value.lower() for x in cells), ""
        if t == "xlsx_cell_equals":
            v = sheets[0][c["ref"]].value
            return v == c["value"], f"{c['ref']}={v}"
        if t == "xlsx_sorted_desc":
            vals = [sheets[0][f"{c['col']}{r}"].value for r in range(c["rows"][0], c["rows"][1] + 1)]
            return vals == sorted(vals, reverse=True), str(vals)
        if t == "xlsx_conditional_or_red":
            ws = sheets[0]
            has_cf = any(True for _ in ws.conditional_formatting)
            red = any((x.font.color is not None and str(x.font.color.rgb or "").upper().endswith(("FF0000", "C00000")))
                      for x in cells if isinstance(x.value, (int, float)) and x.value < 0)
            return has_cf or red, f"định dạng có điều kiện={has_cf}, tô đỏ trực tiếp={red}"
        if t == "xlsx_unchanged_outside":
            orig = openpyxl.load_workbook(ctx["originals"][c["file"]])[c["sheet"]]
            c1, r1, c2, r2 = range_boundaries(c["range"])
            changed = [x.coordinate for x in cells if not (r1 <= x.row <= r2 and c1 <= x.column <= c2)
                       and x.value != orig[x.coordinate].value]
            return not changed, f"ô ngoài vùng bị đổi: {changed[:5]}"

    if t.startswith("docx"):
        p = path(c.get("file"), "docx")
        if p is None:
            return False, "không có tệp docx"
        doc = Document(p)
        text = "\n".join(x.text for x in doc.paragraphs)
        if t == "docx_contains":
            return c["text"] in text, ""
        if t == "docx_not_contains":
            return c["text"].lower() not in text.lower(), ""
        if t == "docx_heading_count":
            n = sum(1 for x in doc.paragraphs if x.style.name.startswith("Heading"))
            return n >= c["min"], f"{n} đề mục"
        if t == "docx_has_revisions_or_comments":
            body = doc.element.body
            n = len(body.findall(".//" + qn("w:ins"))) + len(list(doc.comments))
            return n > 0, f"{n} sửa đổi/nhận xét"

    if t.startswith("pptx"):
        p = path(c.get("file"), "pptx")
        if p is None:
            return False, "không có tệp pptx"
        prs = Presentation(p)
        if t == "pptx_slide_count":
            return len(prs.slides) >= c["min"], f"{len(prs.slides)} slide"
        if t == "pptx_notes_count":
            n = sum(1 for s in prs.slides if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip())
            return n >= c["min"], f"{n} slide có ghi chú"
    return False, f"không biết kiểu kiểm tra {t}"


def integrity(paths: list[Path]) -> bool:
    import openpyxl
    from docx import Document
    from pptx import Presentation
    try:
        for p in paths:
            {"xlsx": openpyxl.load_workbook, "docx": Document, "pptx": Presentation}[p.suffix[1:]](p)
        return True
    except Exception:
        return False


# ---------- Chạy ----------

async def run_case(case: dict, provider, inputs_builders: dict) -> dict:
    from app.agent.loop import TurnStats, run_turn
    from app.agent.prompts import context_block, system_prompt
    from app.db import ChatSession, File, SessionLocal, ToolCallLog
    from app.tools.executor import ToolExecutor
    from app.tools.registry import Selection
    from app.versioning import store

    db = SessionLocal()
    chat = ChatSession()
    db.add(chat)
    db.commit()
    originals, input_names = {}, []
    for key in case.get("inputs", []):
        name, data = inputs_builders[key]()
        f = store.create_file(db, chat.id, name, data)
        originals[name] = store.version_path(f, 1)
        input_names.append(f.name)

    async def yes(_n, _a):
        return True

    history: list[dict] = []
    reply, stats, err = "", TurnStats(), ""
    requests = ([case["setup_request"]] if case.get("setup_request") else []) + [case["request"]]
    started = time.monotonic()
    for i, text in enumerate(requests):
        db.expire_all()
        files = [{"name": f.name, "kind": f.kind, "version": f.current_version}
                 for f in db.query(File).filter_by(session_id=chat.id)]
        sel = case.get("selection") if i == len(requests) - 1 else None
        active = (sel or {}).get("file") or (input_names[0] if input_names else None)
        user_raw = provider.user_message(f"{context_block(files, sel, active, [], [])}\n\n{text}", [])
        out: list = []
        events: list = []

        async def emit(e):
            events.append(e)
        turn_stats = TurnStats() if i < len(requests) - 1 else stats
        ex = ToolExecutor(db, chat.id, yes, Selection.model_validate(sel) if sel else None, turn_id=f"{case['id']}-{i}")
        try:
            await asyncio.wait_for(run_turn(provider=provider, executor=ex, history=history, user_raw=user_raw,
                                            system=system_prompt(text, files, active), emit=emit, max_steps=10,
                                            out=out, stats=turn_stats), 300)
        except Exception as e:  # lỗi model, timeout, quá số bước
            err = f"{type(e).__name__}: {e}"
        history += [user_raw] + [raw for _, _, raw in out]
        reply = next((e["text"] for e in reversed(events) if e["type"] == "message.done"), "")
    duration = int((time.monotonic() - started) * 1000)

    db.expire_all()
    fs = db.query(File).filter_by(session_id=chat.id).all()
    ctx = {"files": {f.name: store.working_path(f) for f in fs}, "versions": {f.name: f.current_version for f in fs},
           "latest": {f.name: max(v.number for v in f.versions) for f in fs},
           "input_names": input_names, "originals": originals, "reply": reply}
    results = [(c, *check(c, ctx)) for c in case["checks"]]
    logs = db.query(ToolCallLog).filter(ToolCallLog.session_id == chat.id,  # mỗi lần chạy là một phiên riêng
                                        ToolCallLog.turn_id == f"{case['id']}-{len(requests) - 1}").all()
    db.close()
    return {
        "id": case["id"], "group": case["group"], "passed": all(ok for _, ok, _ in results) and not err,
        "checks": "; ".join(f"{'✓' if ok else '✗'} {c['type']} {note}".strip() for c, ok, note in results),
        "error": err, "integrity": integrity([store.working_path(f) for f in fs]),
        "steps": stats.steps, "tool_calls": len(logs), "tool_ok": sum(1 for x in logs if x.ok),
        "tools": " ".join(x.name + ("" if x.ok else "✗") for x in sorted(logs, key=lambda x: x.created_at)),
        "first_token_ms": stats.first_token_ms, "duration_ms": duration,
        "input_tokens": stats.input_tokens, "output_tokens": stats.output_tokens, "reply": reply[:300],
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows) or 1
    calls = sum(r["tool_calls"] for r in rows)
    ftt = [r["first_token_ms"] for r in rows if r["first_token_ms"] is not None]
    return {
        "so_lan_chay": len(rows),
        "ti_le_hoan_thanh": round(sum(r["passed"] for r in rows) / n, 3),
        "do_chinh_xac_goi_tool": round(sum(r["tool_ok"] for r in rows) / calls, 3) if calls else None,
        "toan_ven_tep": round(sum(r["integrity"] for r in rows) / n, 3),
        "token_dau_tb_ms": round(sum(ftt) / len(ftt)) if ftt else None,
        "thoi_gian_tb_ms": round(sum(r["duration_ms"] for r in rows) / n),
        "so_buoc_tb": round(sum(r["steps"] for r in rows) / n, 2),
        "token_vao": sum(r["input_tokens"] for r in rows), "token_ra": sum(r["output_tokens"] for r in rows),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Đánh giá Office AI Agent trên bộ yêu cầu mẫu")
    ap.add_argument("--provider", default=os.environ.get("LLM_PROVIDER", "mock"),
                    choices=["gemini", "openai", "ollama", "mock"])
    ap.add_argument("--model", default="", help="Ghi đè model chính của nhà cung cấp")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--only", default="", help="Chỉ chạy case có id chứa chuỗi này")
    ap.add_argument("--out", default=str(HERE / "results"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    storage = Path(tempfile.mkdtemp(prefix="office-eval-"))
    _setup_env(storage)
    from app import runtime_settings, tools  # noqa: F401  (đăng ký tool)
    from app.db import SessionLocal, init_db
    from app.llm import get_provider

    init_db()
    db = SessionLocal()
    cfg = runtime_settings.load(db)
    cfg.provider = args.provider
    if args.model:
        cfg.models[args.provider].agent = args.model
    provider = get_provider(cfg)
    db.close()

    cases = [c for c in json.loads((HERE / "cases.json").read_text(encoding="utf-8")) if args.only in c["id"]]
    builders = make_inputs()
    rows = []

    async def run_all():
        # Một event loop cho cả lượt chạy: client async của SDK gắn với loop đầu tiên nó dùng
        for rep in range(args.repeat):
            for case in cases:
                r = await run_case(case, provider, builders)
                r.update({"run": rep + 1, "provider": provider.name, "model": provider.model})
                rows.append(r)
                print(f"{'ĐẠT ' if r['passed'] else 'TRƯỢT'} {r['id']:<28} {r['duration_ms']:>6} ms {r['steps']:>2} bước  "
                      f"{r['checks']} {r['error']}\n      tool: {r['tools']}", flush=True)

    asyncio.run(run_all())

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with open(out / f"{stamp}-{provider.name}.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summary = summarize(rows)
    (out / f"{stamp}-{provider.name}-tom-tat.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                                encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Kết quả: {out}")



if __name__ == "__main__":
    main()
