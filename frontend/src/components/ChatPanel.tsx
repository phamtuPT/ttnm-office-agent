import { useEffect, useRef, useState } from "react";
import type { ChatItem, Selection } from "../types";
import { TOOL_LABELS } from "../types";
import type { OutgoingImage } from "../useChatSocket";
import { VoiceButton } from "./VoiceButton";

interface Props {
  sessionId: string;
  items: ChatItem[];
  busy: boolean;
  connected: boolean;
  selection: Selection | null;
  onClearSelection: () => void;
  onSend: (text: string, images: OutgoingImage[]) => void;
  onCancel: () => void;
  onError: (msg: string) => void;
}

const MAX_IMAGE_MB = 5;

function describeSelection(s: Selection) {
  if (s.range) return `${s.file} › ${s.sheet}!${s.range}`;
  if (s.paragraphs) return `${s.file} › đoạn ${s.paragraphs.map((i) => i + 1).join(", ")}`;
  if (s.slides) return `${s.file} › slide ${s.slides.map((i) => i + 1).join(", ")}`;
  return s.file;
}

function readAsBase64(file: File): Promise<OutgoingImage> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve({ mime: file.type, data: (r.result as string).split(",")[1] });
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

export function ChatPanel(p: Props) {
  const [text, setText] = useState("");
  const [images, setImages] = useState<{ name: string; img: OutgoingImage }[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [p.items]);

  const addImages = async (files: FileList | null) => {
    for (const f of Array.from(files ?? [])) {
      if (!["image/png", "image/jpeg", "image/webp"].includes(f.type)) {
        p.onError(`${f.name}: chỉ nhận ảnh PNG, JPEG, WEBP`);
        continue;
      }
      if (f.size > MAX_IMAGE_MB * 1024 * 1024) {
        p.onError(`${f.name}: ảnh vượt quá ${MAX_IMAGE_MB} MB`);
        continue;
      }
      const img = await readAsBase64(f);
      setImages((xs) => [...xs, { name: f.name, img }]);
    }
  };

  const submit = () => {
    if (p.busy || (!text.trim() && !images.length)) return;
    p.onSend(text.trim(), images.map((x) => x.img));
    setText("");
    setImages([]);
  };

  return (
    <section className="chat">
      <div className="chat-log" aria-live="polite">
        {p.items.length === 0 && (
          <p className="hint">Tải tệp lên rồi nhập yêu cầu, ví dụ: “Thêm dòng tổng cho cột Doanh thu”.</p>
        )}
        {p.items.map((it, i) => (
          <ChatRow key={i} item={it} />
        ))}
        {p.busy && <div className="typing">Đang xử lý…</div>}
        <div ref={endRef} />
      </div>

      {p.selection && (
        <div className="chip">
          Chỉ sửa trong: <b>{describeSelection(p.selection)}</b>
          <button onClick={p.onClearSelection} aria-label="Bỏ vùng chọn">✕</button>
        </div>
      )}
      {images.length > 0 && (
        <div className="chips">
          {images.map((x, i) => (
            <span className="chip" key={i}>
              🖼 {x.name}
              <button onClick={() => setImages((xs) => xs.filter((_, j) => j !== i))} aria-label="Bỏ ảnh">✕</button>
            </span>
          ))}
        </div>
      )}

      <div className="composer">
        <textarea
          value={text}
          placeholder={p.connected ? "Nhập yêu cầu… (Enter để gửi, Shift+Enter xuống dòng)" : "Đang kết nối…"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          onPaste={(e) => addImages(e.clipboardData.files)}
          rows={3}
        />
        <div className="composer-actions">
          <label className="btn" title="Đính kèm ảnh">
            🖼
            <input type="file" accept="image/png,image/jpeg,image/webp" multiple hidden
              onChange={(e) => { addImages(e.target.files); e.target.value = ""; }} />
          </label>
          <VoiceButton sessionId={p.sessionId} onText={(t) => setText((x) => (x ? x + " " : "") + t)} onError={p.onError} />
          {p.busy ? (
            <button className="btn danger" onClick={p.onCancel}>Dừng</button>
          ) : (
            <button className="btn primary" onClick={submit} disabled={!p.connected}>Gửi</button>
          )}
        </div>
      </div>
    </section>
  );
}

function ChatRow({ item }: { item: ChatItem }) {
  switch (item.kind) {
    case "text":
      return <div className={`msg ${item.role}`}>{item.text}</div>;
    case "tool": {
      const icon = { running: "⏳", ok: "✓", error: "⚠" }[item.status];
      return (
        <details className={`tool ${item.status}`}>
          <summary>
            {icon} {TOOL_LABELS[item.name] ?? item.name}
            {item.status === "error" && item.result?.error ? `: ${String(item.result.error)}` : ""}
          </summary>
          <pre>{JSON.stringify({ args: item.args, result: item.result }, null, 2)}</pre>
        </details>
      );
    }
    case "change":
      return (
        <div className="change">
          ✎ <b>{item.fileName}</b> → phiên bản {item.version}: {item.summary}
        </div>
      );
    case "notice":
      return <div className="notice">{item.text}</div>;
  }
}
