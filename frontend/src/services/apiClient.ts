export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = apiBaseUrl();
  const headers = init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers };
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(payload.detail ?? "Request failed");
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
}

export function apiUrl(path: string): string {
  return `${apiBaseUrl()}${path}`;
}
