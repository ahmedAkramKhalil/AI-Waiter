import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import SplashScreen from "./components/SplashScreen";
import ChatScreen from "./components/ChatScreen";
import OrderConfirmedScreen from "./components/OrderConfirmedScreen";
import { startSession } from "./api/client";
import type { OrderConfirmation } from "./types";

type Screen = "splash" | "chat" | "confirmed";

export default function App() {
  const [screen, setScreen] = useState<Screen>("splash");
  const [sessionId, setSessionId] = useState<string>("");
  const [order, setOrder] = useState<OrderConfirmation | null>(null);
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    setLoading(true);
    try {
      const id = await startSession();
      setSessionId(id);
      setScreen("chat");
    } catch (err) {
      alert("تعذر الاتصال بالخادم. تحقق من VITE_API_BASE.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleOrderPlaced = (o: OrderConfirmation) => {
    setOrder(o);
    setScreen("confirmed");
  };

  const handleRestart = () => {
    setOrder(null);
    setScreen("splash");
    setSessionId("");
  };

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-restaurant">
      <div className="ambient" />

      {/* Mobile frame — centered on large screens, full on mobile */}
      <div className="relative z-10 h-full w-full max-w-md mx-auto shadow-2xl">
        <AnimatePresence mode="wait">
          {screen === "splash" && (
            <motion.div
              key="splash"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.4 }}
              className="absolute inset-0"
            >
              <SplashScreen onStart={handleStart} loading={loading} />
            </motion.div>
          )}

          {screen === "chat" && (
            <motion.div
              key="chat"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
              className="absolute inset-0"
            >
              <ChatScreen
                sessionId={sessionId}
                onOrderPlaced={handleOrderPlaced}
              />
            </motion.div>
          )}

          {screen === "confirmed" && order && (
            <motion.div
              key="confirmed"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="absolute inset-0"
            >
              <OrderConfirmedScreen order={order} onBack={handleRestart} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
