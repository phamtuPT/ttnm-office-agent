import type { ChatSession, OfficeFile } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Lỗi ${res.status}`);
  }
  return res.json();
}

export const api = {
  createSession: () => request<ChatSession>("/api/sessions", { method: "POST" }),
  listSessions: () => request<ChatSession[]>("/api/sessions"),
  messages: (sid: string) =>
    request<{ id: string; role: "user" | "model"; text: string }[]>(`/api/sessions/${sid}/messages`),
  listFiles: (sid: string) => request<OfficeFile[]>(`/api/sessions/${sid}/files`),
  uploadFile: (sid: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<OfficeFile>(`/api/sessions/${sid}/files`, { method: "POST", body: form });
  },
  fileContentUrl: (fid: string) => `/api/files/${fid}/content`,
  outline: (fid: string) => request<any>(`/api/files/${fid}/outline`),
  undo: (fid: string) => request<OfficeFile>(`/api/files/${fid}/undo`, { method: "POST" }),
  redo: (fid: string) => request<OfficeFile>(`/api/files/${fid}/redo`, { method: "POST" }),
  transcribe: (sid: string, audio: Blob) => {
    const form = new FormData();
    form.append("audio", audio, "voice.webm");
    return request<{ text: string }>(`/api/sessions/${sid}/transcribe`, { method: "POST", body: form });
  },
};
