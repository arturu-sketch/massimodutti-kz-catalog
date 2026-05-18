// Cloudflare Worker — приём заявок с сайта Massimo Dutti KZ
// и пересылка их в Telegram-группу менеджеров.
//
// Токен бота НЕ хранится в коде (репозиторий публичный).
// В настройках Worker (Settings → Variables and Secrets) задать:
//   BOT_TOKEN — токен бота от @BotFather
//   CHAT_ID   — id Telegram-группы менеджеров (отрицательное число)
//
// Деплой: dash.cloudflare.com → Workers & Pages → Create → Worker →
//         вставить этот код → Deploy → задать переменные → скопировать URL воркера.

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405, headers: CORS });
    }
    try {
      const order = await request.json();
      const text = String(order?.text || "").slice(0, 3900);
      if (!text) throw new Error("empty order");
      if (!env.BOT_TOKEN || !env.CHAT_ID) throw new Error("missing BOT_TOKEN/CHAT_ID");

      const res = await fetch(
        `https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: env.CHAT_ID,
            text,
            disable_web_page_preview: true,
          }),
        }
      );
      if (!res.ok) throw new Error("telegram " + res.status);

      return new Response(JSON.stringify({ ok: true }), {
        headers: { ...CORS, "Content-Type": "application/json" },
      });
    } catch (err) {
      return new Response(JSON.stringify({ ok: false, error: String(err) }), {
        status: 500,
        headers: { ...CORS, "Content-Type": "application/json" },
      });
    }
  },
};
