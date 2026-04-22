import { motion } from "framer-motion";
import type { ChatMessage } from "../types";
import MealCard from "./MealCard";
import TypingDots from "./TypingDots";

interface Props {
  message: ChatMessage;
  onAddToCart?: (mealId: string) => void;
}

export default function MessageBubble({ message, onAddToCart }: Props) {
  const isUser = message.role === "user";
  const showDots = message.streaming && !message.content;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 220, damping: 22 }}
      className={`flex flex-col gap-3 w-full ${isUser ? "items-start" : "items-end"}`}
    >
      <div
        className={`max-w-[82%] px-4 py-3 rounded-3xl shadow-bubble text-[15px] leading-relaxed
          ${
            isUser
              ? "bg-gradient-to-br from-gold-300 to-gold-500 text-wine-900 rounded-br-md font-semibold"
              : "glass text-cream rounded-bl-md"
          }`}
      >
        {showDots ? <TypingDots /> : message.content}
      </div>

      {message.cards && message.cards.length > 0 && (
        <div className="w-full overflow-x-auto pb-2 -mx-4 px-4">
          <div className="flex gap-3 w-max">
            {message.cards.map((m, i) => (
              <MealCard
                key={m.meal_id + i}
                meal={m}
                index={i}
                onAdd={onAddToCart ? () => onAddToCart(m.meal_id) : undefined}
              />
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
