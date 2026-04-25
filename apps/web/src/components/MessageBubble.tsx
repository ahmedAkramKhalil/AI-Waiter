import { useMemo, useState } from "react";
import type {
  ChoiceQuestion,
  MealCard as MealCardData,
} from "../types";
import { motion } from "framer-motion";
import { Bot } from "lucide-react";
import type { ChatMessage } from "../types";
import MealCard from "./MealCard";
import TypingDots from "./TypingDots";

interface Props {
  message: ChatMessage;
  onAddToCart?: (meal: MealCardData) => void;
  onSubmitChoices?: (text: string) => void;
}

function buildChoiceAnswer(questions: ChoiceQuestion[], selected: Record<string, string>): string {
  const parts = questions
    .map((question) => {
      const option = question.options.find((item) => item.id === selected[question.id]);
      return option?.value;
    })
    .filter(Boolean);
  return `أريد ترشيحًا حسب هذه التفضيلات: ${parts.join("، ")}.`;
}

export default function MessageBubble({ message, onAddToCart, onSubmitChoices }: Props) {
  const isUser = message.role === "user";
  const showDots = message.streaming && !message.content;
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const allChoicesSelected = useMemo(
    () =>
      !!message.choices &&
      message.choices.length > 0 &&
      message.choices.every((question) => !!selected[question.id]),
    [message.choices, selected]
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      className={isUser ? "flex flex-col items-end gap-3" : "flex flex-col items-start gap-3"}
    >
      {isUser ? (
        <div className="heritage-user-bubble">
          {showDots ? <TypingDots /> : message.content}
        </div>
      ) : (
        <div className="flex max-w-full items-end gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-gold/25 bg-primary/10 text-primary">
            <Bot size={18} />
          </div>
          <div className="heritage-ai-bubble">
            {showDots ? <TypingDots /> : message.content}
          </div>
        </div>
      )}

      {message.cards && message.cards.length > 0 && (
        <div className="w-full overflow-x-auto no-scrollbar pl-12">
          <div className="flex gap-4 pb-2">
            {message.cards.map((meal, index) => (
              <MealCard
                key={meal.meal_id + index}
                meal={meal}
                index={index}
                onAdd={onAddToCart ? () => onAddToCart(meal) : undefined}
              />
            ))}
          </div>
        </div>
      )}

      {message.choices && message.choices.length > 0 && (
        <div className="w-full pl-12">
          <div className="space-y-3 rounded-[22px] border border-gold/15 bg-card/60 p-4">
            {message.choices.map((question) => (
              <div key={question.id} className="space-y-2 text-right">
                <div className="text-sm font-semibold text-primary">{question.label}</div>
                <div className="flex flex-wrap justify-end gap-2">
                  {question.options.map((option) => {
                    const active = selected[question.id] === option.id;
                    return (
                      <button
                        key={option.id}
                        disabled={submitted}
                        onClick={() =>
                          setSelected((current) => ({ ...current, [question.id]: option.id }))
                        }
                        className={active ? "heritage-chip active" : "heritage-chip"}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}

            {allChoicesSelected && onSubmitChoices && (
              <div className="flex justify-end pt-1">
                <button
                  onClick={() => {
                    setSubmitted(true);
                    onSubmitChoices(buildChoiceAnswer(message.choices!, selected));
                  }}
                  className="heritage-primary-button"
                  disabled={submitted}
                >
                  {message.choicesSubmitLabel || "رشّح لي الآن"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
}
