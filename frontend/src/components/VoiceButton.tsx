import { useRef, useState } from "react";
import { api } from "../api";

/** Nhấn để ghi âm, nhấn lần nữa để dừng. Văn bản nhận dạng được đưa vào ô nhập để người dùng sửa trước khi gửi. */
export function VoiceButton(p: { sessionId: string; onText: (t: string) => void; onError: (m: string) => void }) {
  const [state, setState] = useState<"idle" | "recording" | "transcribing">("idle");
  const rec = useRef<MediaRecorder | null>(null);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const r = new MediaRecorder(stream);
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("transcribing");
        try {
          const { text } = await api.transcribe(p.sessionId, new Blob(chunks, { type: r.mimeType }));
          if (text) p.onText(text);
        } catch (e) {
          p.onError(`Không nhận dạng được giọng nói: ${(e as Error).message}`);
        } finally {
          setState("idle");
        }
      };
      r.start();
      rec.current = r;
      setState("recording");
    } catch {
      p.onError("Không truy cập được micro. Hãy cấp quyền micro cho trang.");
    }
  };

  const label = { idle: "🎤", recording: "⏹", transcribing: "…" }[state];
  const title = { idle: "Nói yêu cầu", recording: "Dừng ghi âm", transcribing: "Đang nhận dạng" }[state];
  return (
    <button
      className={`btn ${state === "recording" ? "danger" : ""}`}
      title={title}
      aria-label={title}
      disabled={state === "transcribing"}
      onClick={() => (state === "recording" ? rec.current?.stop() : start())}
    >
      {label}
    </button>
  );
}
