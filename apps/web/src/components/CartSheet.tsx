import { AnimatePresence, motion } from "framer-motion";
import { X, Trash2, CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { Cart, OrderConfirmation } from "../types";
import { getCart, submitOrder } from "../api/client";

interface Props {
  open: boolean;
  sessionId: string;
  onClose: () => void;
  onOrderPlaced: (order: OrderConfirmation) => void;
  reloadKey: number;
}

export default function CartSheet({
  open,
  sessionId,
  onClose,
  onOrderPlaced,
  reloadKey,
}: Props) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open || !sessionId) return;
    setLoading(true);
    getCart(sessionId)
      .then(setCart)
      .catch(() => setCart(null))
      .finally(() => setLoading(false));
  }, [open, sessionId, reloadKey]);

  const handleSubmit = async () => {
    if (!cart || cart.items.length === 0) return;
    setSubmitting(true);
    try {
      const order = await submitOrder(sessionId);
      onOrderPlaced(order);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 260, damping: 30 }}
            className="fixed bottom-0 inset-x-0 z-50 max-h-[85vh] rounded-t-[2rem]
                       glass border-t border-gold-300/30 shadow-glossy
                       flex flex-col"
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-12 h-1.5 rounded-full bg-gold-300/50" />
            </div>

            <div className="flex items-center justify-between px-6 pb-4 border-b border-white/10">
              <h2 className="font-display text-2xl text-gold-200">سلتك</h2>
              <button
                onClick={onClose}
                className="p-2 rounded-full bg-white/5 hover:bg-white/10"
                aria-label="إغلاق"
              >
                <X size={18} />
              </button>
            </div>

            {/* Items */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              {loading ? (
                <div className="flex justify-center py-10">
                  <Loader2 className="animate-spin text-gold-300" />
                </div>
              ) : !cart || cart.items.length === 0 ? (
                <div className="text-center py-10 text-cream/60">
                  <Trash2 className="mx-auto mb-3 opacity-40" />
                  السلة فارغة
                </div>
              ) : (
                cart.items.map((item, i) => (
                  <motion.div
                    key={item.meal_id + i}
                    initial={{ opacity: 0, x: -16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-center justify-between glass rounded-2xl p-3"
                  >
                    <div className="flex-1">
                      <div className="font-semibold text-cream">{item.name_ar}</div>
                      <div className="text-xs text-cream/50">
                        {item.quantity} × {item.unit_price} {item.currency}
                      </div>
                    </div>
                    <div className="font-bold text-gold-300">
                      {(item.quantity * item.unit_price).toFixed(0)}
                    </div>
                  </motion.div>
                ))
              )}
            </div>

            {/* Footer */}
            {cart && cart.items.length > 0 && (
              <div className="px-6 py-4 border-t border-white/10 space-y-3">
                <div className="flex items-baseline justify-between">
                  <span className="text-cream/70">الإجمالي</span>
                  <span className="font-black text-2xl text-gold-200">
                    {cart.total.toFixed(0)}
                    <span className="text-sm text-gold-400/70 mr-1">{cart.currency}</span>
                  </span>
                </div>
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="btn-gold sheen relative w-full text-lg disabled:opacity-60"
                >
                  {submitting ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 size={18} className="animate-spin" />
                      جاري الإرسال…
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      <CheckCircle2 size={18} />
                      تأكيد الطلب
                    </span>
                  )}
                </button>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
