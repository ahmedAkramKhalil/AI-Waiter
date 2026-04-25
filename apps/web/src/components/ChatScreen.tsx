import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ConciergeBell, Plus, Send } from "lucide-react";
import type { ChatMessage, MealCard, OrderConfirmation } from "../types";
import { addToCart, appendSessionMessage, getCart, streamChat } from "../api/client";
import MessageBubble from "./MessageBubble";

interface Props {
  sessionId: string;
  greeting?: string;
  suggestions?: string[];
  initialMessages?: ChatMessage[];
  onOrderPlaced: (order: OrderConfirmation) => void;
  onCartUpdated: () => void;
  onOpenCart: () => void;
  queuedPrompt?: string | null;
  onQueuedPromptHandled: () => void;
  onCallWaiter: () => void;
}

const DEFAULT_SUGGESTIONS = [
  "What is the dish of the day?",
  "Recommend a drink",
  "Is it spicy?",
  "Dessert menu",
];

const FINISH_ORDER_RE = /\b(done|complete|finished|finish|خلصت|خلاص|تم|كمل|اكمل الطلب|أكمل الطلب|أنهِ|انهي)\b/i;
const AFFIRMATIVE_REPLY_RE = /^(نعم|ايوه|أيوه|ايوا|أيوا|أكيد|اكيد|تمام|موافق|yes|yep|sure|ok)\s*[؟?!.,،]*$/i;

export default function ChatScreen({
  sessionId,
  greeting,
  suggestions,
  initialMessages,
  onCartUpdated,
  onOpenCart,
  queuedPrompt,
  onQueuedPromptHandled,
  onCallWaiter,
}: Props) {
  const suggestionList = useMemo(
    () =>
      suggestions && suggestions.length > 0 ? suggestions : DEFAULT_SUGGESTIONS,
    [suggestions]
  );
  const welcomeMessage = useMemo<ChatMessage>(
    () => ({
      id: "welcome",
      role: "assistant",
      content:
        greeting ??
        "أهلاً وسهلاً بك في المجلس. تفضّل، كيف تحب أن أرشّح لك من المنيو اليوم؟",
    }),
    [greeting]
  );
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    initialMessages && initialMessages.length > 0 ? initialMessages : [welcomeMessage]
  );
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingUpsellMeal, setPendingUpsellMeal] = useState<MealCard | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(initialMessages && initialMessages.length > 0 ? initialMessages : [welcomeMessage]);
    setPendingUpsellMeal(null);
  }, [initialMessages, sessionId, welcomeMessage]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const handleAddToCart = useCallback(
    async (meal: MealCard) => {
      await addToCart(sessionId, meal.meal_id);
      onCartUpdated();
      const followUpText = `تمت إضافة ${meal.name_ar} إلى السلة. تحب أرشّح لك معه الآن مشروبًا أو طبقًا جانبيًا يكمل الطلب؟`;
      const followUp: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: followUpText,
      };
      setMessages((current) => [...current, followUp]);
      setPendingUpsellMeal(meal);
      try {
        await appendSessionMessage(sessionId, "assistant", followUpText);
      } catch (error) {
        if (import.meta.env.DEV) {
          console.warn("failed to persist local assistant follow-up", error);
        }
      }
    },
    [onCartUpdated, sessionId]
  );

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;
      const followUpContext =
        pendingUpsellMeal && AFFIRMATIVE_REPLY_RE.test(trimmed)
          ? `السياق السابق: بعد إضافة ${pendingUpsellMeal.name_ar} [${pendingUpsellMeal.meal_id}] إلى السلة، النادل سأل الضيف إذا كان يريد مشروبًا أو طبقًا جانبيًا يكمل الطلب.`
          : undefined;
      setPendingUpsellMeal(null);

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
      };

      if (FINISH_ORDER_RE.test(trimmed)) {
        setMessages((current) => [...current, userMsg]);
        setInput("");
        try {
          const cart = await getCart(sessionId);
          const assistantMsg: ChatMessage =
            cart.items.length > 0
              ? {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  content:
                    "تمام، طلبك شبه جاهز. راجع السلة الآن واضغط Submit Order حتى يصل الطلب للمطبخ ويظهر عند لوحة الإدارة.",
                }
              : {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  content:
                    "ما عندك عناصر في السلة حتى الآن. اختر طبقًا أو مشروبًا أولًا، وبعدها لما تقول done أنقلك مباشرة لإرسال الطلب.",
                };
          setMessages((current) => [...current, assistantMsg]);
          if (cart.items.length > 0) {
            window.setTimeout(() => onOpenCart(), 700);
          }
        } catch {
          setMessages((current) => [
            ...current,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content:
                "صار خلل بسيط وأنا أتحقق من السلة. تقدر تفتح السلة الآن وتضغط Submit Order لإرسال الطلب للمطبخ.",
            },
          ]);
          window.setTimeout(() => onOpenCart(), 700);
        }
        return;
      }

      const botId = crypto.randomUUID();
      const botMsg: ChatMessage = {
        id: botId,
        role: "assistant",
        content: "",
        streaming: true,
      };
      setMessages((current) => [...current, userMsg, botMsg]);
      setInput("");
      setSending(true);

      await streamChat(
        sessionId,
        trimmed,
        {
        onText: (delta) => {
          setMessages((current) =>
            current.map((msg) =>
              msg.id === botId ? { ...msg, content: msg.content + delta } : msg
            )
          );
        },
        onMealCards: (cards) => {
          setMessages((current) =>
            current.map((msg) => (msg.id === botId ? { ...msg, cards } : msg))
          );
        },
        onChoices: (choices, submitLabel) => {
          setMessages((current) =>
            current.map((msg) =>
              msg.id === botId
                ? { ...msg, choices, choicesSubmitLabel: submitLabel }
                : msg
            )
          );
        },
        onDone: () => {
          setMessages((current) =>
            current.map((msg) => (msg.id === botId ? { ...msg, streaming: false } : msg))
          );
          setSending(false);
        },
        onError: (err) => {
          setMessages((current) =>
            current.map((msg) =>
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
        },
        { followUpContext }
      );
    },
    [pendingUpsellMeal, sending, sessionId]
  );

  useEffect(() => {
    if (!queuedPrompt) return;
    void send(queuedPrompt);
    onQueuedPromptHandled();
  }, [onQueuedPromptHandled, queuedPrompt, send]);

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={onCallWaiter} className="heritage-primary-button">
          <ConciergeBell size={16} />
          Call Waiter
        </button>
      </div>

      <div className="heritage-chat-shell">
        <div ref={scrollRef} className="heritage-chat-scroll">
          <div className="space-y-5">
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onAddToCart={handleAddToCart}
                onSubmitChoices={(text) => void send(text)}
              />
            ))}
          </div>
        </div>

        <div className="space-y-4 border-t border-gold/20 bg-background/75 p-4 backdrop-blur-sm">
          <div className="flex gap-2 overflow-x-auto no-scrollbar">
            {suggestionList.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => void send(suggestion)}
                className="heritage-chip"
              >
                {suggestion}
              </button>
            ))}
          </div>

          <motion.form
            layout
            onSubmit={(e) => {
              e.preventDefault();
              void send(input);
            }}
            className="heritage-composer"
          >
            <button type="button" className="heritage-icon-button">
              <Plus size={16} />
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about our menu..."
              className="min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-muted"
            />
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="heritage-send-button"
            >
              <Send size={16} />
            </button>
          </motion.form>
        </div>
      </div>
    </div>
  );
}
