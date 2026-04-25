import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bell,
  Bot,
  BookOpen,
  ConciergeBell,
  Home,
  Loader2,
  MessageSquare,
  ShoppingBag,
  Sparkles,
  Star,
} from "lucide-react";
import AdminDashboard from "./components/AdminDashboard";
import ChatScreen from "./components/ChatScreen";
import MenuBrowseScreen from "./components/MenuBrowseScreen";
import CartScreen from "./components/CartScreen";
import OrderConfirmedScreen from "./components/OrderConfirmedScreen";
import { fetchMenu, getCart, getSession, imageUrl, startSession } from "./api/client";
import type {
  ChatMessage,
  MenuMeal,
  OrderConfirmation,
  SessionStartPayload,
} from "./types";

type Screen = "home" | "chat" | "menu" | "cart" | "confirmed";
const SESSION_STORAGE_KEY = "al_nadeel_session_id";

function HomeTab({
  greeting,
  tableNumber,
  featuredMeals,
  onSelectScreen,
  onOpenChatSuggestion,
  onCallWaiter,
  cartCount,
}: {
  greeting: string;
  tableNumber?: number | null;
  featuredMeals: MenuMeal[];
  onSelectScreen: (screen: Screen) => void;
  onOpenChatSuggestion: (message: string) => void;
  onCallWaiter: () => void;
  cartCount: number;
}) {
  const heroMeal = featuredMeals[0];
  const secondaryMeal = featuredMeals[1];

  return (
    <div className="space-y-4 md:space-y-6">
      <section className="heritage-panel overflow-hidden p-4 md:p-6">
        <div className="absolute inset-0 heritage-pattern opacity-30" />
        <div className="relative flex flex-col gap-5">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-3 py-1 text-[11px] tracking-[0.28em] text-secondary uppercase">
            <Sparkles size={14} />
            Ahlan Wa Sahlan
          </div>
          <div className="space-y-2 md:space-y-3">
            <h1 className="font-serif-display text-3xl leading-tight text-primary md:text-4xl">
              المجلس الذكي لخدمة
              <br />
              الضيافة الراقية
            </h1>
            <p className="max-w-xl text-sm leading-6 text-muted md:text-[15px] md:leading-7">
              {greeting}
            </p>
            {tableNumber ? (
              <div className="inline-flex rounded-full border border-[rgba(212,175,55,0.28)] bg-[rgba(212,175,55,0.12)] px-3 py-1 text-xs tracking-[0.18em] text-secondary uppercase">
                Table {tableNumber}
              </div>
            ) : null}
          </div>
          <div className="heritage-divider" />
          <div className="grid gap-3 sm:grid-cols-3">
            <button
              onClick={() => onSelectScreen("menu")}
              className="heritage-action-card"
            >
              <BookOpen size={18} />
              <div>
                <div className="heritage-action-title">Browse Menu</div>
                <div className="heritage-action-copy">تصفح الأقسام والأطباق</div>
              </div>
            </button>
            <button
              onClick={() => onOpenChatSuggestion("أبي طبق مميز اليوم")}
              className="heritage-action-card"
            >
              <Bot size={18} />
              <div>
                <div className="heritage-action-title">AI Waiter</div>
                <div className="heritage-action-copy">ترشيحات ذكية بطابع نادل</div>
              </div>
            </button>
            <button onClick={onCallWaiter} className="heritage-action-card">
              <ConciergeBell size={18} />
              <div>
                <div className="heritage-action-title">Call Waiter</div>
                <div className="heritage-action-copy">استدعاء النادل للطاولة</div>
              </div>
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-3 md:gap-4 md:grid-cols-[1.15fr_0.85fr]">
        <button
          onClick={() => onOpenChatSuggestion("رشح لي أفضل طبق رئيسي")}
          className="heritage-feature-card text-right"
        >
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-primary/6 px-3 py-1 text-[11px] uppercase tracking-[0.28em] text-secondary">
              <Star size={14} />
              Chef&apos;s Recommendation
            </div>
            <h2 className="font-serif-display text-xl text-primary md:text-2xl">
              ابدأ حديثك مع النادل الذكي
            </h2>
            <p className="text-[13px] leading-5 text-muted md:text-sm md:leading-6">
              اسأل عن الترشيحات، المكونات، الحار والخفيف، أو اطلب اقتراحًا مقنعًا
              حسب ذوقك.
            </p>
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-gold/30 bg-primary text-cream shadow-soft md:h-16 md:w-16">
            <MessageSquare size={20} className="md:h-6 md:w-6" />
          </div>
        </button>

        <button
          onClick={() => onSelectScreen("cart")}
          className="heritage-summary-card text-right"
        >
          <div className="space-y-2">
            <div className="text-[11px] uppercase tracking-[0.3em] text-secondary">
              Your Platter
            </div>
            <div className="font-serif-display text-xl text-primary md:text-2xl">
              {cartCount} عنصر
            </div>
            <p className="text-[13px] leading-5 text-muted md:text-sm md:leading-6">
              راجع سلتك وأكمل الطلب أو عدّل الكميات من شاشة السلة.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 text-secondary">
            <ShoppingBag size={18} />
            الذهاب للسلة
          </div>
        </button>
      </section>

      <section className="space-y-3 md:space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-serif-display text-xl text-primary md:text-2xl">
              أصناف مقترحة اليوم
            </h2>
            <p className="text-sm text-muted">
              اختيارات مميزة يقدمها النادل أولاً عند التوصية.
            </p>
          </div>
          <button
            onClick={() => onSelectScreen("menu")}
            className="heritage-link-button"
          >
            عرض المنيو كاملًا
          </button>
        </div>

        <div className="grid gap-3 md:gap-4 md:grid-cols-2">
          {heroMeal && (
            <button
              onClick={() => onSelectScreen("menu")}
              className="heritage-dish-card text-right"
            >
                <img
                  src={imageUrl(heroMeal.image_url)}
                  alt={heroMeal.name_ar}
                  className="heritage-dish-image"
                />
              <div className="heritage-dish-overlay" />
              <div className="relative z-10 space-y-2 p-4 md:p-5">
                <div className="inline-flex rounded-full border border-gold/40 bg-background/85 px-3 py-1 text-[11px] uppercase tracking-[0.28em] text-secondary">
                  Signature Dish
                </div>
                <div className="font-serif-display text-xl text-cream md:text-2xl">
                  {heroMeal.name_ar}
                </div>
                <p className="max-w-md text-[13px] leading-5 text-cream/85 md:text-sm md:leading-6">
                  {heroMeal.sales_pitch_ar || heroMeal.description_ar}
                </p>
                <div className="text-base font-semibold text-gold md:text-lg">
                  {heroMeal.price} {heroMeal.currency}
                </div>
              </div>
            </button>
          )}
          {secondaryMeal && (
            <div className="heritage-panel p-3 md:p-4">
              <div className="flex h-full flex-col gap-3">
                <img
                  src={imageUrl(secondaryMeal.image_url)}
                  alt={secondaryMeal.name_ar}
                  className="h-36 w-full rounded-[18px] object-cover md:h-44"
                />
                <div className="space-y-2">
                  <div className="text-[11px] uppercase tracking-[0.28em] text-secondary">
                    Curated Pick
                  </div>
                  <h3 className="font-serif-display text-lg text-primary md:text-xl">
                    {secondaryMeal.name_ar}
                  </h3>
                  <p className="text-[13px] leading-5 text-muted md:text-sm md:leading-6">
                    {secondaryMeal.sales_pitch_ar || secondaryMeal.description_ar}
                  </p>
                </div>
                <button
                  onClick={() => onOpenChatSuggestion(`أبي مثل ${secondaryMeal.name_ar}`)}
                  className="heritage-ghost-button mt-auto"
                >
                  اسأل النادل عن هذا الطبق
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function BottomNav({
  active,
  cartCount,
  onChange,
}: {
  active: Screen;
  cartCount: number;
  onChange: (screen: Screen) => void;
}) {
  const items: Array<{
    id: Screen;
    label: string;
    icon: typeof Home;
  }> = [
    { id: "home", label: "Home", icon: Home },
    { id: "chat", label: "Chat", icon: MessageSquare },
    { id: "menu", label: "Menu", icon: BookOpen },
    { id: "cart", label: "Cart", icon: ShoppingBag },
  ];

  return (
    <nav className="mobile-bottom-nav-shell md:fixed md:inset-x-0 md:bottom-0 md:z-50 md:px-4 md:pb-4">
      <div className="mx-auto max-w-4xl">
        <div className="heritage-bottom-nav">
          {items.map((item) => {
            const Icon = item.icon;
            const activeItem = active === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onChange(item.id)}
                className={activeItem ? "heritage-nav-item active" : "heritage-nav-item"}
              >
                <div className="relative">
                  <Icon size={18} />
                  {item.id === "cart" && cartCount > 0 && (
                    <span className="heritage-nav-badge">{cartCount}</span>
                  )}
                </div>
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  if (typeof window !== "undefined" && window.location.pathname.startsWith("/admin")) {
    return <AdminDashboard />;
  }

  const [screen, setScreen] = useState<Screen>("home");
  const [session, setSession] = useState<SessionStartPayload | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [menu, setMenu] = useState<MenuMeal[]>([]);
  const [menuLoading, setMenuLoading] = useState(true);
  const [cartCount, setCartCount] = useState(0);
  const [cartReloadKey, setCartReloadKey] = useState(0);
  const [order, setOrder] = useState<OrderConfirmation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [callWaiterNotice, setCallWaiterNotice] = useState<string | null>(null);
  const [queuedChatPrompt, setQueuedChatPrompt] = useState<string | null>(null);

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    setLoading(true);
    setError(null);
    try {
      const tableParam =
        typeof window !== "undefined"
          ? Number(window.location.search ? new URLSearchParams(window.location.search).get("table") : null)
          : NaN;
      const tableNumber = Number.isFinite(tableParam) && tableParam > 0 ? tableParam : null;
      const storedSessionId =
        typeof window !== "undefined" ? window.localStorage.getItem(SESSION_STORAGE_KEY) : null;

      const [restoredSession, menuData] = await Promise.all([
        storedSessionId ? getSession(storedSessionId).catch(() => null) : Promise.resolve(null),
        fetchMenu(),
      ]);

      let activeSession: SessionStartPayload;
      let restoredHistory: ChatMessage[] = [];

      if (
        restoredSession &&
        (tableNumber == null || restoredSession.table_number == null || restoredSession.table_number === tableNumber)
      ) {
        activeSession = restoredSession;
        restoredHistory = restoredSession.history.map((message, index) => ({
          id: `history-${index}`,
          role: message.role,
          content: message.content,
        }));
      } else {
        const started = await startSession(tableNumber);
        activeSession = started;
        if (typeof window !== "undefined") {
          window.localStorage.setItem(SESSION_STORAGE_KEY, started.session_id);
        }
      }

      if (typeof window !== "undefined" && activeSession.session_id) {
        window.localStorage.setItem(SESSION_STORAGE_KEY, activeSession.session_id);
      }

      setSession(activeSession);
      setChatHistory(restoredHistory);
      setMenu(menuData.meals);
      setMenuLoading(false);
      const cart = await getCart(activeSession.session_id);
      setCartCount(cart.items.reduce((sum, item) => sum + item.quantity, 0));
    } catch (err) {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(SESSION_STORAGE_KEY);
      }
      setError(err instanceof Error ? err.message : "تعذر تحميل التطبيق");
    } finally {
      setLoading(false);
    }
  }

  async function refreshCartCount() {
    if (!session?.session_id) return;
    try {
      const cart = await getCart(session.session_id);
      setCartCount(cart.items.reduce((sum, item) => sum + item.quantity, 0));
    } catch {
      /* ignore */
    }
  }

  async function handleCartUpdated() {
    setCartReloadKey((current) => current + 1);
    await refreshCartCount();
  }

  function handleOpenChatPrompt(message: string) {
    setQueuedChatPrompt(message);
    setScreen("chat");
  }

  function handleCallWaiter() {
    setCallWaiterNotice("تم إرسال نداء للنادل، وسيصل إلى طاولتك خلال لحظات.");
    window.setTimeout(() => setCallWaiterNotice(null), 2800);
  }

  const featuredMeals = useMemo(
    () =>
      [...menu]
        .sort((a, b) => {
          if (a.featured !== b.featured) return a.featured ? -1 : 1;
          if (a.recommendation_rank !== b.recommendation_rank) {
            return b.recommendation_rank - a.recommendation_rank;
          }
          return b.price - a.price;
        })
        .slice(0, 2)
        .map((meal) => ({
          ...meal,
          image_url: meal.image_url,
        })),
    [menu]
  );

  const shouldShowConfirmed = screen === "confirmed" && order;

  if (loading) {
    return (
      <div className="heritage-app-shell">
        <div className="heritage-bg" />
        <div className="mx-auto flex min-h-[100dvh] max-w-md items-center justify-center px-6">
          <div className="heritage-panel flex w-full flex-col items-center gap-4 p-8 text-center">
            <Loader2 className="animate-spin text-primary" size={28} />
            <h1 className="font-serif-display text-3xl text-primary">Al Nadeel AI</h1>
            <p className="text-sm leading-6 text-muted">
              نحضّر لك تجربة ضيافة ذكية بطابع المجلس العربي الأصيل.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="heritage-app-shell">
        <div className="heritage-bg" />
        <div className="mx-auto flex min-h-[100dvh] max-w-md items-center justify-center px-6">
          <div className="heritage-panel space-y-4 p-8 text-center">
            <h1 className="font-serif-display text-3xl text-primary">تعذر تحميل التطبيق</h1>
            <p className="text-sm leading-6 text-muted">{error}</p>
            <button onClick={() => void bootstrap()} className="heritage-primary-button">
              إعادة المحاولة
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="heritage-app-shell">
      <div className="heritage-bg" />
      <header className="heritage-topbar">
        <div className="flex items-center gap-3">
          <div className="heritage-brand-mark">
            <Sparkles size={18} />
          </div>
          <div>
            <div className="font-serif-display text-lg uppercase tracking-[0.18em] text-primary md:text-xl md:tracking-[0.2em]">
              Al-Majlis AI
            </div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-secondary md:text-[11px] md:tracking-[0.28em]">
              Smart Waiter
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="heritage-icon-button" onClick={handleCallWaiter}>
            <ConciergeBell size={18} />
          </button>
          <button className="heritage-icon-button">
            <Bell size={18} />
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-3 pb-36 pt-20 md:px-6 md:pb-32 md:pt-24">
        <AnimatePresence>
          {callWaiterNotice && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mb-4 rounded-2xl border border-gold/30 bg-background/90 px-4 py-3 text-sm text-secondary shadow-soft backdrop-blur-md"
            >
              {callWaiterNotice}
            </motion.div>
          )}
        </AnimatePresence>

        {shouldShowConfirmed ? (
          <OrderConfirmedScreen
            order={order}
            onBack={() => {
              setOrder(null);
              setScreen("home");
              void refreshCartCount();
            }}
          />
        ) : (
          <div className="space-y-6">
            <section className={screen === "home" ? "block" : "hidden"}>
              <HomeTab
                greeting={session.greeting}
                tableNumber={session.table_number}
                featuredMeals={featuredMeals}
                onSelectScreen={setScreen}
                onOpenChatSuggestion={handleOpenChatPrompt}
                onCallWaiter={handleCallWaiter}
                cartCount={cartCount}
              />
            </section>

            <section className={screen === "chat" ? "block" : "hidden"}>
              <ChatScreen
                sessionId={session.session_id}
                greeting={session.greeting}
                suggestions={session.suggestions}
                initialMessages={chatHistory}
                onOrderPlaced={(placed) => {
                  setOrder(placed);
                  setScreen("confirmed");
                }}
                onCartUpdated={() => void handleCartUpdated()}
                onOpenCart={() => setScreen("cart")}
                queuedPrompt={queuedChatPrompt}
                onQueuedPromptHandled={() => setQueuedChatPrompt(null)}
                onCallWaiter={handleCallWaiter}
              />
            </section>

            <section className={screen === "menu" ? "block" : "hidden"}>
              <MenuBrowseScreen
                meals={menu}
                loading={menuLoading}
                sessionId={session.session_id}
                onCartUpdated={() => void handleCartUpdated()}
                onAskWaiter={(message) => handleOpenChatPrompt(message)}
              />
            </section>

            <section className={screen === "cart" ? "block" : "hidden"}>
              <CartScreen
                sessionId={session.session_id}
                active={screen === "cart"}
                reloadKey={cartReloadKey}
                onCartUpdated={() => void handleCartUpdated()}
                onOrderPlaced={(placed) => {
                  setOrder(placed);
                  setScreen("confirmed");
                }}
              />
            </section>
          </div>
        )}
      </main>

      {!shouldShowConfirmed && (
        <BottomNav active={screen} cartCount={cartCount} onChange={setScreen} />
      )}
    </div>
  );
}
