"""Bộ câu lệnh giọng nói và đo lỗi nhận dạng (đề xuất mục 10: 10–15 câu lệnh + bản chép chuẩn).

    python -m eval.voice_eval synth            # tạo bản ghi tổng hợp (Gemini TTS, 2 giọng) → voice_dataset/tts/
    python -m eval.voice_eval run              # chép lời mọi bản ghi (tổng hợp + recordings/) → WER, CER

Đo đường chép lời dự phòng phía máy chủ (POST /api/transcribe → provider.transcribe), dùng khi trình duyệt không có
Web Speech API. Bản tổng hợp chỉ là mốc ban đầu; số liệu cho báo cáo lấy từ bản ghi thật của người dùng trong
recordings/ (xem README trong đó).
"""
import argparse
import asyncio
import csv
import json
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HERE = Path(__file__).resolve().parent
DATA = HERE / "voice_dataset"
VOICES = {"nu": "Kore", "nam": "Puck"}
TTS_MODEL = "gemini-3.8-flash-tts"
MIME = {".wav": "audio/wav", ".webm": "audio/webm", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}


def commands() -> dict:
    return {c["id"]: c for c in json.loads((DATA / "commands.json").read_text(encoding="utf-8"))}


def synth() -> int:
    from google import genai
    from google.genai import errors, types

    from app.config import get_settings

    client = genai.Client(api_key=get_settings().gemini_api_key)
    out = DATA / "tts"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in commands().values():
        for who, voice in VOICES.items():
            path = out / f"{c['id']}-tts-{who}.wav"
            if path.exists():
                continue
            for attempt in range(5):
                try:
                    resp = client.models.generate_content(
                        model=TTS_MODEL,
                        contents=c["text"],  # chỉ câu lệnh: hướng dẫn kèm theo sẽ bị đọc thành tiếng
                        config=types.GenerateContentConfig(
                            response_modalities=["AUDIO"],
                            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
                    break
                except errors.ClientError as e:  # 429: model TTS giới hạn ~10 lượt/phút
                    if e.code != 429 or attempt == 4:
                        raise
                    time.sleep(30)
            time.sleep(6.5)
            pcm = resp.candidates[0].content.parts[0].inline_data.data  # PCM 16-bit mono 24 kHz
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                w.writeframes(pcm)
            n += 1
            print(f"{path.name}: {len(pcm) / 48000:.1f} s", flush=True)
    return n


def run(provider_name: str) -> dict:
    from app import runtime_settings
    from app.db import SessionLocal, init_db
    from app.llm import get_provider
    from app.media.ocr import cer, wer

    cmds = commands()
    files = sorted(p for d in ("tts", "recordings") if (DATA / d).exists() for p in (DATA / d).iterdir()
                   if p.suffix.lower() in MIME and p.stem.split("-")[0] in cmds)
    if not files:
        raise SystemExit("Chưa có bản ghi: chạy `synth` hoặc thêm bản ghi vào voice_dataset/recordings/")
    init_db()
    with SessionLocal() as db:
        cfg = runtime_settings.load(db)
    cfg.provider = provider_name
    provider = get_provider(cfg)
    rows = []

    async def go():
        for p in files:
            ref = cmds[p.stem.split("-")[0]]["text"]
            started = time.monotonic()
            hyp = await provider.transcribe(p.read_bytes(), MIME[p.suffix.lower()])
            rows.append({"file": p.name, "source": p.parent.name, "reference": ref, "transcript": hyp,
                         "wer": round(wer(ref, hyp), 4), "cer": round(cer(ref.lower(), hyp.lower()), 4),
                         "ms": int((time.monotonic() - started) * 1000)})
            print(f"{p.name:<26} WER {rows[-1]['wer']:.0%}  {hyp}", flush=True)

    asyncio.run(go())

    def avg(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    summary = {"provider": provider_name, "recordings": len(rows),
               "wer_all": avg([r["wer"] for r in rows]), "cer_all": avg([r["cer"] for r in rows]),
               "exact_sentences": sum(r["wer"] == 0 for r in rows) / len(rows),
               "by_source": {s: {"n": len(xs), "wer": avg([r["wer"] for r in xs])}
                             for s in ("tts", "recordings") if (xs := [r for r in rows if r["source"] == s])},
               "avg_ms": avg([r["ms"] for r in rows])}
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with open(out / f"{stamp}-voice-{provider_name}.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (out / f"{stamp}-voice-{provider_name}-tom-tat.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                                      encoding="utf-8")
    return summary


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["synth", "run"])
    ap.add_argument("--provider", default="gemini")
    a = ap.parse_args()
    if a.action == "synth":
        print(f"Đã tạo {synth()} bản ghi tổng hợp")
    else:
        print(json.dumps(run(a.provider), ensure_ascii=False, indent=2))
