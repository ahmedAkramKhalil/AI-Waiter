import { motion } from "framer-motion";
import { ChefHat, Sparkles } from "lucide-react";

interface Props {
  onStart: () => void;
  loading?: boolean;
}

export default function SplashScreen({ onStart, loading }: Props) {
  return (
    <div className="relative z-10 h-full w-full flex flex-col items-center justify-between px-6 py-10 text-center">
      {/* Top ornament */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full flex justify-center"
      >
        <div className="chip text-gold-200">
          <Sparkles size={12} />
          تجربة ضيافة ذكية
        </div>
      </motion.div>

      {/* Hero */}
      <div className="flex flex-col items-center gap-6">
        <motion.div
          initial={{ scale: 0.6, opacity: 0, rotateY: -30 }}
          animate={{ scale: 1, opacity: 1, rotateY: 0 }}
          transition={{ type: "spring", stiffness: 120, damping: 14 }}
          style={{ transformPerspective: 1000 }}
          className="relative w-36 h-36 rounded-full glass-gold sheen flex items-center justify-center animate-float"
        >
          <div className="absolute inset-2 rounded-full bg-wine-800/40 border border-gold-300/20" />
          <ChefHat size={64} className="text-gold-200 relative z-10 drop-shadow-lg" />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.6 }}
          className="space-y-2"
        >
          <h1 className="font-display text-4xl font-bold text-gold-200 drop-shadow-lg">
            مطعم الأصالة
          </h1>
          <p className="text-cream/70 text-sm leading-relaxed max-w-xs">
            مرحباً بك. أنا <span className="text-gold-300 font-bold">أصيل</span> — نادلك الذكي.
            <br />
            اسألني عما تشتهيه، وسأقترح عليك الأطباق المناسبة.
          </p>
        </motion.div>
      </div>

      {/* CTA */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.5 }}
        className="w-full max-w-sm space-y-3"
      >
        <button
          onClick={onStart}
          disabled={loading}
          className="btn-gold w-full text-lg sheen relative disabled:opacity-60"
        >
          {loading ? "جاري التحضير…" : "ابدأ المحادثة"}
        </button>
        <p className="text-cream/40 text-xs">أكلات عربية أصيلة · خدمة ذكية بالذكاء الاصطناعي</p>
      </motion.div>
    </div>
  );
}
