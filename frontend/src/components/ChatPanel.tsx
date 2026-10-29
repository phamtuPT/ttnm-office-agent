import { Check, ChevronRight, FilePen, ImagePlus, LoaderCircle, Mic, SendHorizontal, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ChatItem, Selection } from "../types";
import { TOOL_LABELS } from "../types";
import type { OutgoingImage } from "../useChatSocket";
import { Markdown } from "./Markdown";
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

/** Một ô Excel đơn lẻ chỉ là vị trí con trỏ (điểm neo), không giới hạn vùng trợ lý được sửa. */
export function isAnchor(s: Selection) {
  if (!s.range) return false;
  const [a, b] = s.range.replaceAll("$", "").toUpperCase().split(":");
  return !b || a === b;
}

export function describeSelection(s: Selection) {
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

type ToolItem = Extract<ChatItem, { kind: "tool" }>;
type Block = { kind: "tools"; items: ToolItem[] } | ChatItem;

/** Gom các bước tool liên tiếp thành một khối terminal. */
export function toBlocks(items: ChatItem[]): Block[] {
  const out: Block[] = [];
  for (const it of items) {
    const last = out[out.length - 1];
    if (it.kind === "tool" && last?.kind === "tools") last.items.push(it);
    else if (it.kind === "tool") out.push({ kind: "tools", items: [it] });
    else out.push(it);
  }
  return out;
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

  const canSend = p.connected && !p.busy && (text.trim().length > 0 || images.length > 0);
  const submit = () => {
    if (!canSend) return;
    p.onSend(text.trim(), images.map((x) => x.img));
    setText("");
    setImages([]);
  };

  return (
    <section className="chat" aria-label="Hội thoại">
      <div className="chat-log" aria-live="polite">
        {p.items.length === 0 && (
          <div className="chat-empty">
            <h2>Bạn cần làm gì với tệp?</h2>
            <p>Gõ, nói hoặc dán ảnh. Trợ lý nêu kế hoạch, làm trực tiếp trên tệp đang mở và báo lại chỗ đã sửa. Muốn sửa đúng một vùng thì chọn vùng đó trên khung xem trước trước khi gửi.</p>
          </div>
        )}
        {toBlocks(p.items).map((b, i) =>
          b.kind === "tools" ? <ToolLog key={i} items={b.items} /> : <ChatRow key={i} item={b} onOpenFile={p.onOpenFile} />,
        )}
        {p.busy && !p.items.some((x) => x.kind === "text" && x.streaming) && <div className="notice">Đang xử lý…</div>}
        <div ref={endRef} />
      </div>

      <div className="context-chips">
        {p.activeFile && !p.selection && (
          <span className="chip muted" title="Không nói tệp nào thì trợ lý làm trên tệp đang mở">Tệp đang mở: <b>{p.activeFile}</b></span>
        )}
        {p.selection && (isAnchor(p.selection) ? (
          <span className="chip muted" title="Một ô chỉ là vị trí bắt đầu, trợ lý vẫn được ghi ra các ô khác. Kéo chọn nhiều ô để giới hạn vùng sửa.">
            Ô đang chọn: <b>{describeSelection(p.selection)}</b>
            <button onClick={p.onClearSelection} aria-label="Bỏ ô đang chọn"><X size={14} aria-hidden /></button>
          </span>
        ) : (
          <span className="chip" title="Trợ lý chỉ được sửa trong vùng này">
            Chỉ sửa trong: <b>{describeSelection(p.selection)}</b>
            <button onClick={p.onClearSelection} aria-label="Bỏ vùng chọn"><X size={14} aria-hidden /></button>
          </span>
        ))}
        {images.map((x, i) => (
          <span className="chip img" key={i}>
            <img src={x.url} alt="" />
            {x.name}
            <button onClick={() => setImages((xs) => xs.filter((_, j) => j !== i))} aria-label={`Bỏ ảnh ${x.name}`}><X size={14} aria-hidden /></button>
          </span>
        ))}
      </div>

      <div className="composer">
        <textarea
          ref={inputRef}
          value={text}
          placeholder={p.connected ? "Nhập hoặc nói yêu cầu…" : "Đang kết nối tới máy chủ…"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          onPaste={(e) => addImages(e.clipboardData.files)}
          rows={2}
          aria-label="Yêu cầu"
        />
        {interim && <div className="interim" aria-live="polite"><Mic size={14} aria-hidden /> {interim}</div>}
        <div className="composer-actions">
          <label className="btn icon ghost" title="Đính kèm ảnh (hoặc dán ảnh vào ô soạn)">
            <ImagePlus size={18} aria-hidden />
            <span className="sr-only">Đính kèm ảnh</span>
            <input type="file" accept={IMAGE_TYPES.join(",")} multiple hidden
              onChange={(e) => { addImages(e.target.files); e.target.value = ""; }} />
          </label>
          <VoiceButton
            sessionId={p.sessionId}
            onFinal={(t) => { setText((x) => (x ? x.trimEnd() + " " : "") + t); inputRef.current?.focus(); }}
            onInterim={setInterim}
            onError={p.onError}
          />
          <span className="hint">Enter gửi · Shift+Enter xuống dòng</span>
          <span className="spacer" />
          {p.busy ? (
            <button className="btn danger" onClick={p.onCancel}><Square size={14} aria-hidden /> Dừng</button>
          ) : (
            <button className="btn solid" onClick={submit} disabled={!canSend}><SendHorizontal size={16} aria-hidden /> Gửi</button>
          )}
        </div>
      </div>
    </section>
  );
}

function ToolLog({ items }: { items: ToolItem[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="term" role="log" aria-label="Các bước trợ lý đã làm">
      <div className="term-head"><i /><i /><i /> <span>công cụ · {items.length} bước</span></div>
      {items.map((t, i) => {
        const mark = {
          running: <LoaderCircle size={14} className="run spin" aria-label="đang chạy" />,
          ok: <Check size={14} className="ok" aria-label="xong" />,
          error: <X size={14} className="err" aria-label="lỗi" />,
        }[t.status];
        return (
          <div key={i}>
            <button className="term-line" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
              <ChevronRight size={14} className="prompt" aria-hidden /> {t.name} {mark}{" "}
              <span className="lbl">{TOOL_LABELS[t.name] ?? ""}</span>
              {t.status === "error" && t.result?.error ? <span className="err"> — {String(t.result.error)}</span> : null}
            </button>
            {open === i && <pre>{JSON.stringify({ args: t.args, result: t.result }, null, 2)}</pre>}
          </div>
        );
      })}
    </div>
  );
}

function ChatRow({ item, onOpenFile }: { item: ChatItem; onOpenFile: (id: string) => void }) {
  switch (item.kind) {
    case "text": {
      if (item.role === "user") return <div className="msg user">{item.text}</div>;
      // Dòng kế hoạch ① … → ② … hiển thị tách riêng
      const [first, ...rest] = item.text.split("\n");
      const isPlan = /^\s*①/.test(first);
      return (
        <div className={`msg model md ${item.streaming ? "cursor" : ""}`}>
          {isPlan && <div className="plan"><Markdown text={first} inline /></div>}
          <Markdown text={isPlan ? rest.join("\n") : item.text} />
        </div>
      );
    }
    case "change":
      return (
        <button className="change" onClick={() => onOpenFile(item.fileId)} title="Mở tệp để xem thay đổi">
          <FilePen size={16} aria-hidden /><span><b>{item.fileName}</b> · v{item.version} — {item.summary}</span>
        </button>
      );
    case "notice":
      return <div className="notice">{item.text}</div>;
    default:
      return null;
  }
}
