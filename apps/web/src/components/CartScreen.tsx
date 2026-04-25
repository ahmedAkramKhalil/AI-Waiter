import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Minus, Plus, Sparkles, Trash2 } from "lucide-react";
import { addToCart, getCart, removeFromCart, submitOrder } from "../api/client";
import type { Cart, OrderConfirmation } from "../types";

interface Props {
  sessionId: string;
  active: boolean;
  reloadKey: number;
  onCartUpdated: () => void;
  onOrderPlaced: (order: OrderConfirmation) => void;
}

export default function CartScreen({
  sessionId,
  active,
  reloadKey,
  onCartUpdated,
  onOrderPlaced,
}: Props) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyMealId, setBusyMealId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!active) return;
    void loadCart();
  }, [active, reloadKey, sessionId]);

  async function loadCart() {
    setLoading(true);
    try {
      const nextCart = await getCart(sessionId);
      setCart(nextCart);
    } finally {
      setLoading(false);
    }
  }

  async function updateQuantity(mealId: string, nextQuantity: number) {
    if (!cart) return;
    setBusyMealId(mealId);
    try {
      await removeFromCart(sessionId, mealId);
      if (nextQuantity > 0) {
        await addToCart(sessionId, mealId, nextQuantity);
      }
      await loadCart();
      onCartUpdated();
    } finally {
      setBusyMealId(null);
    }
  }

  async function removeItem(mealId: string) {
    setBusyMealId(mealId);
    try {
      await removeFromCart(sessionId, mealId);
      await loadCart();
      onCartUpdated();
      setNotice("تم حذف العنصر من السلة");
      window.setTimeout(() => setNotice(null), 1800);
    } finally {
      setBusyMealId(null);
    }
  }

  async function handleSubmit() {
    if (!cart?.items.length) return;
    setSubmitting(true);
    try {
      const order = await submitOrder(sessionId);
      onCartUpdated();
      onOrderPlaced(order);
    } finally {
      setSubmitting(false);
    }
  }

  const service = cart ? cart.total * 0.05 : 0;
  const total = (cart?.total ?? 0) + service;

  return (
    <div className="space-y-6">
      <section className="heritage-panel p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.28em] text-secondary">
              Your Platter
            </div>
            <h1 className="mt-2 font-serif-display text-4xl text-primary">
              السلة والطلب
            </h1>
          </div>
          <div className="rounded-full border border-gold/30 bg-gold/10 px-3 py-1 text-xs text-secondary">
            {cart?.items.length ?? 0} Items
          </div>
        </div>
      </section>

      <AnimatePresence>
        {notice && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="rounded-2xl border border-gold/30 bg-background/90 px-4 py-3 text-sm text-secondary shadow-soft"
          >
            {notice}
          </motion.div>
        )}
      </AnimatePresence>

      {loading ? (
        <div className="heritage-panel p-8 text-center text-muted">جاري تحميل السلة...</div>
      ) : !cart || cart.items.length === 0 ? (
        <div className="heritage-panel space-y-4 p-8 text-center">
          <Sparkles className="mx-auto text-gold" />
          <h2 className="font-serif-display text-3xl text-primary">السلة فارغة</h2>
          <p className="text-sm leading-6 text-muted">
            أضف بعض الأطباق من المنيو أو اطلب من النادل الذكي أن يقترح لك شيئًا مميزًا.
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {cart.items.map((item) => (
              <article key={item.meal_id} className="heritage-panel p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2 text-right">
                    <h3 className="font-serif-display text-2xl text-primary">
                      {item.name_ar}
                    </h3>
                    <p className="text-sm text-muted">
                      {item.unit_price.toFixed(0)} {item.currency} للقطعة
                    </p>
                  </div>
                  <button
                    onClick={() => void removeItem(item.meal_id)}
                    className="heritage-icon-button"
                    disabled={busyMealId === item.meal_id}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <div className="heritage-qty-control">
                    <button
                      onClick={() => void updateQuantity(item.meal_id, item.quantity - 1)}
                      disabled={busyMealId === item.meal_id}
                    >
                      <Minus size={14} />
                    </button>
                    <span>{item.quantity}</span>
                    <button
                      onClick={() => void updateQuantity(item.meal_id, item.quantity + 1)}
                      disabled={busyMealId === item.meal_id}
                    >
                      <Plus size={14} />
                    </button>
                  </div>
                  <div className="text-lg font-semibold text-secondary">
                    {(item.unit_price * item.quantity).toFixed(0)} {item.currency}
                  </div>
                </div>
              </article>
            ))}
          </div>

          <section className="heritage-panel p-6">
            <div className="space-y-4 text-right">
              <div className="flex items-center justify-between text-sm text-muted">
                <span>{cart.total.toFixed(2)} SAR</span>
                <span>Subtotal</span>
              </div>
              <div className="flex items-center justify-between text-sm text-muted">
                <span>{service.toFixed(2)} SAR</span>
                <span>Service Charge (5%)</span>
              </div>
              <div className="heritage-divider" />
              <div className="flex items-center justify-between">
                <span className="text-2xl font-semibold text-secondary">
                  {total.toFixed(2)} SAR
                </span>
                <span className="font-serif-display text-3xl text-primary">
                  Total Amount
                </span>
              </div>
              <button
                onClick={() => void handleSubmit()}
                disabled={submitting}
                className="heritage-primary-button w-full justify-center"
              >
                {submitting ? "جارٍ إرسال الطلب..." : "Submit Order"}
              </button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
