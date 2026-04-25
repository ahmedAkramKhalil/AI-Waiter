import { useEffect, useMemo, useState } from "react";
import {
  BellRing,
  Copy,
  ImagePlus,
  PencilLine,
  Plus,
  QrCode,
  Save,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import {
  deleteMenuMeal,
  fetchAdminOrders,
  fetchMenu,
  imageUrl,
  markAdminOrdersSeen,
  saveMenuMeal,
  uploadMenuImage,
} from "../api/client";
import type { AdminOrdersResponse, MenuMeal, OrderConfirmation } from "../types";

const EMPTY_MEAL: MenuMeal = {
  id: "",
  name_ar: "",
  description_ar: "",
  ingredients: [],
  allergens: [],
  tags: [],
  category: "",
  price: 0,
  currency: "SAR",
  spice_level: 1,
  calories: 0,
  image_id: "",
  image_url: "",
  featured: false,
  recommendation_rank: 0,
  sales_pitch_ar: "",
};

function parseCommaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function mealToForm(meal: MenuMeal): MenuMeal {
  return {
    ...meal,
    ingredients: [...meal.ingredients],
    allergens: [...meal.allergens],
    tags: [...meal.tags],
  };
}

function nextMealId(meals: MenuMeal[]): string {
  const maxNumber = meals.reduce((max, meal) => {
    const match = meal.id.match(/MEAL_(\d+)/);
    const value = match ? Number(match[1]) : 0;
    return Math.max(max, value);
  }, 0);
  return `MEAL_${String(maxNumber + 1).padStart(3, "0")}`;
}

export default function AdminDashboard() {
  const [meals, setMeals] = useState<MenuMeal[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [form, setForm] = useState<MenuMeal>(EMPTY_MEAL);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string>("");
  const [ordersFeed, setOrdersFeed] = useState<AdminOrdersResponse | null>(null);
  const [tablesCount, setTablesCount] = useState(12);

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    void loadOrders();
    const interval = window.setInterval(() => {
      void loadOrders();
    }, 5000);
    return () => window.clearInterval(interval);
  }, []);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchMenu();
      setMeals(data.meals);
      setCategories(data.categories);
      if (data.meals[0]) {
        setSelectedId(data.meals[0].id);
        setForm(mealToForm(data.meals[0]));
      } else {
        setSelectedId("");
        setForm(EMPTY_MEAL);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "تعذر تحميل المنيو");
    } finally {
      setLoading(false);
    }
  }

  async function loadOrders() {
    try {
      const data = await fetchAdminOrders();
      setOrdersFeed(data);
    } catch {
      /* ignore */
    }
  }

  const sortedMeals = useMemo(
    () =>
      [...meals].sort((a, b) => {
        if (a.featured !== b.featured) return a.featured ? -1 : 1;
        if (a.recommendation_rank !== b.recommendation_rank) {
          return b.recommendation_rank - a.recommendation_rank;
        }
        return a.name_ar.localeCompare(b.name_ar, "ar");
      }),
    [meals]
  );

  const appBaseUrl =
    typeof window !== "undefined" ? window.location.origin : "http://localhost:5173";
  const qrTables = useMemo(
    () => Array.from({ length: tablesCount }, (_, idx) => idx + 1),
    [tablesCount]
  );
  const groupedOrders = useMemo(() => {
    const grouped = new Map<number | null, OrderConfirmation[]>();
    for (const order of ordersFeed?.orders ?? []) {
      const key = order.table_number ?? null;
      const current = grouped.get(key) ?? [];
      current.push(order);
      grouped.set(key, current);
    }
    return grouped;
  }, [ordersFeed]);

  function selectMeal(meal: MenuMeal) {
    setSelectedId(meal.id);
    setForm(mealToForm(meal));
    setMessage("");
  }

  function createNewMeal() {
    const nextId = nextMealId(meals);
    setSelectedId("");
    setForm({ ...EMPTY_MEAL, id: nextId });
    setMessage("جهّزت نموذج صنف جديد. أضف التفاصيل ثم احفظ.");
  }

  function updateForm<K extends keyof MenuMeal>(key: K, value: MenuMeal[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleImageUpload(file: File) {
    try {
      const uploaded = await uploadMenuImage(file);
      const nextForm = {
        ...form,
        image_id: uploaded.image_id,
        image_url: uploaded.image_url,
      };
      setForm(nextForm);
      setMeals((prev) =>
        prev.map((meal) =>
          meal.id === nextForm.id
            ? { ...meal, image_id: uploaded.image_id, image_url: uploaded.image_url }
            : meal
        )
      );

      if (form.id && meals.some((meal) => meal.id === form.id)) {
        const saved = await saveMenuMeal(nextForm);
        setMeals((prev) =>
          prev.map((meal) => (meal.id === saved.id ? saved : meal))
        );
        setForm(mealToForm(saved));
        setMessage("تم رفع الصورة وربطها بالصنف مباشرة.");
        return;
      }

      setForm((prev) => ({
        ...prev,
        image_id: uploaded.image_id,
        image_url: uploaded.image_url,
      }));
      setMessage("تم رفع الصورة. احفظ الصنف لتثبيت الربط.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "تعذر رفع الصورة");
    }
  }

  function handleSave() {
    void (async () => {
      setSaving(true);
      try {
        const saved = await saveMenuMeal(form);
        const latestMenu = await fetchMenu();
        setMeals(latestMenu.meals);
        setCategories(latestMenu.categories);
        setSelectedId(saved.id);
        setForm(mealToForm(saved));
        setMessage("تم حفظ الصنف وتحديث المنيو.");
      } catch (err) {
        setMessage(err instanceof Error ? err.message : "تعذر حفظ الصنف");
      } finally {
        setSaving(false);
      }
    })();
  }

  function handleDelete() {
    if (!form.id) return;
    const confirmed = window.confirm(`حذف الصنف ${form.name_ar || form.id}؟`);
    if (!confirmed) return;
    void (async () => {
      setSaving(true);
      try {
        await deleteMenuMeal(form.id);
        const nextMeals = meals.filter((meal) => meal.id !== form.id);
        setMeals(nextMeals);
        if (nextMeals[0]) {
          setSelectedId(nextMeals[0].id);
          setForm(mealToForm(nextMeals[0]));
        } else {
          setSelectedId("");
          setForm(EMPTY_MEAL);
        }
        setMessage("تم حذف الصنف.");
      } catch (err) {
        setMessage(err instanceof Error ? err.message : "تعذر حذف الصنف");
      } finally {
        setSaving(false);
      }
    })();
  }

  function qrImageUrl(tableNumber: number) {
    const url = `${appBaseUrl}/?table=${tableNumber}`;
    return `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(url)}`;
  }

  async function copyTableLink(tableNumber: number) {
    const url = `${appBaseUrl}/?table=${tableNumber}`;
    try {
      await navigator.clipboard.writeText(url);
      setMessage(`تم نسخ رابط Table ${tableNumber}`);
    } catch {
      setMessage("تعذر نسخ الرابط");
    }
  }

  return (
    <div className="heritage-app-shell min-h-[100dvh] text-ink">
      <div className="heritage-bg" />
      <div className="relative z-10 mx-auto max-w-7xl px-4 py-6 md:px-6">
        <div className="heritage-panel mb-6 p-6">
          <div className="absolute inset-0 heritage-pattern opacity-20" />
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="relative">
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-[rgba(212,175,55,0.28)] bg-[rgba(212,175,55,0.12)] px-3 py-1 text-xs text-secondary">
                <Sparkles size={14} />
                لوحة إدارة المنيو
              </div>
              <h1 className="font-serif-display text-4xl text-primary">تحكم بالمنيو وبترشيحات النادل</h1>
              <p className="mt-2 max-w-2xl text-sm leading-7 text-muted">
                أضف الأصناف، عدّل الأسعار والوصف، ارفع الصور، وحدد ما الذي يجب أن يرشحه
                النادل أولاً مع عبارة إقناع مناسبة.
              </p>
            </div>
            <button onClick={createNewMeal} className="btn-gold inline-flex items-center gap-2">
              <Plus size={18} />
              صنف جديد
            </button>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
          <section className="heritage-panel p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-serif-display text-2xl text-primary">الأصناف</h2>
              <span className="text-xs text-muted">{sortedMeals.length} صنف</span>
            </div>
            <div className="space-y-3 overflow-y-auto pr-1 lg:max-h-[calc(100dvh-220px)]">
              {loading && <div className="text-sm text-muted">جاري تحميل المنيو...</div>}
              {!loading &&
                sortedMeals.map((meal) => (
                  <button
                    key={meal.id}
                    onClick={() => selectMeal(meal)}
                    className={`w-full rounded-3xl border p-3 text-right transition ${
                      selectedId === meal.id
                        ? "border-[rgba(212,175,55,0.38)] bg-[rgba(212,175,55,0.12)] shadow-soft"
                        : "border-[rgba(212,175,55,0.14)] bg-white/55 hover:bg-white/80"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-bold text-primary">{meal.name_ar}</div>
                        <div className="mt-1 text-xs text-muted">
                          {meal.category} • {meal.price} ريال
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1 text-[10px]">
                        {meal.featured && (
                          <span className="rounded-full bg-[rgba(212,175,55,0.18)] px-2 py-1 text-secondary">
                            مرشح أولاً
                          </span>
                        )}
                        {meal.recommendation_rank > 0 && (
                          <span className="rounded-full bg-[rgba(107,0,1,0.06)] px-2 py-1 text-muted">
                            أولوية {meal.recommendation_rank}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                ))}
            </div>
          </section>

          <section className="heritage-panel p-5 md:p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="font-serif-display text-3xl text-primary">تفاصيل الصنف</h2>
                <p className="mt-1 text-sm text-muted">
                  أي تغيير تحفظه هنا يحدّث المنيو والبحث وترشيحات النادل.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={handleDelete} className="btn-ghost inline-flex items-center gap-2">
                  <Trash2 size={16} />
                  حذف
                </button>
                <button onClick={handleSave} disabled={saving} className="btn-gold inline-flex items-center gap-2">
                  <Save size={16} />
                  {saving ? "جارٍ الحفظ..." : "حفظ"}
                </button>
              </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm text-muted">المعرف</span>
                  <input className="admin-input" value={form.id} onChange={(e) => updateForm("id", e.target.value)} />
                </label>
                <label className="space-y-2">
                  <span className="text-sm text-muted">اسم الصنف</span>
                  <input className="admin-input" value={form.name_ar} onChange={(e) => updateForm("name_ar", e.target.value)} />
                </label>
                <label className="space-y-2 md:col-span-2">
                  <span className="text-sm text-muted">الوصف</span>
                  <textarea className="admin-input min-h-28" value={form.description_ar} onChange={(e) => updateForm("description_ar", e.target.value)} />
                </label>
                <label className="space-y-2">
                  <span className="text-sm text-muted">التصنيف</span>
                  <input
                    list="menu-categories"
                    className="admin-input"
                    value={form.category}
                    onChange={(e) => updateForm("category", e.target.value)}
                  />
                  <datalist id="menu-categories">
                    {categories.map((category) => (
                      <option key={category} value={category} />
                    ))}
                  </datalist>
                </label>
                <label className="space-y-2">
                  <span className="text-sm text-muted">السعر</span>
                  <input
                    type="number"
                    className="admin-input"
                    value={form.price}
                    onChange={(e) => updateForm("price", Number(e.target.value))}
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm text-muted">السعرات</span>
                  <input
                    type="number"
                    className="admin-input"
                    value={form.calories}
                    onChange={(e) => updateForm("calories", Number(e.target.value))}
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm text-muted">درجة الحار</span>
                  <input
                    type="number"
                    min={0}
                    max={5}
                    className="admin-input"
                    value={form.spice_level}
                    onChange={(e) => updateForm("spice_level", Number(e.target.value))}
                  />
                </label>
                <label className="space-y-2 md:col-span-2">
                  <span className="text-sm text-muted">المكونات</span>
                  <input
                    className="admin-input"
                    value={form.ingredients.join(", ")}
                    onChange={(e) => updateForm("ingredients", parseCommaList(e.target.value))}
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm text-muted">الوسوم</span>
                  <input
                    className="admin-input"
                    value={form.tags.join(", ")}
                    onChange={(e) => updateForm("tags", parseCommaList(e.target.value))}
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm text-muted">الحساسيات</span>
                  <input
                    className="admin-input"
                    value={form.allergens.join(", ")}
                    onChange={(e) => updateForm("allergens", parseCommaList(e.target.value))}
                  />
                </label>
                <label className="space-y-2 md:col-span-2">
                  <span className="text-sm text-muted">عبارة الإقناع للنادل</span>
                  <textarea
                    className="admin-input min-h-24"
                    value={form.sales_pitch_ar}
                    onChange={(e) => updateForm("sales_pitch_ar", e.target.value)}
                    placeholder="مثال: من أكثر الأطباق طلبًا وطعمه متوازن جدًا."
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm text-muted">أولوية الترشيح</span>
                  <input
                    type="number"
                    min={0}
                    className="admin-input"
                    value={form.recommendation_rank}
                    onChange={(e) => updateForm("recommendation_rank", Number(e.target.value))}
                  />
                </label>
                <label className="flex items-center gap-3 rounded-3xl border border-[rgba(212,175,55,0.24)] bg-[rgba(212,175,55,0.12)] px-4 py-3 text-sm text-primary">
                  <input
                    type="checkbox"
                    checked={form.featured}
                    onChange={(e) => updateForm("featured", e.target.checked)}
                  />
                  هذا الصنف يجب أن يرشحه النادل أولاً
                </label>
              </div>

              <div className="space-y-4">
                <div className="overflow-hidden rounded-[28px] border border-[rgba(212,175,55,0.18)] bg-white/60 shadow-soft">
                  {form.image_url || form.image_id ? (
                    <img
                      src={imageUrl(form.image_url || `/images/${form.image_id}`)}
                      alt={form.name_ar}
                      className="h-72 w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-72 items-center justify-center bg-white/50 text-muted">
                      <ImagePlus size={34} />
                    </div>
                  )}
                </div>
                <label className="btn-ghost flex cursor-pointer items-center justify-center gap-2">
                  <Upload size={16} />
                  رفع صورة جديدة
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) void handleImageUpload(file);
                    }}
                  />
                </label>
                <div className="rounded-[24px] border border-[rgba(212,175,55,0.18)] bg-white/55 p-4 text-sm text-muted">
                  <div className="mb-2 flex items-center gap-2 text-secondary">
                    <PencilLine size={16} />
                    كيف سيستخدمه النادل؟
                  </div>
                  <p>
                    عندما يكون الصنف <strong>مرشح أولاً</strong> أو له <strong>أولوية ترشيح</strong> أعلى،
                    سيظهر للنادل قبل غيره إذا كان مناسبًا لطلب العميل.
                  </p>
                </div>
              </div>
            </div>

            <AnimatePresence>
              {message && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  className="mt-5 rounded-2xl border border-[rgba(212,175,55,0.24)] bg-[rgba(212,175,55,0.12)] px-4 py-3 text-sm text-secondary"
                >
                  {message}
                </motion.div>
              )}
            </AnimatePresence>
          </section>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_1fr]">
          <section className="heritage-panel p-5 md:p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-[rgba(212,175,55,0.28)] bg-[rgba(212,175,55,0.12)] px-3 py-1 text-xs text-secondary">
                  <QrCode size={14} />
                  QR Generator
                </div>
                <h2 className="font-serif-display text-3xl text-primary">QR لكل طاولة</h2>
                <p className="mt-1 text-sm text-muted">
                  عند مسح الكود، يفتح التطبيق ويثبت رقم الطاولة داخل الجلسة تلقائيًا.
                </p>
              </div>
              <div className="w-24">
                <input
                  type="number"
                  min={1}
                  className="admin-input text-center"
                  value={tablesCount}
                  onChange={(e) => setTablesCount(Math.max(1, Number(e.target.value) || 1))}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {qrTables.map((tableNumber) => (
                <div
                  key={tableNumber}
                  className="rounded-[26px] border border-[rgba(212,175,55,0.18)] bg-white/70 p-4 shadow-soft"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <div className="font-serif-display text-2xl text-primary">
                      Table {tableNumber}
                    </div>
                    <button
                      onClick={() => void copyTableLink(tableNumber)}
                      className="heritage-icon-button"
                    >
                      <Copy size={16} />
                    </button>
                  </div>
                  <img
                    src={qrImageUrl(tableNumber)}
                    alt={`QR for table ${tableNumber}`}
                    className="mx-auto h-40 w-40 rounded-[20px] border border-[rgba(212,175,55,0.16)] bg-white p-2"
                  />
                  <div className="mt-3 text-center text-xs text-muted">
                    يمسح العميل الكود لبدء جلسة مرتبطة بهذه الطاولة.
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="heritage-panel p-5 md:p-6">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-[rgba(212,175,55,0.28)] bg-[rgba(212,175,55,0.12)] px-3 py-1 text-xs text-secondary">
                  <BellRing size={14} />
                  Live Orders
                </div>
                <h2 className="font-serif-display text-3xl text-primary">طلبات الطاولات</h2>
                <p className="mt-1 text-sm text-muted">
                  تصل الطلبات الجديدة هنا مع رقم الطاولة، ويمكنك رؤية كل طاولة وما طلبته.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="rounded-full border border-[rgba(212,175,55,0.26)] bg-[rgba(212,175,55,0.12)] px-3 py-1 text-sm text-secondary">
                  {ordersFeed?.unseen_count ?? 0} جديد
                </div>
                <button
                  onClick={() => void markAdminOrdersSeen().then(loadOrders)}
                  className="btn-ghost"
                >
                  تم الاطلاع
                </button>
              </div>
            </div>

            <div className="space-y-4">
              {(ordersFeed?.tables ?? []).length === 0 ? (
                <div className="rounded-[24px] border border-[rgba(212,175,55,0.16)] bg-white/60 p-6 text-center text-sm text-muted">
                  لا توجد طلبات حتى الآن.
                </div>
              ) : (
                ordersFeed?.tables.map((table) => {
                  const tableOrders = groupedOrders.get(table.table_number ?? null) ?? [];
                  return (
                    <div
                      key={String(table.table_number)}
                      className="rounded-[24px] border border-[rgba(212,175,55,0.16)] bg-white/65 p-4 shadow-soft"
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <div>
                          <div className="font-serif-display text-2xl text-primary">
                            {table.table_number ? `Table ${table.table_number}` : "بدون طاولة"}
                          </div>
                          <div className="text-xs text-muted">
                            {table.orders_count} طلب • {table.total_value.toFixed(2)} SAR
                          </div>
                        </div>
                        {table.unseen_count > 0 ? (
                          <div className="rounded-full bg-[rgba(107,0,1,0.12)] px-3 py-1 text-xs text-primary">
                            {table.unseen_count} جديد
                          </div>
                        ) : (
                          <div className="rounded-full bg-[rgba(212,175,55,0.12)] px-3 py-1 text-xs text-secondary">
                            تمت المراجعة
                          </div>
                        )}
                      </div>
                      <div className="space-y-3">
                        {tableOrders.map((order) => (
                          <div
                            key={order.order_id}
                            className={`rounded-[20px] border px-4 py-3 text-right ${
                              order.seen_by_admin
                                ? "border-[rgba(212,175,55,0.14)] bg-white/55"
                                : "border-[rgba(107,0,1,0.16)] bg-[rgba(107,0,1,0.05)]"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="text-sm font-semibold text-secondary">
                                {order.total.toFixed(2)} {order.currency}
                              </div>
                              <div>
                                <div className="font-semibold text-primary">{order.order_id}</div>
                                <div className="text-xs text-muted">
                                  {order.timestamp
                                    ? new Date(order.timestamp).toLocaleString()
                                    : ""}
                                </div>
                              </div>
                            </div>
                            <div className="mt-2 space-y-1 text-sm text-ink">
                              {order.items.map((item, idx) => (
                                <div key={item.meal_id + idx}>
                                  {item.name_ar} × {item.quantity}
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
