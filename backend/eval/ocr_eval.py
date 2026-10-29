"""Bộ ảnh có nhãn và đo độ chính xác đọc ảnh (đề xuất mục 7 và 8.3).

Chỉ số: CER (tỉ lệ lỗi ký tự, mục tiêu ≤ 5% với ảnh rõ nét) và độ chính xác trích bảng (ô đúng giá trị + vị trí,
mục tiêu ≥ 90%). Đo trên vision LLM đang cấu hình (cùng đường agent đọc ảnh trong ứng dụng) và Tesseract nếu có.

    python -m eval.ocr_eval build                 # dựng lại 50 ảnh tổng hợp + nhãn trong eval/ocr_dataset/
    python -m eval.ocr_eval run --provider gemini [--engine tesseract] [--limit 10]

Ảnh tổng hợp gồm 4 loại (hoá đơn, bảng giá, công văn, ảnh chụp bảng tính) × 5 điều kiện chụp (rõ nét, tối/tương phản
thấp, nghiêng, mờ, nhiễu + bóng đổ). Nhóm có thể thêm ảnh chụp thật: bỏ ảnh vào ocr_dataset/ và thêm một dòng vào
labels.json theo cùng định dạng ({"file", "kind", "condition", "text", "table"}).
"""
import argparse
import asyncio
import csv
import json
import random
import re
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HERE = Path(__file__).resolve().parent
DATA = HERE / "ocr_dataset"
CONDITIONS = ["ro-net", "toi", "nghieng", "mo", "nhieu-bong"]
KINDS = {"hoa-don": 15, "bang-gia": 15, "cong-van": 10, "bang-tinh": 10}

PRODUCTS = ["Máy lọc nước", "Nồi chiên không dầu", "Quạt điều hoà", "Bàn là hơi nước", "Ấm siêu tốc", "Máy xay sinh tố",
            "Đèn bàn LED", "Bình giữ nhiệt", "Nồi cơm điện", "Máy sấy tóc", "Bếp từ đôi", "Lò vi sóng"]
COMPANIES = ["Công ty TNHH Minh Phát", "Công ty CP Thương mại Đông Á", "Cửa hàng Điện máy Hưng Thịnh",
             "Công ty TNHH Kỹ thuật Sao Việt"]
PEOPLE = ["Nguyễn Văn An", "Trần Thị Bích", "Lê Hoàng Nam", "Phạm Minh Tuấn", "Võ Thị Mai", "Đặng Quốc Bảo"]
LETTER = ["Căn cứ kế hoạch công tác năm 2026 của đơn vị,", "Phòng Hành chính thông báo lịch họp giao ban tháng 11",
          "vào lúc 8 giờ 30 ngày 05/11/2026 tại phòng họp tầng 3.", "Đề nghị các phòng ban cử đại diện tham dự đầy đủ,",
          "chuẩn bị báo cáo kết quả thực hiện nhiệm vụ quý III", "và đề xuất kế hoạch quý IV gửi về trước ngày 03/11/2026.",
          "Mọi thắc mắc xin liên hệ chị Võ Thị Mai, số máy lẻ 215."]


def _money(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def _font(size: int, bold: bool = False):
    from app.preview.thumbnail import _font as font
    return font(size, bold)


def _content(kind: str, rnd: random.Random) -> dict:
    if kind == "hoa-don":
        items = rnd.sample(PRODUCTS, 4)
        rows = [["Sản phẩm", "SL", "Đơn giá", "Thành tiền"]]
        total = 0
        for it in items:
            qty, price = rnd.randint(1, 5), rnd.choice([350, 490, 820, 1250, 1890, 3200, 4500]) * 1000
            total += qty * price
            rows.append([it, str(qty), _money(price), _money(qty * price)])
        head = [rnd.choice(COMPANIES), f"HOÁ ĐƠN BÁN HÀNG số {rnd.randint(1000, 9999)}",
                f"Ngày {rnd.randint(1, 28):02d}/{rnd.randint(1, 12):02d}/2026"]
        return {"head": head, "table": rows, "widths": [0.42, 0.1, 0.23, 0.25], "foot": [f"Tổng cộng: {_money(total)} đồng"]}
    if kind == "bang-gia":
        rows = [["STT", "Tên hàng", "Đơn vị", "Giá bán"]]
        for i, it in enumerate(rnd.sample(PRODUCTS, 6), 1):
            rows.append([str(i), it, rnd.choice(["Cái", "Bộ", "Chiếc"]), _money(rnd.randint(15, 520) * 10000)])
        return {"head": ["BẢNG GIÁ THAM KHẢO", f"Áp dụng từ {rnd.randint(1, 28):02d}/10/2026"], "table": rows, "widths": [0.09, 0.47, 0.18, 0.26], "foot": []}
    if kind == "cong-van":
        lines = LETTER[:]
        rnd.shuffle(lines[1:4])
        return {"head": [rnd.choice(COMPANIES), "THÔNG BÁO"], "table": None,
                "body": lines, "foot": [f"Người ký: {rnd.choice(PEOPLE)}"]}
    rows = [["Mã NV", "Họ tên", "Phòng", "Lương"]]
    for i, p in enumerate(rnd.sample(PEOPLE, 5), 1):
        rows.append([f"NV{i:02d}", p, rnd.choice(["Kế toán", "Kỹ thuật", "Kinh doanh"]),
                     _money(rnd.randint(12, 30) * 1000000)])
    return {"head": [], "table": rows, "widths": [0.15, 0.39, 0.22, 0.24], "foot": [], "sheet": True}


def _render(c: dict) -> Image.Image:
    W, H = 1240, 900
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    y = 50
    for i, line in enumerate(c.get("head", [])):
        f = _font(40 if i == 1 else 30, bold=i < 2)
        d.text((60, y), line, fill=(20, 20, 20), font=f)
        y += f.size + 18
    for line in c.get("body", []):
        f = _font(30)
        d.text((60, y), line, fill=(25, 25, 25), font=f)
        y += f.size + 16
    if c.get("table"):
        rows = c["table"]
        cols = len(rows[0])
        widths = c.get("widths") or [1 / cols] * cols
        x0, cw = 60, W - 120
        rh, f = 58, _font(28)
        y += 12
        if c.get("sheet"):  # ảnh chụp bảng tính: hàng tiêu đề cột A, B, C
            d.rectangle([x0, y, x0 + cw, y + 40], fill=(241, 243, 244))
            x = x0
            for j in range(cols):
                d.text((x + 10, y + 6), "ABCD"[j], fill=(95, 99, 104), font=_font(24))
                x += widths[j] * cw
            y += 40
        for i, row in enumerate(rows):
            x = x0
            if i == 0:
                d.rectangle([x0, y, x0 + cw, y + rh], fill=(232, 240, 254) if c.get("sheet") else (235, 235, 235))
            for j, cell in enumerate(row):
                w = widths[j] * cw
                d.rectangle([x, y, x + w, y + rh], outline=(150, 150, 150), width=2)
                d.text((x + 12, y + 14), cell, fill=(20, 20, 20), font=_font(28, bold=i == 0))
                x += w
            y += rh
        y += 24
    for line in c.get("foot", []):
        f = _font(32, bold=True)
        d.text((60, y), line, fill=(20, 20, 20), font=f)
        y += f.size + 14
    return img.crop((0, 0, W, min(H, y + 50)))


def _degrade(img: Image.Image, cond: str, rnd: random.Random) -> Image.Image:
    if cond == "toi":
        img = ImageEnhance.Brightness(img).enhance(0.55)
        img = ImageEnhance.Contrast(img).enhance(0.6)
    elif cond == "nghieng":
        img = img.rotate(rnd.choice([-6, -4, 3, 5]), expand=True, fillcolor=(205, 200, 190))
    elif cond == "mo":
        img = img.filter(ImageFilter.GaussianBlur(1.6))
    elif cond == "nhieu-bong":
        w, h = img.size
        shade = Image.linear_gradient("L").resize((w, h)).point(lambda v: 255 - v // 3)
        img = Image.composite(img, Image.new("RGB", img.size, (90, 85, 80)), shade)
        noise = Image.effect_noise((w, h), 28).convert("RGB")
        img = Image.blend(img, noise, 0.12)
    return img


def label_text(c: dict) -> str:
    lines = list(c.get("head", [])) + list(c.get("body", []))
    if c.get("sheet"):  # ảnh chụp bảng tính có hàng tên cột A, B, C, D
        lines.append(" ".join("ABCD"[:len(c["table"][0])]))
    for row in c.get("table") or []:
        lines.append(" ".join(row))
    return "\n".join(lines + list(c.get("foot", [])))


def build() -> list[dict]:
    DATA.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(2026)
    labels = []
    for kind, count in KINDS.items():
        for i in range(count):
            cond = CONDITIONS[i % len(CONDITIONS)]
            c = _content(kind, rnd)
            img = _degrade(_render(c), cond, rnd)
            name = f"{kind}-{i + 1:02d}-{cond}.jpg"
            img.convert("RGB").save(DATA / name, "JPEG", quality=82)
            labels.append({"file": name, "kind": kind, "condition": cond, "text": label_text(c),
                           "table": c.get("table")})
    (DATA / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return labels


# ── Đo ──────────────────────────────────────────────────────────────────────────────────────────────────────

PROMPT_TEXT = ("Chép lại CHÍNH XÁC toàn bộ chữ trong ảnh theo thứ tự đọc, mỗi dòng một dòng; bảng thì mỗi hàng một dòng, "
               "các ô cách nhau một dấu cách. Chỉ trả về phần chữ, không giải thích, không dùng Markdown.")
PROMPT_TABLE = ("Trích bảng trong ảnh thành JSON: một mảng các hàng, mỗi hàng là mảng chuỗi (giữ nguyên dấu chấm phân cách "
                "hàng nghìn, gồm cả hàng tiêu đề). Chỉ trả về JSON.")


def _norm(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFC", s.replace("```json", "").replace("```", "")).strip()


def _parse_table(s: str) -> list[list[str]]:
    m = re.search(r"\[\s*\[.*\]\s*\]", s, re.S)
    try:
        return [[str(x) for x in row] for row in json.loads(m.group(0))] if m else []
    except (json.JSONDecodeError, TypeError):
        return []


async def _ask(provider, prompt: str, image: bytes) -> str:
    async def ignore(_t):
        return None
    history = [provider.user_message(prompt, [(image, "image/jpeg")])]
    result = await provider.stream_turn(history, "Bạn đọc ảnh tài liệu tiếng Việt chính xác từng ký tự.", [], ignore)
    return result.text


def run(provider_name: str, engine: str, limit: int | None) -> dict:
    from app.media import ocr

    labels = json.loads((DATA / "labels.json").read_text(encoding="utf-8"))[:limit]
    rows = []

    async def go():
        provider = None
        if engine == "llm":
            from app import runtime_settings
            from app.db import SessionLocal, init_db
            from app.llm import get_provider
            init_db()
            with SessionLocal() as db:
                cfg = runtime_settings.load(db)
            cfg.provider = provider_name
            provider = get_provider(cfg)
        for lab in labels:
            img = (DATA / lab["file"]).read_bytes()
            started = time.monotonic()
            if engine == "tesseract":
                text = ocr.ocr(DATA / lab["file"])
                table = None
            else:
                text = _norm(await _ask(provider, PROMPT_TEXT, img))
                table = _parse_table(await _ask(provider, PROMPT_TABLE, img)) if lab["table"] else None
            row = {"file": lab["file"], "kind": lab["kind"], "condition": lab["condition"],
                   "cer": round(ocr.cer(lab["text"], text), 4),
                   "table_acc": round(ocr.table_cell_accuracy(lab["table"], table), 4) if table is not None else "",
                   "ms": int((time.monotonic() - started) * 1000)}
            rows.append(row)
            print(f"{row['file']:<34} CER {row['cer']:.1%}  bảng {row['table_acc'] if row['table_acc'] == '' else format(row['table_acc'], '.0%')}",
                  flush=True)

    asyncio.run(go())

    def avg(xs):
        xs = [x for x in xs if x != ""]
        return round(sum(xs) / len(xs), 4) if xs else None

    clear = [r for r in rows if r["condition"] == "ro-net"]
    summary = {
        "engine": engine if engine == "tesseract" else provider_name, "images": len(rows),
        "cer_all": avg([r["cer"] for r in rows]), "cer_clear": avg([r["cer"] for r in clear]),
        "clear_under_5pct": sum(r["cer"] <= 0.05 for r in clear) / max(len(clear), 1),
        "table_accuracy": avg([r["table_acc"] for r in rows]),
        "cer_by_condition": {c: avg([r["cer"] for r in rows if r["condition"] == c]) for c in CONDITIONS},
        "cer_by_kind": {k: avg([r["cer"] for r in rows if r["kind"] == k]) for k in KINDS},
    }
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with open(out / f"{stamp}-ocr-{summary['engine']}.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (out / f"{stamp}-ocr-{summary['engine']}-tom-tat.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["build", "run"])
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--engine", choices=["llm", "tesseract"], default="llm")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.action == "build":
        print(f"Đã dựng {len(build())} ảnh trong {DATA}")
    else:
        print(json.dumps(run(a.provider, a.engine, a.limit), ensure_ascii=False, indent=2))
