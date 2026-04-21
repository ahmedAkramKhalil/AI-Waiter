# AI Waiter — Web (Mobile-First RTL)

Modern mobile-first Arabic (RTL) web app for the AI Waiter backend. Built with
**Vite + React + TypeScript + Tailwind + Framer Motion**. Glossy glass-morphism
UI with a deep burgundy + gold restaurant palette, 3D tilt on meal cards, and
real-time SSE chat streaming.

## Quick start

```bash
cd apps/web
cp .env.example .env            # set VITE_API_BASE
npm install
npm run dev                     # http://localhost:5173
```

### Pointing to the backend

Edit `.env`:

```env
# Local Python backend
VITE_API_BASE=http://localhost:8001

# Or the RunPod tunnel
VITE_API_BASE=https://tmw7xtoyxyz8g4-8001.proxy.runpod.net
```

The backend already allows all CORS origins (`apps/api/main.py`), so no
extra config is needed.

## Production build

```bash
npm run build       # outputs ./dist
npm run preview     # serves ./dist on :4173
```

Deploy `dist/` to any static host (Vercel / Netlify / nginx / Cloudflare Pages).

## Screens

| Screen       | File                                          |
|--------------|-----------------------------------------------|
| Splash       | `src/components/SplashScreen.tsx`             |
| Chat + RAG   | `src/components/ChatScreen.tsx`               |
| Meal card    | `src/components/MealCard.tsx`                 |
| Cart bottom-sheet | `src/components/CartSheet.tsx`           |
| Order confirmed | `src/components/OrderConfirmedScreen.tsx`  |

## Endpoints consumed

- `POST /session/start` → `{ session_id }`
- `POST /chat` → SSE stream (events: `text`, `meal_cards`, `done`)
- `GET  /cart/{session_id}`
- `POST /order/submit`
- `GET  /images/{filename}` (static meal images)

SSE is consumed via `fetch` + `ReadableStream` (in `src/api/client.ts`) so
we can POST the body — native `EventSource` can't.

## Design system

- **Palette** (`tailwind.config.ts`): `wine` (burgundy), `gold`, `cream`
- **Surfaces**: `.glass`, `.glass-gold` — backdrop-blur + inset-highlight shadows
- **Gloss**: `.sheen` — animated diagonal shimmer overlay
- **Fonts**: Tajawal (UI), Amiri (display)
- **3D**: meal cards use `transformPerspective` + hover tilt
