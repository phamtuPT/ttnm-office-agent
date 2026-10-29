import { useEffect, useState } from "react";
import type { FileKind } from "./types";

/** Các phiên đang mở thành tab trên thanh cửa sổ (như tab trình duyệt). Chỉ là tiện ích hiển thị → lưu trong trình duyệt. */
export interface OpenTab {
  id: string;
  title: string;
  kind: FileKind | null;
}

const KEY = "office-agent-tabs";
const EVENT = "office-agent-tabs-change";
const MAX_TABS = 6;

function load(): OpenTab[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

function save(tabs: OpenTab[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(tabs));
  } catch {
    /* trình duyệt chặn lưu trữ: tab chỉ sống trong phiên này */
  }
  memory = tabs;
  window.dispatchEvent(new Event(EVENT));
}

let memory: OpenTab[] | null = null;
const current = () => memory ?? (memory = load());

/** Mở (hoặc cập nhật tên/loại) tab của một phiên; giữ tối đa MAX_TABS tab, bỏ tab cũ nhất. */
export function openTab(tab: OpenTab): void {
  const tabs = current();
  const i = tabs.findIndex((t) => t.id === tab.id);
  if (i >= 0) {
    if (tabs[i].title === tab.title && tabs[i].kind === tab.kind) return;
    save(tabs.map((t, j) => (j === i ? tab : t)));
  } else {
    save([...tabs, tab].slice(-MAX_TABS));
  }
}

export function closeTab(id: string): void {
  save(current().filter((t) => t.id !== id));
}

export function useOpenTabs(): OpenTab[] {
  const [tabs, setTabs] = useState<OpenTab[]>(current);
  useEffect(() => {
    const on = () => setTabs([...current()]);
    window.addEventListener(EVENT, on);
    return () => window.removeEventListener(EVENT, on);
  }, []);
  return tabs;
}
