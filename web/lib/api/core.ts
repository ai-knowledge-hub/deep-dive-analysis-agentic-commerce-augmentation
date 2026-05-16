import { SessionSummary } from "./types";

let warnedApiBase = false;
const DEFAULT_API_BASE = "http://localhost:8000";
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined" ? window.location.origin : DEFAULT_API_BASE);

function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    const localOverride = window.localStorage.getItem("api_base");
    if (localOverride) return localOverride;
  }
  if (
    API_BASE.includes("localhost:3000") ||
    API_BASE.includes("127.0.0.1:3000")
  ) {
    if (typeof window !== "undefined" && !warnedApiBase) {
      warnedApiBase = true;
      // eslint-disable-next-line no-console
      console.warn(
        `API base resolved to ${API_BASE}; falling back to ${DEFAULT_API_BASE}. ` +
          "Set NEXT_PUBLIC_API_URL in web/.env.local and restart Next to silence this warning.",
      );
    }
    return DEFAULT_API_BASE;
  }
  return API_BASE;
}
const CLIENT_ID_STORAGE_KEY = "client_id";
const BRAND_ID_STORAGE_KEY = "brand_id";
const PRODUCT_ID_STORAGE_KEY = "product_id";
const REGISTRY_WRITE_TOKEN_STORAGE_KEY = "registry_write_token";

export function getSessionsStorageKey(userId: string, clientId?: string): string {
  const clientTag = clientId ? `.${clientId}` : "";
  return `intentionality.sessions.${userId}${clientTag}`;
}

export function readCachedSessions(key: string): SessionSummary[] {
  if (typeof window === "undefined") return [];
  const storedRaw = window.localStorage.getItem(key);
  if (!storedRaw) return [];
  try {
    return JSON.parse(storedRaw) as SessionSummary[];
  } catch {
    window.localStorage.removeItem(key);
    return [];
  }
}

export function writeCachedSessions(key: string, sessions: SessionSummary[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(sessions));
}

export function getClientId(): string | undefined {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(CLIENT_ID_STORAGE_KEY);
    if (stored) {
      return stored;
    }
  }
  return process.env.NEXT_PUBLIC_CLIENT_ID ?? undefined;
}

export function getBrandId(): string | undefined {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(BRAND_ID_STORAGE_KEY);
    if (stored) {
      return stored;
    }
  }
  return undefined;
}

export function getProductId(): string | undefined {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(PRODUCT_ID_STORAGE_KEY);
    if (stored) {
      return stored;
    }
  }
  return undefined;
}

export function getRegistryWriteToken(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return normalizeRegistryWriteToken(
    window.localStorage.getItem(REGISTRY_WRITE_TOKEN_STORAGE_KEY),
  );
}

export function setRegistryWriteToken(token: string): void {
  if (typeof window === "undefined") return;
  const normalized = normalizeRegistryWriteToken(token);
  if (!normalized) {
    window.localStorage.removeItem(REGISTRY_WRITE_TOKEN_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(REGISTRY_WRITE_TOKEN_STORAGE_KEY, normalized);
}

export function clearRegistryWriteToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(REGISTRY_WRITE_TOKEN_STORAGE_KEY);
}

export function registryWriteAuthHeaders(): HeadersInit | undefined {
  const token = getRegistryWriteToken();
  return token ? { Authorization: `Bearer ${token}` } : undefined;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { headers: initHeaders, ...rest } = init ?? {};
  const response = await fetch(`${resolveApiBase()}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...headerRecord(initHeaders),
    },
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }
  return response.json();
}

export async function requestStream<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const { headers: initHeaders, ...rest } = init ?? {};
  const response = await fetch(`${resolveApiBase()}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...headerRecord(initHeaders),
    },
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }
  if (!response.body) {
    return response.json();
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let lastPayload: T | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const lines = part.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const data = line.replace(/^data:\s*/, "").trim();
        if (!data) continue;
        try {
          lastPayload = JSON.parse(data) as T;
        } catch {
          // ignore malformed chunks
        }
      }
    }
  }

  if (lastPayload) {
    return lastPayload;
  }
  return response.json();
}

export type StreamHandlers<T> = {
  onDelta?: (delta: string) => void;
  onStatus?: (status: string) => void;
  onPayload?: (payload: T) => void;
};

export async function requestStreamWithEvents<T>(
  path: string,
  init: RequestInit | undefined,
  handlers: StreamHandlers<T>,
): Promise<T> {
  const { headers: initHeaders, ...rest } = init ?? {};
  const response = await fetch(`${resolveApiBase()}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...headerRecord(initHeaders),
    },
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }
  if (!response.body) {
    return response.json();
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let lastPayload: T | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const lines = block.split("\n");
      let eventName = "message";
      for (const line of lines) {
        if (line.startsWith("event:")) {
          eventName = line.replace("event:", "").trim();
        }
      }
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const data = line.replace(/^data:\s*/, "").trim();
        if (!data) continue;
        try {
          const parsed = JSON.parse(data);
          if (eventName === "delta") {
            handlers.onDelta?.(parsed.content ?? "");
          } else if (eventName === "status") {
            handlers.onStatus?.(parsed.phase ?? "");
          } else if (eventName === "conversation") {
            lastPayload = parsed as T;
            handlers.onPayload?.(parsed as T);
          }
        } catch {
          // ignore malformed chunks
        }
      }
    }
  }

  if (lastPayload) {
    return lastPayload;
  }
  return response.json();
}

function normalizeRegistryWriteToken(token?: string | null): string | undefined {
  const normalized = String(token ?? "")
    .trim()
    .replace(/^Bearer\s+/i, "")
    .trim();
  return normalized || undefined;
}

function headerRecord(headers?: HeadersInit): Record<string, string> {
  if (!headers) return {};
  const result: Record<string, string> = {};
  new Headers(headers).forEach((value, key) => {
    result[key] = value;
  });
  return result;
}

export function listCachedSessions(userId: string): SessionSummary[] {
  const clientId = getClientId();
  return readCachedSessions(getSessionsStorageKey(userId, clientId));
}

export function mergeAndCacheSessions(
  userId: string,
  sessions: SessionSummary[],
): SessionSummary[] {
  const clientId = getClientId();
  const cacheKey = getSessionsStorageKey(userId, clientId);
  const cached = readCachedSessions(cacheKey);
  const merged = new Map<string, SessionSummary>();
  sessions.forEach((session) => merged.set(session.id, session));
  cached.forEach((session) => {
    if (!merged.has(session.id)) {
      merged.set(session.id, session);
    }
  });
  const mergedList = Array.from(merged.values());
  writeCachedSessions(cacheKey, mergedList);
  return mergedList;
}
