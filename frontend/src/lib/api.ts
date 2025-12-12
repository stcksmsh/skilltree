export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} failed: ${r.status}`);
  return (await r.json()) as T;
}

export async function apiPost(path: string): Promise<void> {
  const r = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!r.ok) throw new Error(`${path} failed: ${r.status}`);
}
