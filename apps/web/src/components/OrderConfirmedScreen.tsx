import { motion } from "framer-motion";
import { CheckCircle2, Sparkles } from "lucide-react";
import type { OrderConfirmation } from "../types";

interface Props {
  order: OrderConfirmation;
  onBack: () => void;
}

export default function OrderConfirmedScreen({ order, onBack }: Props) {
  return (
    <div className="mx-auto max-w-2xl">
      <div className="heritage-panel overflow-hidden p-8 text-center">
        <div className="absolute inset-0 heritage-pattern opacity-25" />
        <div className="relative space-y-6">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 180, damping: 16 }}
            className="mx-auto flex h-28 w-28 items-center justify-center rounded-full border border-gold/30 bg-primary text-cream shadow-soft"
          >
            <CheckCircle2 size={56} />
          </motion.div>
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-3 py-1 text-[11px] uppercase tracking-[0.28em] text-secondary">
              <Sparkles size={14} />
              Order Confirmed
            </div>
            <h1 className="font-serif-display text-4xl text-primary">
              تم تأكيد طلبك
            </h1>
            <p className="mx-auto max-w-lg text-sm leading-7 text-muted">
              شكرًا لاختيارك المجلس الذكي. بدأنا تجهيز الطلب، وسيصل إلى طاولتك خلال
              وقت قصير.
            </p>
          </div>

          <div className="mx-auto max-w-xl rounded-[24px] border border-gold/20 bg-card/90 p-5 text-right shadow-soft">
            <div className="flex items-center justify-between border-b border-gold/15 pb-4">
              <span className="text-lg font-semibold text-secondary">
                {order.order_id}
              </span>
              <span className="font-serif-display text-2xl text-primary">
                رقم الطلب
              </span>
            </div>
            <div className="space-y-3 py-4">
              {order.items.map((item, index) => (
                <div key={item.meal_id + index} className="flex items-center justify-between text-sm">
                  <span className="font-medium text-secondary">
                    {(item.quantity * item.unit_price).toFixed(0)} {item.currency}
                  </span>
                  <span className="text-ink">
                    {item.name_ar} × {item.quantity}
                  </span>
                </div>
              ))}
            </div>
            <div className="heritage-divider" />
            <div className="flex items-center justify-between pt-4">
              <span className="text-xl font-semibold text-secondary">
                {order.total.toFixed(0)} {order.currency}
              </span>
              <span className="font-serif-display text-3xl text-primary">
                الإجمالي
              </span>
            </div>
          </div>

          <button onClick={onBack} className="heritage-primary-button mx-auto">
            طلب جديد
          </button>
        </div>
      </div>
    </div>
  );
}
