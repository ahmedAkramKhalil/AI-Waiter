import type {
  AdminOrdersResponse,
  Cart,
  ChoiceQuestion,
  ImageUploadResponse,
  MealCard,
  MenuMeal,
  MenuResponse,
  OrderConfirmation,
  SessionStatePayload,
  SessionStartPayload,
  WaiterCallNotification,
} from "../types";

const configuredApiBase = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
let resolvedApiBase = configuredApiBase;

function candidateApiBases(): string[] {
  const bases: string[] = [];
  const add = (value: string | undefined) => {
    const normalized = (value ?? "").replace(/\/$/, "");
    if (normalized && !bases.includes(normalized)) bases.push(normalized);
  };

  add(configuredApiBase);

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    const localProtocol = protocol === "https:" ? "https:" : "http:";
    add(`${localProtocol}//${hostname}:8001`);
    add(`${localProtocol}//${hostname}:8000`);

    if (hostname !== "localhost" && hostname !== "127.0.0.1") {
      add("http://localhost:8001");
      add("http://localhost:8000");
    }
  }

  add("http://localhost:8001");
  add("http://localhost:8000");
  return bases;
}

function currentApiBase(): string {
  return resolvedApiBase || candidateApiBases()[0] || "http://localhost:8001";
}

async function fetchWithApiFallback(
  path: string,
  init?: RequestInit,
  expectStream = false
): Promise<Response> {
  const bases = resolvedApiBase
    ? [resolvedApiBase, ...candidateApiBases().filter((base) => base !== resolvedApiBase)]
    : candidateApiBases();

  let lastError: Error | null = null;

  for (const base of bases) {
    try {
      const res = await fetch(`${base}${path}`, init);
      if (!res.ok) {
        throw new Error(`${path} ${res.status}`);
      }
      if (expectStream && !res.body) {
        throw new Error(`${path} stream unavailable`);
      }
      resolvedApiBase = base;
      return res;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
    }
  }

  const tried = bases.join(", ");
  throw new Error(
    `تعذر الوصول إلى الخادم. Tried: ${tried}${lastError ? ` | ${lastError.message}` : ""}`
  );
}

export function imageUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const base = currentApiBase();
  const normalized = `${path.startsWith("/") ? "" : "/"}${path}`
    .split("/")
    .map((segment, index) => (index === 0 ? segment : encodeURIComponent(segment)))
    .join("/");
  return `${base}${normalized}`;
}

export async function startSession(tableNumber?: number | null): Promise<SessionStartPayload> {
  const res = await fetchWithApiFallback("/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ table_number: tableNumber ?? null }),
  });
  const data = await res.json();
  return {
    session_id: data.session_id,
    table_number: data.table_number ?? null,
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

export async function getSession(sessionId: string): Promise<SessionStatePayload> {
  const res = await fetchWithApiFallback(`/session/${sessionId}`);
  const data = await res.json();
  return {
    session_id: data.session_id,
    table_number: data.table_number ?? null,
    greeting:
      data.greeting ??
      "أهلاً وسهلاً بك في مطعم الأصالة 🌙 كيف أقدر أخدمك اليوم؟",
    suggestions: data.suggestions ?? [
      "أبي شي حار وغير غالي",
      "اقترح لي طبق رئيسي",
      "وش عندكم من المشويات؟",
      "أضف الكبسة",
    ],
    history: Array.isArray(data.history) ? data.history : [],
  };
}

export async function appendSessionMessage(
  sessionId: string,
  role: "user" | "assistant",
  content: string
): Promise<void> {
  await fetchWithApiFallback(`/session/${sessionId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, content }),
  });
}

export async function getCart(sessionId: string): Promise<Cart> {
  const res = await fetchWithApiFallback(`/cart/${sessionId}`);
  return (await res.json()) as Cart;
}

export async function addToCart(
  sessionId: string,
  mealId: string,
  quantity = 1
): Promise<Cart> {
  const res = await fetchWithApiFallback("/cart/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, meal_id: mealId, quantity }),
  });
  return (await res.json()) as Cart;
}

export async function removeFromCart(
  sessionId: string,
  mealId: string
): Promise<Cart> {
  const res = await fetchWithApiFallback("/cart/remove", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, meal_id: mealId }),
  });
  return (await res.json()) as Cart;
}

export async function submitOrder(sessionId: string): Promise<OrderConfirmation> {
  const res = await fetchWithApiFallback("/order/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return (await res.json()) as OrderConfirmation;
}

export async function fetchMenu(): Promise<MenuResponse> {
  const res = await fetchWithApiFallback("/menu");
  return (await res.json()) as MenuResponse;
}

export async function saveMenuMeal(meal: MenuMeal): Promise<MenuMeal> {
  const res = await fetchWithApiFallback("/admin/menu/meal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(meal),
  });
  return (await res.json()) as MenuMeal;
}

export async function deleteMenuMeal(mealId: string): Promise<void> {
  await fetchWithApiFallback(`/admin/menu/meal/${mealId}`, {
    method: "DELETE",
  });
}

export async function uploadMenuImage(file: File): Promise<ImageUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetchWithApiFallback("/admin/menu/upload-image", {
    method: "POST",
    body: form,
  });
  return (await res.json()) as ImageUploadResponse;
}

export async function fetchAdminOrders(): Promise<AdminOrdersResponse> {
  const res = await fetchWithApiFallback("/admin/orders");
  return (await res.json()) as AdminOrdersResponse;
}

export async function markAdminOrdersSeen(): Promise<void> {
  await fetchWithApiFallback("/admin/orders/mark-seen", { method: "POST" });
}

export async function callWaiter(
  sessionId: string,
  tableNumber?: number | null,
  noteAr?: string | null
): Promise<WaiterCallNotification> {
  const res = await fetchWithApiFallback("/waiter/call", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      table_number: tableNumber ?? null,
      note_ar: noteAr ?? null,
    }),
  });
  return (await res.json()) as WaiterCallNotification;
}

/**
 * SSE chat stream — reads text deltas + meal cards + done.
 * Uses fetch + ReadableStream to allow POST body (EventSource can't POST).
 */
export interface ChatCallbacks {
  onText: (delta: string) => void;
  onMealCards: (cards: MealCard[]) => void;
  onChoices: (questions: ChoiceQuestion[], submitLabel?: string) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

export interface StreamChatOptions {
  signal?: AbortSignal;
  followUpContext?: string;
}

export async function streamChat(
  sessionId: string,
  message: string,
  cb: ChatCallbacks,
  options?: StreamChatOptions
): Promise<void> {
  try {
    const res = await fetchWithApiFallback(
      "/chat",
      {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        follow_up_context: options?.followUpContext ?? null,
      }),
      signal: options?.signal,
      },
      true
    );

    const body = res.body;
    if (!body) throw new Error("chat stream unavailable");
    const reader = body.getReader();
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
        else if (eventName === "choices") cb.onChoices(payload.questions ?? [], payload.submit_label);
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
