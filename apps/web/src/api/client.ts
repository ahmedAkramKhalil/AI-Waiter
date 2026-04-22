import type { Cart, MealCard, OrderConfirmation } from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "http://localhost:8001").replace(
  /\/$/,
  ""
);

export function imageUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

export interface SessionStart {
  session_id: string;
  greeting: string;
  suggestions: string[];
}

export async function startSession(): Promise<SessionStart> {
  const res = await fetch(`${API_BASE}/session/start`, { method: "POST" });
  if (!res.ok) throw new Error(`session/start ${res.status}`);
  const data = await res.json();
  return {
    session_id: data.session_id,
    greeting:
      data.greeting ??
      "أهلاً وسهلاً بك في مطعم الأصالة 🌙 كيف أقدر أخدمك اليوم؟",
    suggestions: data.suggestions ?? [
      "أبي شي حار وغير غالي",
      "اقترح لي طبق رئيسي",
      "وش عندكم من المشويات؟",
      "أضف الكبسة",
    ],
  };
}

export async function getCart(sessionId: string): Promise<Cart> {
  const res = await fetch(`${API_BASE}/cart/${sessionId}`);
  if (!res.ok) throw new Error(`cart ${res.status}`);
  return (await res.json()) as Cart;
}

export async function addToCart(
  sessionId: string,
  mealId: string,
  quantity = 1
): Promise<Cart> {
  const res = await fetch(`${API_BASE}/cart/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, meal_id: mealId, quantity }),
  });
  if (!res.ok) throw new Error(`cart/add ${res.status}`);
  return (await res.json()) as Cart;
}

export async function removeFromCart(
  sessionId: string,
  mealId: string
): Promise<Cart> {
  const res = await fetch(`${API_BASE}/cart/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, meal_id: mealId }),
  });
  if (!res.ok) throw new Error(`cart/remove ${res.status}`);
  return (await res.json()) as Cart;
}

export async function submitOrder(sessionId: string): Promise<OrderConfirmation> {
  const res = await fetch(`${API_BASE}/order/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`order ${res.status}`);
  return (await res.json()) as OrderConfirmation;
}

/**
 * SSE chat stream — reads text deltas + meal cards + done.
 * Uses fetch + ReadableStream to allow POST body (EventSource can't POST).
 */
export interface ChatCallbacks {
  onText: (delta: string) => void;
  onMealCards: (cards: MealCard[]) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

export async function streamChat(
  sessionId: string,
  message: string,
  cb: ChatCallbacks,
  signal?: AbortSignal
): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal,
    });
    if (!res.ok || !res.body) throw new Error(`chat ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    const flush = (rawEvent: string) => {
      const lines = rawEvent.split(/\r?\n/);
      let eventName = "message";
      let dataStr = "";
      for (const line of lines) {
        if (!line || line.startsWith(":")) continue; // skip keep-alives/pings
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataStr += line.slice(5).replace(/^ /, "");
      }
      if (!dataStr) return;
      try {
        const payload = JSON.parse(dataStr);
        if (import.meta.env.DEV) console.debug("[SSE]", eventName, payload);
        if (eventName === "text") cb.onText(payload.delta ?? "");
        else if (eventName === "meal_cards") cb.onMealCards(payload.cards ?? []);
        else if (eventName === "done") cb.onDone();
      } catch (e) {
        if (import.meta.env.DEV) console.warn("[SSE parse error]", dataStr, e);
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Events separated by blank line (\n\n or \r\n\r\n)
      let idx: number;
      const sep = /\r?\n\r?\n/;
      while ((idx = buffer.search(sep)) !== -1) {
        const rawEvent = buffer.slice(0, idx);
        const match = buffer.slice(idx).match(sep)!;
        buffer = buffer.slice(idx + match[0].length);
        flush(rawEvent);
      }
    }
    if (buffer.trim()) flush(buffer);
    cb.onDone();
  } catch (err) {
    cb.onError(err instanceof Error ? err : new Error(String(err)));
  }
}
