import { useEffect, useRef, useState } from "react";
import { api } from "../api";

/**
 * Nhập yêu cầu bằng giọng nói. Bản chép lời đưa vào ô soạn để người dùng xem/sửa — KHÔNG tự gửi.
 * - Ưu tiên Web Speech API của trình duyệt (Chrome/Edge, tiếng Việt, hiện chữ ngay khi đang nói).
 * - Trình duyệt không hỗ trợ → ghi âm rồi gửi lên máy chủ nhận dạng (Gemini/OpenAI).
 */

type State = "idle" | "listening" | "transcribing";

interface Props {
  sessionId: string;
  onFinal: (text: string) => void; // đoạn đã chốt → nối vào ô soạn
  onInterim: (text: string) => void; // đoạn đang nghe → hiển thị tạm
  onError: (msg: string) => void;
}

const SpeechRecognitionImpl: any =
  typeof window !== "undefined" ? (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition : undefined;

const SPEECH_ERRORS: Record<string, string> = {
  "not-allowed": "Trình duyệt chưa được cấp quyền micro. Hãy bấm biểu tượng ổ khoá trên thanh địa chỉ để cho phép, hoặc gõ yêu cầu.",
  "service-not-allowed": "Trình duyệt chặn dịch vụ nhận dạng giọng nói. Hãy gõ yêu cầu.",
  "no-speech": "Không nghe thấy tiếng nói. Hãy nói gần micro hơn rồi thử lại.",
  "audio-capture": "Không tìm thấy micro trên máy.",
  network: "Mất kết nối tới dịch vụ nhận dạng giọng nói.",
};

export function VoiceButton(p: Props) {
  const [state, setState] = useState<State>("idle");
  const recog = useRef<any>(null);
  const recorder = useRef<MediaRecorder | null>(null);

  useEffect(() => () => recog.current?.abort(), []);

  const startSpeechApi = () => {
    const r = new SpeechRecognitionImpl();
    r.lang = "vi-VN";
    r.interimResults = true;
    r.continuous = true;
    r.onresult = (e: any) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) p.onFinal(res[0].transcript.trim());
        else interim += res[0].transcript;
      }
      p.onInterim(interim);
    };
    r.onerror = (e: any) => {
      if (e.error !== "aborted") p.onError(SPEECH_ERRORS[e.error] ?? `Lỗi nhận dạng giọng nói: ${e.error}`);
    };
    r.onend = () => {
      p.onInterim("");
      setState("idle");
    };
    r.start();
    recog.current = r;
    setState("listening");
  };

  const startRecorder = async () => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      p.onError("Không truy cập được micro. Hãy cấp quyền micro cho trang, hoặc gõ yêu cầu.");
      return;
    }
    const chunks: Blob[] = [];
    const r = new MediaRecorder(stream);
    r.ondataavailable = (e) => chunks.push(e.data);
    r.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      setState("transcribing");
      try {
        const { text } = await api.transcribe(p.sessionId, new Blob(chunks, { type: r.mimeType }));
        if (text) p.onFinal(text);
        else p.onError("Không nhận dạng được nội dung. Hãy thử lại hoặc gõ yêu cầu.");
      } catch (e) {
        p.onError(`Không nhận dạng được giọng nói: ${(e as Error).message}`);
      } finally {
        setState("idle");
      }
    };
    r.start();
    recorder.current = r;
    setState("listening");
  };

  const toggle = () => {
    if (state === "listening") {
      recog.current?.stop();
      if (recorder.current?.state === "recording") recorder.current.stop();
      return;
    }
    if (SpeechRecognitionImpl) startSpeechApi();
    else startRecorder();
  };

  const label = { idle: "🎤", listening: "⏹", transcribing: "…" }[state];
  const title = { idle: "Nói yêu cầu (bấm lần nữa để dừng)", listening: "Đang nghe — bấm để dừng", transcribing: "Đang nhận dạng…" }[state];
  return (
    <button
      className={`btn ${state === "listening" ? "danger pulse" : ""}`}
      title={title}
      aria-label={title}
      aria-pressed={state === "listening"}
      disabled={state === "transcribing"}
      onClick={toggle}
    >
      {label}
    </button>
  );
}
