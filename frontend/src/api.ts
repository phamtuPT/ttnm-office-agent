import type { AppSettings, ChatSession, FileKind, FileVersion, OfficeFile } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `Lỗi ${res.status}`;
    throw new Error(detail);
  }
  return res.json();
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  /** kind: bắt đầu với tệp trống loại đó; bỏ trống = phiên không có tệp (để tải tệp lên). */
  createSession: (kind?: FileKind) => request<ChatSession>("/api/sessions", json("POST", { kind: kind ?? null })),
  listSessions: () => request<ChatSession[]>("/api/sessions"),
  getSession: (sid: string) => request<ChatSession>(`/api/sessions/${sid}`),
  renameSession: (sid: string, title: string) => request<ChatSession>(`/api/sessions/${sid}`, json("PATCH", { title })),
  deleteSession: async (sid: string) => {
    const res = await fetch(`/api/sessions/${sid}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Không xoá được phiên (lỗi ${res.status})`);
  },
  messages: (sid: string) =>
    request<{ id: string; role: "user" | "model"; text: string }[]>(`/api/sessions/${sid}/messages`),
  undoLastRequest: (sid: string) => request<OfficeFile[]>(`/api/sessions/${sid}/undo-last`, { method: "POST" }),
  listFiles: (sid: string) => request<OfficeFile[]>(`/api/sessions/${sid}/files`),
  uploadFile: (sid: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<OfficeFile>(`/api/sessions/${sid}/files`, { method: "POST", body: form });
  },
  fileContentUrl: (fid: string) => `/api/files/${fid}/content`,
  outline: (fid: string) => request<any>(`/api/files/${fid}/outline`),
  pages: (fid: string) => request<{ available: boolean; pages: number; version?: number }>(`/api/files/${fid}/pages`),
  pageUrl: (fid: string, i: number, version: number) => `/api/files/${fid}/pages/${i}.png?v=${version}`,
  thumbnailUrl: (fid: string, version: number) => `/api/files/${fid}/thumbnail.png?v=${version}`,
  versions: (fid: string) => request<FileVersion[]>(`/api/files/${fid}/versions`),
  undo: (fid: string) => request<OfficeFile>(`/api/files/${fid}/undo`, { method: "POST" }),
  redo: (fid: string) => request<OfficeFile>(`/api/files/${fid}/redo`, { method: "POST" }),
  restore: (fid: string, n: number) => request<OfficeFile>(`/api/files/${fid}/restore/${n}`, { method: "POST" }),
  transcribe: (sid: string, audio: Blob) => {
    const form = new FormData();
    form.append("audio", audio, "voice.webm");
    return request<{ text: string }>(`/api/sessions/${sid}/transcribe`, { method: "POST", body: form });
  },
  getSettings: () => request<AppSettings>("/api/settings"),
  saveSettings: (patch: Partial<Omit<AppSettings, "has_key">> & { api_keys?: Record<string, string> }) =>
    request<AppSettings>("/api/settings", json("PUT", patch)),
};
