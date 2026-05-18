# Подключение отправки заявок в Telegram

Сайт статический (GitHub Pages), токен бота нельзя держать в коде.
Заявки уходят через защищённый бэкенд. Рекомендуемый вариант — **Cloudflare Worker**
(бесплатный, стабильный). Альтернатива — Supabase Edge Function (см. ниже).

Бот и группа уже готовы:
- Бот: `@hermes19821_bot`
- Группа менеджеров: «Massimo Dutti — заявки», chat id `-1003600865564`

---

## Вариант A — Cloudflare Worker (рекомендуется)

1. Зайти на **dash.cloudflare.com** (создать бесплатный аккаунт, если нет).
2. **Workers & Pages → Create → Worker** → дать имя (напр. `md-orders`) → **Deploy**.
3. **Edit code** → вставить содержимое файла `cloudflare-worker.js` из этого репозитория → **Deploy**.
4. **Settings → Variables and Secrets** → добавить две переменные:
   - `BOT_TOKEN` — токен бота от @BotFather
   - `CHAT_ID` — `-1003600865564`
5. Скопировать URL воркера (вида `https://md-orders.<аккаунт>.workers.dev`).
6. В `index.html` вписать его в строку:
   ```js
   const ORDER_ENDPOINT = 'https://md-orders.<аккаунт>.workers.dev';
   ```

## Вариант B — Supabase Edge Function

Файл функции: `supabase/functions/submit-order/index.ts`.

```bash
supabase login
supabase link --project-ref <project-ref>
supabase secrets set TELEGRAM_BOT_TOKEN=<токен_бота>
supabase secrets set TELEGRAM_CHAT_ID=-1003600865564
supabase functions deploy submit-order --no-verify-jwt
```

URL функции: `https://<project-ref>.supabase.co/functions/v1/submit-order` —
вписать его в `ORDER_ENDPOINT` в `index.html`.

---

## Проверка

```bash
curl -X POST '<URL_бэкенда>' \
  -H 'Content-Type: application/json' \
  -d '{"text":"Тестовая заявка с сайта"}'
```

В группе менеджеров появится сообщение.

Если `ORDER_ENDPOINT` пустой или бэкенд недоступен — сайт не теряет заявку:
переключается на запасной режим (копирование заявки в буфер обмена).
