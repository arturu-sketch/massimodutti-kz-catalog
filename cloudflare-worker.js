// Cloudflare Worker — приём заявок с мультибренд-витрины
// и пересылка их в Telegram-группу менеджеров через @hermes19821_bot.
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
      const text = buildOrderText(order);
      if (!text) throw new Error("empty order");
      if (!env.BOT_TOKEN || !env.CHAT_ID) throw new Error("missing BOT_TOKEN/CHAT_ID");

      const keyboard = buildKeyboard(order);
      const chunks = splitText(text, 3600);
      for (let i = 0; i < chunks.length; i += 1) {
        const payload = {
            chat_id: env.CHAT_ID,
            text: chunks[i],
            disable_web_page_preview: true,
            reply_markup: i === 0 ? keyboard : undefined,
          };

        const res = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error("telegram " + res.status);
      }

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

function buildOrderText(order) {
  const existing = String(order?.text || "").trim();
  if (existing && !/Название: Товар\b/.test(existing) && /ИТОГО:/i.test(existing)) return existing;
  const customer = order?.customer || {};
  const items = Array.isArray(order?.items) ? order.items : [];
  const total = items.reduce((sum, item) => sum + (Number(item?.line_total || item?.price_rub || 0) * (item?.line_total ? 1 : Number(item?.qty || 1))), 0);
  const lines = [
    "🛍 Новая заявка ЗАРАЕКБ",
    "",
    `Клиент: ${joinName(customer) || "не указан"}`,
    `Город: ${customer.city || "не указан"}`,
    `Телефон: ${customer.phone || "не указан"}`,
    `Email: ${customer.email || "не указан"}`,
    `Мессенджер: ${customer.messenger || "не указан"}`,
    "",
    `Позиции: ${items.length} ${pluralRu(items.length, "товар", "товара", "товаров")}`,
  ];
  items.forEach((item, index) => {
    lines.push("");
    lines.push("━━━━━━━━━━━━");
    lines.push(`ТОВАР ${index + 1}/${items.length}`);
    lines.push("━━━━━━━━━━━━");
    lines.push(`Название: ${item.name || `Товар ${index + 1}`}`);
    lines.push(`Бренд: ${item.brand || "уточнить"}`);
    lines.push(`Артикул: ${item.ref || "уточнить"}`);
    lines.push(`Цвет: ${item.color || "уточнить"}`);
    lines.push(`Размер: ${item.size || "уточнить"}`);
    lines.push(`Количество: ${item.qty || 1} шт.`);
    lines.push(`Цена: ${formatRub(item.line_total || (Number(item.price_rub || 0) * Number(item.qty || 1)))}`);
    if (item.official_url) lines.push(`Официальный магазин: ${item.official_url}`);
    if (item.url) lines.push(`Карточка ЗАРАЕКБ: ${item.url}`);
  });
  lines.push("");
  lines.push(`ИТОГО: ${formatRub(order?.total || total)}`);
  return lines.join("\n");
}

function splitText(text, limit) {
  const chunks = [];
  let rest = String(text || "");
  while (rest.length > limit) {
    let cut = rest.lastIndexOf("\n\n", limit);
    if (cut < limit * 0.5) cut = rest.lastIndexOf("\n", limit);
    if (cut < limit * 0.5) cut = limit;
    chunks.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest) chunks.push(rest);
  return chunks;
}

function joinName(customer) {
  return [customer.lastName, customer.firstName].filter(Boolean).join(" ").trim();
}

function formatRub(value) {
  const amount = Number(value || 0);
  return amount ? `${new Intl.NumberFormat("ru-RU").format(amount)} ₽` : "по запросу";
}

function pluralRu(count, one, few, many) {
  const n = Math.abs(Number(count)) % 100;
  const n1 = n % 10;
  if (n > 10 && n < 20) return many;
  if (n1 > 1 && n1 < 5) return few;
  if (n1 === 1) return one;
  return many;
}

function buildKeyboard(order) {
  const buttons = [];
  const firstItem = Array.isArray(order?.items) ? order.items[0] : null;
  if (firstItem?.official_url) buttons.push([{ text: "Официальный товар", url: firstItem.official_url }]);
  if (firstItem?.url) buttons.push([{ text: "Карточка ЗАРАЕКБ", url: firstItem.url }]);
  if (order?.sourceUrl) buttons.push([{ text: "Открыть сайт", url: order.sourceUrl }]);
  return buttons.length ? { inline_keyboard: buttons.slice(0, 2) } : undefined;
}
