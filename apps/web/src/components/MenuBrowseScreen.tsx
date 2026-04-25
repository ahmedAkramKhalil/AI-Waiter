import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Flame, Plus, Sparkles } from "lucide-react";
import { addToCart, imageUrl } from "../api/client";
import type { MenuMeal } from "../types";

interface Props {
  meals: MenuMeal[];
  loading: boolean;
  sessionId: string;
  onCartUpdated: () => void;
  onAskWaiter: (message: string) => void;
}

export default function MenuBrowseScreen({
  meals,
  loading,
  sessionId,
  onCartUpdated,
  onAskWaiter,
}: Props) {
  const [category, setCategory] = useState<string>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const categories = useMemo(() => {
    const values = [...new Set(meals.map((meal) => meal.category))];
    return ["all", ...values];
  }, [meals]);

  const visibleMeals = useMemo(() => {
    const filtered =
      category === "all" ? meals : meals.filter((meal) => meal.category === category);
    return [...filtered].sort((a, b) => {
      if (a.featured !== b.featured) return a.featured ? -1 : 1;
      if (a.recommendation_rank !== b.recommendation_rank) {
        return b.recommendation_rank - a.recommendation_rank;
      }
      return a.name_ar.localeCompare(b.name_ar, "ar");
    });
  }, [category, meals]);

  async function handleAdd(meal: MenuMeal) {
    try {
      setBusyId(meal.id);
      await addToCart(sessionId, meal.id);
      onCartUpdated();
      setNotice(`تمت إضافة ${meal.name_ar} إلى السلة`);
      window.setTimeout(() => setNotice(null), 2000);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <section className="heritage-panel p-6 text-center">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-3 py-1 text-[11px] tracking-[0.28em] text-secondary uppercase">
            <Sparkles size={14} />
            Culinary Library
          </div>
          <h1 className="font-serif-display text-4xl text-primary">
            تصفّح المنيو
          </h1>
          <p className="max-w-xl text-[15px] leading-7 text-muted">
            اختر من الأطباق المميزة أو اطلب من النادل الذكي أن يرشّح لك طبقًا حسب
            ذوقك وميزانيتك.
          </p>
        </div>
      </section>

      <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
        {categories.map((value) => (
          <button
            key={value}
            onClick={() => setCategory(value)}
            className={
              category === value ? "heritage-pill active" : "heritage-pill"
            }
          >
            {value === "all" ? "All Dishes" : value}
          </button>
        ))}
      </div>

      <AnimatePresence>
        {notice && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="rounded-2xl border border-gold/30 bg-background/95 px-4 py-3 text-sm text-secondary shadow-soft"
          >
            {notice}
          </motion.div>
        )}
      </AnimatePresence>

      {loading ? (
        <div className="heritage-panel p-8 text-center text-muted">
          جاري تحميل المنيو...
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-3">
          {visibleMeals.map((meal) => (
            <article key={meal.id} className="heritage-menu-card">
              <div className="relative h-36 overflow-hidden md:h-52">
                <img
                  src={imageUrl(meal.image_url)}
                  alt={meal.name_ar}
                  className="h-full w-full object-cover transition duration-700 group-hover:scale-105"
                />
                <div className="heritage-card-fade" />
                <div className="absolute inset-x-0 bottom-0 z-10 p-4 text-right">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-gold md:text-lg">
                      {meal.price} {meal.currency}
                    </div>
                    {meal.featured && (
                      <span className="rounded-full border border-gold/35 bg-background/85 px-2 py-1 text-[9px] uppercase tracking-[0.18em] text-secondary md:text-[10px] md:tracking-[0.22em]">
                        Featured
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="space-y-2 p-3 text-right md:space-y-3 md:p-4">
                <div className="flex items-start justify-between gap-2 md:gap-3">
                  <div>
                    <h3 className="font-serif-display text-lg leading-tight text-primary md:text-2xl">
                      {meal.name_ar}
                    </h3>
                    <div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-secondary md:text-xs md:tracking-[0.22em]">
                      {meal.category}
                    </div>
                  </div>
                  {meal.spice_level > 0 && (
                    <div className="inline-flex items-center gap-1 rounded-full border border-gold/25 bg-gold/10 px-2 py-1 text-[10px] text-secondary md:text-xs">
                      <Flame size={12} />
                      {meal.spice_level}/5
                    </div>
                  )}
                </div>

                <p className="line-clamp-3 text-xs leading-5 text-muted md:text-sm md:leading-6">
                  {meal.sales_pitch_ar || meal.description_ar}
                </p>

                <div className="flex flex-col gap-2 md:flex-row md:items-center">
                  <button
                    onClick={() => void handleAdd(meal)}
                    disabled={busyId === meal.id}
                    className="heritage-primary-button w-full justify-center md:flex-1"
                  >
                    <Plus size={16} />
                    {busyId === meal.id ? "جارٍ الإضافة..." : "أضف للسلة"}
                  </button>
                  <button
                    onClick={() => onAskWaiter(`رشح لي شيئًا مثل ${meal.name_ar}`)}
                    className="heritage-ghost-button w-full md:flex-1"
                  >
                    اسأل النادل
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
