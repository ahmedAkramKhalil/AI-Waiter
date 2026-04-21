export interface MealCard {
  meal_id: string;
  name_ar: string;
  price: number;
  currency: string;
  image_url: string;
  spice_level: number;
  calories: number;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  cards?: MealCard[];
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
  status: string;
}
