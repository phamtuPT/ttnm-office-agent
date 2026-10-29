import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { ChatItem, ConfirmRequest, FileDiff, Selection, ServerEvent } from "./types";

interface Handlers {
  onFileChanged: (fileId: string, diff: FileDiff) => void;
  onTitle: (title: string) => void;
  onError: (message: string) => void;
}

export interface OutgoingImage {
  mime: string;
  data: string; // base64, không có tiền tố data:
}

/** Kết nối WebSocket của một phiên chat và chuyển chuỗi sự kiện thành danh sách hiển thị. */
export function useChatSocket(sessionId: string | null, handlers: Handlers) {
  const [items, setItems] = useState<ChatItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmRequest | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const h = useRef(handlers);
  h.current = handlers;

  useEffect(() => {
    if (!sessionId) return;
    let closed = false;
    setItems([]);
    api.messages(sessionId).then((msgs) =>
      setItems(msgs.map((m) => ({ kind: "text", role: m.role, text: m.text }))),
    );

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/sessions/${sessionId}`);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      setBusy(false);
      if (!closed) h.current.onError("Mất kết nối tới máy chủ. Hãy tải lại trang.");
    };
    ws.onmessage = (e) => handle(JSON.parse(e.data) as ServerEvent);
    return () => {
      closed = true;
      ws.close();
    };
  }, [sessionId]);

  const handle = (ev: ServerEvent) => {
    switch (ev.type) {
      case "turn.start":
        setBusy(true);
        break;
      case "turn.end":
        setBusy(false);
        setItems((xs) => xs.map((x) => (x.kind === "text" && x.streaming ? { ...x, streaming: false } : x)));
        break;
      case "turn.cancelled":
        setItems((xs) => [...xs, { kind: "notice", text: "Đã dừng theo yêu cầu." }]);
        break;
      case "message.delta":
        setItems((xs) => {
          const last = xs[xs.length - 1];
          if (last?.kind === "text" && last.role === "model" && last.streaming)
            return [...xs.slice(0, -1), { ...last, text: last.text + ev.text }];
          return [...xs, { kind: "text", role: "model", text: ev.text, streaming: true }];
        });
        break;
      case "message.done":
        setItems((xs) => {
          const last = xs[xs.length - 1];
          const done: ChatItem = { kind: "text", role: "model", text: ev.text };
          return last?.kind === "text" && last.streaming ? [...xs.slice(0, -1), done] : [...xs, done];
        });
        break;
      case "tool.start":
        setItems((xs) => [
          ...xs.map((x) => (x.kind === "text" && x.streaming ? { ...x, streaming: false } : x)),
          { kind: "tool", id: ev.id, name: ev.name, args: ev.args, status: "running" },
        ]);
        break;
      case "tool.result":
      case "tool.error":
        setItems((xs) =>
          xs.map((x) =>
            x.kind === "tool" && x.status === "running" && x.id === ev.id && x.name === ev.name
              ? { ...x, status: ev.type === "tool.result" ? "ok" : "error", result: ev.result }
              : x,
          ),
        );
        break;
      case "file.changed":
        if (ev.summary !== "Không có thay đổi")
          setItems((xs) => [...xs, { kind: "change", fileName: ev.file_name, version: ev.version, summary: ev.summary }]);
        h.current.onFileChanged(ev.file_id, ev.diff);
        break;
      case "confirm.request":
        setConfirm({ id: ev.id, tool: ev.tool, args: ev.args });
        break;
      case "session.title":
        h.current.onTitle(ev.title);
        break;
      case "error":
        h.current.onError(ev.message);
        break;
    }
  };

  const send = useCallback((text: string, images: OutgoingImage[], selection: Selection | null) => {
    wsRef.current?.send(JSON.stringify({ type: "chat", text, images, selection }));
    setItems((xs) => [
      ...xs,
      { kind: "text", role: "user", text: images.length ? `${text}\n[${images.length} ảnh]` : text },
    ]);
  }, []);

  const cancel = useCallback(() => wsRef.current?.send(JSON.stringify({ type: "cancel" })), []);

  const answerConfirm = useCallback((approved: boolean) => {
    setConfirm((c) => {
      if (c) wsRef.current?.send(JSON.stringify({ type: "confirm.response", id: c.id, approved }));
      return null;
    });
  }, []);

  return { items, busy, connected, confirm, send, cancel, answerConfirm };
}
