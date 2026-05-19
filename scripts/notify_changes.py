#!/usr/bin/env python3
"""
Сравнивает свежие products-*.json с версией из git (HEAD) и шлёт
в Telegram-группу менеджеров сводку: новинки, новые скидки, снятые товары.
ENV: TG_BOT_TOKEN, TG_CHAT_ID
"""
import os, json, subprocess, requests

BRANDS = {
    "massimodutti": "Massimo Dutti", "bershka": "Bershka",
    "stradivarius": "Stradivarius", "oysho": "Oysho",
    "zarahome": "Zara Home", "zara": "Zara",
}
TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHAT = os.environ.get("TG_CHAT_ID", "")


def git_head(path):
    try:
        r = subprocess.run(["git", "show", f"HEAD:{path}"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return []


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def key(p):
    return (p.get("ref"), p.get("color"))


def main():
    lines = ["🔄 ЗАРАЕКБ — обновление каталогов", ""]
    any_change = False
    for bid, name in BRANDS.items():
        path = f"products-{bid}.json"
        new = load(path)
        if not new:
            continue
        old = git_head(path)
        o = {key(p): p for p in old}
        n = {key(p): p for p in new}
        added = [n[k] for k in n if k not in o]
        removed = [k for k in o if k not in n]
        sales = [n[k] for k in n if k in o
                 and not o[k].get("price_old_rub") and n[k].get("price_old_rub")]
        block = [f"{name}: {len(new)} товаров"]
        if added:
            block.append(f"  🆕 новинок: {len(added)}")
        if sales:
            block.append(f"  🔥 новых скидок: {len(sales)}")
        if removed:
            block.append(f"  ❌ снято с продажи: {len(removed)}")
        if added or sales or removed:
            any_change = True
        lines.append("\n".join(block))
    if not any_change:
        lines.append("\nЗначимых изменений нет.")

    text = "\n".join(lines)[:4000]
    if not TOKEN or not CHAT:
        print("[notify] нет TG_BOT_TOKEN/TG_CHAT_ID:\n" + text)
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT, "text": text, "disable_web_page_preview": True},
            timeout=20,
        )
        print("[notify] telegram:", r.status_code)
    except Exception as exc:
        print("[notify] error:", exc)


if __name__ == "__main__":
    main()
