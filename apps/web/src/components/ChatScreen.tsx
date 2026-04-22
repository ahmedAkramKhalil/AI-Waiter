import { useCallback, useEffect, useRef, useState } from "react";
import { Send, ShoppingBag, ChefHat, Check } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { ChatMessage, OrderConfirmation } from "../types";
import { addToCart, getCart, streamChat } from "../api/client";
import MessageBubble from "./MessageBubble";
import CartSheet from "./CartSheet";

interface Props {
  sessionId: string;
  greeting?: string;
  suggestions?: string[];
  onOrderPlaced: (order: OrderConfirmation) => void;
}

const DEFAULT_SUGGESTIONS = [
  "أبي شي حار وغير غالي",
  "اقترح لي طبق رئيسي",
  "وش عندكم من المشويات؟",
  "أضف الكبسة",
];

export default function ChatScreen({
  sessionId,
  greeting,
  suggestions,
  onOrderPlaced,
}: Props) {
  const suggestionList =
    suggestions && suggestions.length > 0 ? suggestions : DEFAULT_SUGGESTIONS;
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        greeting ??
        "أهلاً وسهلاً بك في مطعم الأصالة 🌙 كيف أقدر أخدمك اليوم؟",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [cartReloadKey, setCartReloadKey] = useState(0);
  const [cartCount, setCartCount] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Refresh the badge count whenever the cart might have changed
  const refreshCount = useCallback(async () => {
    try {
      const c = await getCart(sessionId);
      setCartCount(c.items.reduce((n, i) => n + i.quantity, 0));
    } catch {
      /* ignore */
    }
  }, [sessionId]);

  useEffect(() => {
    refreshCount();
  }, [refreshCount, cartReloadKey]);

  const handleAddToCart = useCallback(
    async (mealId: string) => {
      try {
        const updated = await addToCart(sessionId, mealId);
        setCartCount(updated.items.reduce((n, i) => n + i.quantity, 0));
        setCartReloadKey((k) => k + 1);
        const added = updated.items.find((i) => i.meal_id === mealId);
        setToast(`تمت إضافة ${added?.name_ar ?? "الوجبة"} للسلة`);
        setTimeout(() => setToast(null), 2000);
      } catch (e) {
        console.error(e);
        setToast("تعذّرت إضافة الوجبة");
        setTimeout(() => setToast(null), 2000);
      }
    },
    [sessionId]
  );

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
      };
      const botId = crypto.randomUUID();
      const botMsg: ChatMessage = {
        id: botId,
        role: "assistant",
        content: "",
        streaming: true,
      };
      setMessages((m) => [...m, userMsg, botMsg]);
      setInput("");
      setSending(true);

      await streamChat(sessionId, trimmed, {
        onText: (delta) => {
          setMessages((m) =>
            m.map((msg) =>
              msg.id === botId ? { ...msg, content: msg.content + delta } : msg
            )
          );
        },
        onMealCards: (cards) => {
          setMessages((m) =>
            m.map((msg) => (msg.id === botId ? { ...msg, cards } : msg))
          );
          // Heuristic: if a card was added, also refresh cart in background
          setCartReloadKey((k) => k + 1);
        },
        onDone: () => {
          setMessages((m) =>
            m.map((msg) => (msg.id === botId ? { ...msg, streaming: false } : msg))
          );
          setSending(false);
        },
        onError: (err) => {
          setMessages((m) =>
            m.map((msg) =>
              msg.id === botId
                ? {
                    ...msg,
                    streaming: false,
                    content: `عذراً، حدث خطأ في الاتصال: ${err.message}`,
                  }
                : msg
            )
          );
          setSending(false);
        },
      });
    },
    [sending, sessionId]
  );

  return (
    <div className="relative z-10 h-full w-full flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-white/5 backdrop-blur-lg bg-wine-900/30">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full glass-gold flex items-center justify-center">
            <ChefHat size={20} className="text-gold-100" />
          </div>
          <div>
            <div className="font-display text-lg text-gold-200 leading-none">أصيل</div>
            <div className="text-[11px] text-cream/50">نادل مطعم الأصالة · متصل</div>
          </div>
        </div>
        <button
          onClick={() => setCartOpen(true)}
          className="relative p-3 rounded-2xl glass sheen hover:bg-white/10"
          aria-label="السلة"
        >
          <ShoppingBag size={18} className="text-gold-200" />
          <AnimatePresence>
            {cartCount > 0 && (
              <motion.span
                key={cartCount}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                transition={{ type: "spring", stiffness: 400, damping: 18 }}
                className="absolute -top-1 -left-1 min-w-[20px] h-5 px-1 rounded-full
                           bg-gradient-to-b from-gold-200 to-gold-400 text-wine-900
                           text-[11px] font-black flex items-center justify-center
                           shadow-gold border border-white/40"
              >
                {cartCount}
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </header>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
      >
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} onAddToCart={handleAddToCart} />
        ))}

        {/* Suggestion chips — shown only if just the welcome message */}
        {messages.length === 1 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-wrap gap-2 pt-2"
          >
            {suggestionList.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="chip text-gold-200 hover:bg-white/15 transition-colors"
              >
                {s}
              </button>
            ))}
          </motion.div>
        )}
      </div>

      {/* Composer */}
      <AnimatePresence>
        <motion.div
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="p-3 pb-[max(12px,env(safe-area-inset-bottom))] border-t border-white/5
                     bg-wine-900/40 backdrop-blur-xl"
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2 glass rounded-full pr-4 pl-1 py-1"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="اكتب طلبك بالعربية…"
              dir="rtl"
              className="flex-1 bg-transparent text-cream placeholder-cream/40
                         py-3 px-2 outline-none text-[15px]"
            />
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="btn-gold sheen relative w-11 h-11 p-0 flex items-center justify-center
                         disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="إرسال"
            >
              <Send size={18} className="-rotate-180" />
            </button>
          </form>
        </motion.div>
      </AnimatePresence>

      <CartSheet
        open={cartOpen}
        sessionId={sessionId}
        onClose={() => setCartOpen(false)}
        onOrderPlaced={onOrderPlaced}
        reloadKey={cartReloadKey}
      />

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ y: 30, opacity: 0, scale: 0.9 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 10, opacity: 0 }}
            className="fixed bottom-24 left-1/2 -translate-x-1/2 z-[60]
                       glass-gold sheen rounded-full px-5 py-3
                       flex items-center gap-2 text-sm font-semibold text-wine-900
                       shadow-gold"
          >
            <Check size={16} strokeWidth={3} />
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
