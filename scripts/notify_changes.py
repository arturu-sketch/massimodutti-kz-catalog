#!/usr/bin/env python3
"""
Сравнивает свежие products-*.json с версией из git (HEAD) и шлёт
в Telegram-группу менеджеров сводку: новинки, размеры появились/пропали,
новые скидки, распродано/снято.
ENV: TG_BOT_TOKEN, TG_CHAT_ID
"""
import os, json, subprocess

try:
    import requests
except ModuleNotFoundError:
    requests = None

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
    pid = p.get("product_id")
    cid = p.get("color_id")
    if pid and cid:
        return ("id", str(pid), str(cid))
    return ("ref", p.get("ref"), p.get("color"))


def sizes(p):
    return set(str(s).strip() for s in (p.get("sizes") or []) if str(s).strip())


def sample(items, limit=3):
    out = []
    for p in items[:limit]:
        name = p.get("name") or "товар"
        ref = p.get("ref") or ""
        color = p.get("color") or ""
        out.append(f"    • {name} · {ref} · {color}")
    return out


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
        removed = [o[k] for k in o if k not in n]
        sold_out = [n[k] for k in n if k in o and o[k].get("in_stock") is not False and n[k].get("in_stock") is False]
        sales = [n[k] for k in n if k in o
                 and not o[k].get("price_old_rub") and n[k].get("price_old_rub")]
        size_added, size_removed = [], []
        for k in n:
            if k not in o:
                continue
            before = sizes(o[k])
            after = sizes(n[k])
            appeared = sorted(after - before)
            gone = sorted(before - after)
            if appeared:
                size_added.append((n[k], appeared))
            if gone:
                size_removed.append((n[k], gone))
        block = [f"{name}: {len(new)} товаров"]
        if added:
            block.append(f"  🆕 новинок: {len(added)}")
            block.extend(sample(added))
        if size_added:
            block.append(f"  ✅ размеры появились: {len(size_added)}")
            block.extend(f"    • {p.get('name')} · {p.get('ref')} · +{', '.join(vals)}" for p, vals in size_added[:3])
        if size_removed:
            block.append(f"  ⚠️ размеры разобрали: {len(size_removed)}")
            block.extend(f"    • {p.get('name')} · {p.get('ref')} · -{', '.join(vals)}" for p, vals in size_removed[:3])
        if sales:
            block.append(f"  🔥 новых скидок: {len(sales)}")
            block.extend(sample(sales))
        if sold_out:
            block.append(f"  ⛔ распродано: {len(sold_out)}")
            block.extend(sample(sold_out))
        if removed:
            block.append(f"  ❌ снято с продажи: {len(removed)}")
            block.extend(sample(removed))
        if added or size_added or size_removed or sales or sold_out or removed:
            any_change = True
        lines.append("\n".join(block))
    if not any_change:
        lines.append("\nЗначимых изменений нет.")

    text = "\n".join(lines)[:4000]
    if not TOKEN or not CHAT or requests is None:
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
