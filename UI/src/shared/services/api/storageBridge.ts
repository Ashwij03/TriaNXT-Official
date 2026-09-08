import { api, isApiEnabled } from "./client";

const INSTALLED_KEY = "__trianxtApiStorageBridgeInstalled";
const EXCLUDED_KEYS = new Set([
  "currentUser", "isLoggedIn", "userFullName", "trianxtAuthToken",
  "adminPreviewRole", "piPreviewRole", "profilePhoto",
]);

function isBusinessKey(key: string) {
  if (!key || EXCLUDED_KEYS.has(key)) return false;
  if (key.startsWith("__trianxt")) return false;
  return true;
}

function parseStored(value: string | null) {
  if (value === null) return null;
  try { return JSON.parse(value); } catch { return value; }
}

export async function hydrateApiStorage() {
  if (!isApiEnabled() || typeof window === "undefined") return;
  try {
    const response: any = await api.get("/api/client-storage/");
    const rows = Array.isArray(response) ? response : (response?.data || []);
    const serverKeys = new Set<string>();
    const pendingUploads: Promise<any>[] = [];

    for (const row of rows) {
      const key = String(row?.key || "");
      if (!isBusinessKey(key)) continue;
      serverKeys.add(key);
      window.localStorage.setItem(key, JSON.stringify(row.value));
    }

    // One-time bootstrap: if the API has no value for an existing local
    // business key, upload it so the API becomes the durable source of truth.
    for (let i = 0; i < window.localStorage.length; i++) {
      const key = window.localStorage.key(i);
      if (!key || !isBusinessKey(key) || serverKeys.has(key)) continue;
      pendingUploads.push(api.put(`/api/client-storage/${encodeURIComponent(key)}`, {
        value: parseStored(window.localStorage.getItem(key)),
      }).catch((err) => console.warn(`[TriaNXT] API storage bootstrap failed for ${key}`, err)));
    }
    await Promise.allSettled(pendingUploads);
  } catch (err) {
    console.warn("[TriaNXT] API storage hydration failed", err);
  }
}

export function installApiStorageBridge() {
  if (!isApiEnabled() || typeof window === "undefined") return;
  const storage = window.localStorage as any;
  if (storage[INSTALLED_KEY]) return;

  const originalSetItem = storage.setItem.bind(storage);
  const originalRemoveItem = storage.removeItem.bind(storage);
  storage.setItem = (key: string, value: string) => {
    originalSetItem(key, value);
    if (!isBusinessKey(key)) return;
    void api.put(`/api/client-storage/${encodeURIComponent(key)}`, {
      value: parseStored(value),
    }).catch((err) => console.warn(`[TriaNXT] API storage write failed for ${key}`, err));
  };
  storage.removeItem = (key: string) => {
    originalRemoveItem(key);
    if (!isBusinessKey(key)) return;
    void api.delete(`/api/client-storage/${encodeURIComponent(key)}`).catch((err) => console.warn(`[TriaNXT] API storage delete failed for ${key}`, err));
  };
  try { originalSetItem(INSTALLED_KEY, "true"); } catch { /* ignore */ }
}

export async function enableApiStorage() {
  if (!isApiEnabled()) return;
  await hydrateApiStorage();
  installApiStorageBridge();
}
