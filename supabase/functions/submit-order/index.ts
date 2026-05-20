// Supabase Edge Function: submit-order
// Принимает заявку с мультибренд-витрины и пересылает её в Telegram-группу менеджеров.
//
// Секреты (Project Settings → Edge Functions → Secrets):
//   TELEGRAM_BOT_TOKEN — токен бота от @BotFather
//   TELEGRAM_CHAT_ID   — id Telegram-группы менеджеров (отрицательное число, напр. -1001234567890)
//
// Деплой (endpoint должен быть публичным — без проверки JWT):
//   supabase functions deploy submit-order --no-verify-jwt

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405, headers: cors });
  }

  try {
    const order = await req.json();
    const text = String(order?.text ?? "").slice(0, 3900);
    if (!text) throw new Error("empty order");

    const token = Deno.env.get("TELEGRAM_BOT_TOKEN");
    const chatId = Deno.env.get("TELEGRAM_CHAT_ID");
    if (!token || !chatId) throw new Error("missing telegram secrets");

    const photos = Array.isArray(order?.photos) ? order.photos.filter(Boolean) : [];
    const firstPhoto = photos[0] || "";
    const keyboard = buildKeyboard(order);
    const method = firstPhoto ? "sendPhoto" : "sendMessage";
    const payload = firstPhoto
      ? {
          chat_id: chatId,
          photo: firstPhoto,
          caption: text.slice(0, 1000),
          reply_markup: keyboard,
        }
      : {
          chat_id: chatId,
          text,
          disable_web_page_preview: true,
          reply_markup: keyboard,
        };

    const tg = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!tg.ok) {
      const detail = await tg.text();
      throw new Error(`telegram ${tg.status}: ${detail}`);
    }

    return new Response(JSON.stringify({ ok: true }), {
      headers: { ...cors, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ ok: false, error: String(err) }), {
      status: 500,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  }
});

function buildKeyboard(order: any) {
  const buttons = [];
  const firstItem = Array.isArray(order?.items) ? order.items[0] : null;
  if (firstItem?.url) buttons.push([{ text: "Открыть товар", url: firstItem.url }]);
  if (order?.sourceUrl) buttons.push([{ text: "Открыть сайт", url: order.sourceUrl }]);
  return buttons.length ? { inline_keyboard: buttons.slice(0, 2) } : undefined;
}
