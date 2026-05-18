# Подключение отправки заявок в Telegram

Сайт статический (GitHub Pages), поэтому токен бота нельзя держать в коде.
Заявки уходят через защищённый бэкенд — Supabase Edge Function.

## 1. Создать Telegram-бота и группу

1. В Telegram открыть **@BotFather** → `/newbot` → получить **токен бота**.
2. Создать группу менеджеров, добавить туда бота.
3. Узнать **chat id группы**: временно добавить в группу **@getmyid_bot** или
   открыть `https://api.telegram.org/bot<ТОКЕН>/getUpdates` после сообщения в группе.
   Id группы — отрицательное число вида `-1001234567890`.

## 2. Развернуть Edge Function

```bash
# установить Supabase CLI: https://supabase.com/docs/guides/cli
supabase login
supabase link --project-ref <project-ref>

# секреты (хранятся только на сервере)
supabase secrets set TELEGRAM_BOT_TOKEN=<токен_бота>
supabase secrets set TELEGRAM_CHAT_ID=<-100...>

# деплой публичного endpoint (без проверки JWT)
supabase functions deploy submit-order --no-verify-jwt
```

Функция станет доступна по адресу:
`https://<project-ref>.supabase.co/functions/v1/submit-order`

## 3. Прописать endpoint в сайте

В `index.html` найти строку:

```js
const ORDER_ENDPOINT = '';
```

и подставить URL функции:

```js
const ORDER_ENDPOINT = 'https://<project-ref>.supabase.co/functions/v1/submit-order';
```

После этого заявка с кнопки «Оформить заявку» автоматически уходит в группу менеджеров.
Если endpoint пустой или недоступен — сайт переключается на запасной режим
(копирование заявки в буфер обмена), клиент не теряет данные.

## 4. Проверка

```bash
curl -X POST 'https://<project-ref>.supabase.co/functions/v1/submit-order' \
  -H 'Content-Type: application/json' \
  -d '{"text":"Тестовая заявка с сайта"}'
```

В группе менеджеров должно появиться сообщение.
