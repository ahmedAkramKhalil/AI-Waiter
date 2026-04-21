import { motion } from "framer-motion";
import { Flame, Zap } from "lucide-react";
import type { MealCard as Meal } from "../types";
import { imageUrl } from "../api/client";

interface Props {
  meal: Meal;
  onAdd?: (meal: Meal) => void;
  index?: number;
}

export default function MealCard({ meal, onAdd, index = 0 }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, rotateX: -8 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{ delay: index * 0.08, type: "spring", stiffness: 120, damping: 14 }}
      whileHover={{ y: -4, rotateX: 2, rotateY: -2 }}
      style={{ transformPerspective: 1000 }}
      className="relative group min-w-[220px] w-[220px] rounded-3xl overflow-hidden
                 glass sheen"
    >
      {/* Image */}
      <div className="relative h-36 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-t from-wine-900/80 via-transparent to-transparent z-10" />
        <img
          src={imageUrl(meal.image_url)}
          alt={meal.name_ar}
          loading="lazy"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).src =
              "data:image/svg+xml;utf8," +
              encodeURIComponent(
                `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><rect fill='#3c0f18' width='200' height='200'/><text x='50%' y='50%' fill='#d9a83a' font-size='18' text-anchor='middle' font-family='sans-serif' dy='.3em'>🍽️</text></svg>`
              );
          }}
          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
        />
        <div className="absolute top-2 right-2 z-20 flex gap-1">
          {meal.spice_level > 0 && (
            <span className="chip !bg-wine-800/80 !border-wine-400/40 text-gold-200">
              <Flame size={12} />
              {meal.spice_level}/5
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="px-4 py-3 space-y-2">
        <h3 className="font-bold text-cream text-base leading-tight truncate">
          {meal.name_ar}
        </h3>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1 text-xs text-cream/60">
            <Zap size={12} />
            {meal.calories} كالوري
          </span>
          <span className="font-black text-gold-300 text-lg">
            {meal.price}
            <span className="text-xs text-gold-400/80 mr-1">{meal.currency}</span>
          </span>
        </div>
        {onAdd && (
          <button
            onClick={() => onAdd(meal)}
            className="btn-gold w-full py-2 text-sm sheen relative"
          >
            أضف للسلة
          </button>
        )}
      </div>
    </motion.div>
  );
}
