import { motion } from "framer-motion";
import { Flame, Plus } from "lucide-react";
import type { MealCard as Meal } from "../types";
import { imageUrl } from "../api/client";

interface Props {
  meal: Meal;
  onAdd?: () => void;
  index?: number;
}

export default function MealCard({ meal, onAdd, index = 0 }: Props) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
      className="group min-w-[290px] max-w-[290px] overflow-hidden rounded-[24px] border border-gold/20 bg-card shadow-soft"
    >
      <div className="relative h-48 overflow-hidden">
        <img
          src={imageUrl(meal.image_url)}
          alt={meal.name_ar}
          className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
        />
        <div className="heritage-card-fade" />
        <div className="absolute inset-x-0 top-0 z-10 flex items-start justify-between p-4">
          {meal.spice_level > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-gold/30 bg-background/85 px-2 py-1 text-xs text-secondary">
              <Flame size={12} />
              {meal.spice_level}/5
            </span>
          ) : (
            <span />
          )}
          <div className="rounded-full border border-gold/30 bg-background/85 px-3 py-1 text-xs uppercase tracking-[0.2em] text-secondary">
            Suggested
          </div>
        </div>
      </div>
      <div className="space-y-3 p-4 text-right">
        <div className="flex items-start justify-between gap-3">
          <div className="text-lg font-semibold text-secondary">
            {meal.price} {meal.currency}
          </div>
          <h3 className="font-serif-display text-2xl leading-tight text-primary">
            {meal.name_ar}
          </h3>
        </div>
        <div className="text-sm leading-6 text-muted">
          {meal.calories} kcal
        </div>
        {onAdd && (
          <button onClick={onAdd} className="heritage-primary-button w-full justify-center">
            <Plus size={16} />
            Add to Cart
          </button>
        )}
      </div>
    </motion.article>
  );
}
