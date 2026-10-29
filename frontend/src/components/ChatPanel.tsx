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
  activeFile: string | null;
  selection: Selection | null;
  onClearSelection: () => void;
  onSend: (text: string, images: OutgoingImage[]) => void;
  onCancel: () => void;
  onOpenFile: (fileId: string) => void;
  onError: (msg: string) => void;
}

const MAX_IMAGE_MB = 10;
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/heic", "image/gif"];

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
  const [interim, setInterim] = useState("");
  const [images, setImages] = useState<{ name: string; url: string; img: OutgoingImage }[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [p.items]);

  const addImages = async (files: FileList | null) => {
    for (const f of Array.from(files ?? [])) {
      if (!IMAGE_TYPES.includes(f.type)) {
        p.onError(`${f.name}: chỉ nhận ảnh PNG, JPEG, WEBP, HEIC, GIF`);
        continue;
      }
      if (f.size > MAX_IMAGE_MB * 1024 * 1024) {
        p.onError(`${f.name}: ảnh vượt quá ${MAX_IMAGE_MB} MB`);
        continue;
      }
      const img = await readAsBase64(f);
      setImages((xs) => [...xs, { name: f.name, url: URL.createObjectURL(f), img }]);
    }
  };

  const submit = () => {
    if (p.busy || (!text.trim() && !images.length)) return;
    p.onSend(text.trim(), images.map((x) => x.img));
    setText("");
    setImages([]);
  };

  return (
    <section className="chat" aria-label="Hội thoại">
      <div className="chat-log" aria-live="polite">
        {p.items.length === 0 && (
          <div className="hint">
            <p>Giao việc bằng lời, ví dụ:</p>
            <ul>
              <li>“Tạo bảng doanh thu 12 tháng, có dòng tổng và biểu đồ cột”</li>
              <li>Kéo chọn B2:D10 rồi gõ “tô đỏ các giá trị âm”</li>
              <li>Gửi ảnh hoá đơn kèm “chuyển thành bảng Excel và tính tổng”</li>
            </ul>
          </div>
        )}
        {p.items.map((it, i) => (
          <ChatRow key={i} item={it} onOpenFile={p.onOpenFile} />
        ))}
        {p.busy && <div className="typing">Đang xử lý…</div>}
        <div ref={endRef} />
      </div>

      <div className="context-chips">
        {p.activeFile && !p.selection && (
          <span className="chip muted" title="Không nói tệp nào thì trợ lý làm trên tệp đang mở">Tệp đang mở: <b>{p.activeFile}</b></span>
        )}
        {p.selection && (
          <span className="chip">
            Chỉ sửa trong: <b>{describeSelection(p.selection)}</b>
            <button onClick={p.onClearSelection} aria-label="Bỏ vùng chọn">✕</button>
          </span>
        )}
        {images.map((x, i) => (
          <span className="chip img" key={i}>
            <img src={x.url} alt="" />
            {x.name}
            <button onClick={() => setImages((xs) => xs.filter((_, j) => j !== i))} aria-label={`Bỏ ảnh ${x.name}`}>✕</button>
          </span>
        ))}
      </div>

      <div className="composer">
        <textarea
          ref={inputRef}
          value={text}
          placeholder={p.connected ? "Nhập hoặc nói yêu cầu… (Enter để gửi, Shift+Enter xuống dòng)" : "Đang kết nối…"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          onPaste={(e) => addImages(e.clipboardData.files)}
          rows={3}
          aria-label="Yêu cầu"
        />
        {interim && <div className="interim" aria-live="polite">🎤 {interim}</div>}
        <div className="composer-actions">
          <label className="btn" title="Đính kèm ảnh (hoặc dán ảnh vào ô soạn)">
            🖼
            <input type="file" accept={IMAGE_TYPES.join(",")} multiple hidden
              onChange={(e) => { addImages(e.target.files); e.target.value = ""; }} />
          </label>
          <VoiceButton
            sessionId={p.sessionId}
            onFinal={(t) => { setText((x) => (x ? x.trimEnd() + " " : "") + t); inputRef.current?.focus(); }}
            onInterim={setInterim}
            onError={p.onError}
          />
          <span className="spacer" />
          {p.busy ? (
            <button className="btn danger" onClick={p.onCancel}>Dừng</button>
          ) : (
            <button className="btn primary" onClick={submit} disabled={!p.connected || (!text.trim() && !images.length)}>Gửi</button>
          )}
        </div>
      </div>
    </section>
  );
}

function ChatRow({ item, onOpenFile }: { item: ChatItem; onOpenFile: (id: string) => void }) {
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
        <button className="change" onClick={() => onOpenFile(item.fileId)} title="Mở tệp để xem thay đổi">
          ✎ <b>{item.fileName}</b> → phiên bản {item.version}: {item.summary}
        </button>
      );
    case "notice":
      return <div className="notice">{item.text}</div>;
  }
}
