export interface MealCard {
  meal_id: string;
  name_ar: string;
  price: number;
  currency: string;
  image_url: string;
  spice_level: number;
  calories: number;
}

export interface ChoiceOption {
  id: string;
  label: string;
  value: string;
}

export interface ChoiceQuestion {
  id: string;
  label: string;
  options: ChoiceOption[];
}

export interface MenuMeal {
  id: string;
  name_ar: string;
  description_ar: string;
  ingredients: string[];
  allergens: string[];
  tags: string[];
  category: string;
  price: number;
  currency: string;
  spice_level: number;
  calories: number;
  image_id: string;
  image_url: string;
  featured: boolean;
  recommendation_rank: number;
  sales_pitch_ar: string;
}

export interface MenuResponse {
  meals: MenuMeal[];
  categories: string[];
}

export interface ImageUploadResponse {
  image_id: string;
  image_url: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  cards?: MealCard[];
  choices?: ChoiceQuestion[];
  choicesSubmitLabel?: string;
  streaming?: boolean;
}

export interface CartItem {
  meal_id: string;
  name_ar: string;
  quantity: number;
  unit_price: number;
  currency: string;
}

export interface Cart {
  session_id: string;
  items: CartItem[];
  total: number;
  currency: string;
}

export interface OrderConfirmation {
  order_id: string;
  session_id: string;
  items: CartItem[];
  total: number;
  currency: string;
  table_number?: number | null;
  notes_ar?: string | null;
  status: string;
  estimated_minutes?: number;
  timestamp?: string;
  seen_by_admin?: boolean;
}

export interface WaiterCallNotification {
  call_id: string;
  session_id: string;
  table_number?: number | null;
  note_ar?: string | null;
  status: string;
  timestamp?: string;
  seen_by_admin?: boolean;
}

export interface SessionStartPayload {
  session_id: string;
  table_number?: number | null;
  greeting: string;
  suggestions: string[];
}

export interface SessionStatePayload extends SessionStartPayload {
  history: Array<{
    role: ChatRole;
    content: string;
  }>;
}

export interface AdminTableSummary {
  table_number?: number | null;
  orders_count: number;
  unseen_count: number;
  latest_order_id?: string | null;
  latest_timestamp?: string | null;
  total_value: number;
}

export interface AdminOrdersResponse {
  unseen_count: number;
  tables: AdminTableSummary[];
  orders: OrderConfirmation[];
  waiter_calls: WaiterCallNotification[];
}
