import { motion } from "framer-motion";
import { CheckCircle2, Sparkles } from "lucide-react";
import type { OrderConfirmation } from "../types";

interface Props {
  order: OrderConfirmation;
  onBack: () => void;
}

export default function OrderConfirmedScreen({ order, onBack }: Props) {
  return (
    <div className="relative z-10 h-full w-full flex flex-col items-center justify-center px-6 py-10 text-center">
      <motion.div
        initial={{ scale: 0.5, opacity: 0, rotate: -20 }}
        animate={{ scale: 1, opacity: 1, rotate: 0 }}
        transition={{ type: "spring", stiffness: 180, damping: 15 }}
        className="relative w-32 h-32 rounded-full glass-gold sheen flex items-center justify-center mb-6"
      >
        <CheckCircle2 size={64} className="text-gold-100 drop-shadow-lg" strokeWidth={2.5} />
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="font-display text-3xl text-gold-200 mb-2"
      >
        تم تأكيد طلبك!
      </motion.h1>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="text-cream/70 text-sm mb-6"
      >
        شكراً لك. سيتم تجهيز طلبك في الحال.
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass rounded-3xl p-5 w-full max-w-sm space-y-3"
      >
        <div className="flex items-center justify-between text-sm">
          <span className="text-cream/60">رقم الطلب</span>
          <span className="font-mono font-bold text-gold-200">{order.order_id}</span>
        </div>
        <div className="h-px bg-white/10" />
        {order.items.map((item, i) => (
          <div key={i} className="flex justify-between text-sm text-cream/90">
            <span>
              {item.name_ar} × {item.quantity}
            </span>
            <span className="text-gold-300">
              {(item.quantity * item.unit_price).toFixed(0)}
            </span>
          </div>
        ))}
        <div className="h-px bg-white/10" />
        <div className="flex justify-between items-baseline">
          <span className="text-cream/70">الإجمالي</span>
          <span className="text-2xl font-black text-gold-200">
            {order.total.toFixed(0)}
            <span className="text-xs mr-1 text-gold-400/80">SAR</span>
          </span>
        </div>
      </motion.div>

      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        onClick={onBack}
        className="btn-ghost mt-8 flex items-center gap-2"
      >
        <Sparkles size={16} />
        طلب جديد
      </motion.button>
    </div>
  );
}
