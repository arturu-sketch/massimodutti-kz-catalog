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
BALANCE_FILE = os.environ.get("SF_BALANCE_FILE", "scrapingfish-balance.json")


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


def norm(value):
    return " ".join(
        str(value or "")
        .replace("\u00c2", " ")
        .replace("\u00a0", " ")
        .split()
    ).upper()


def aliases(p):
    rows = []
    ref = norm(p.get("ref"))
    color = norm(p.get("color"))
    if ref:
        rows.append(("ref", ref, color))
    pid = p.get("product_id")
    cid = p.get("color_id")
    if pid and cid:
        rows.append(("id", str(pid), str(cid)))
    return rows


def match_catalogs(old, new):
    old_aliases = {}
    for idx, item in enumerate(old):
        for alias in aliases(item):
            old_aliases.setdefault(alias, []).append(idx)

    matched_old = set()
    matched_new = set()
    pairs = []
    for new_idx, item in enumerate(new):
        old_idx = None
        for alias in aliases(item):
            for candidate in old_aliases.get(alias, []):
                if candidate not in matched_old:
                    old_idx = candidate
                    break
            if old_idx is not None:
                break
        if old_idx is None:
            continue
        matched_old.add(old_idx)
        matched_new.add(new_idx)
        pairs.append((old[old_idx], item))

    added = [item for idx, item in enumerate(new) if idx not in matched_new]
    removed = [item for idx, item in enumerate(old) if idx not in matched_old]
    return pairs, added, removed


def sizes(p):
    return set(str(s).strip() for s in (p.get("sizes") or []) if str(s).strip())


def model_key(p):
    ref = norm(p.get("ref"))
    if ref:
        return ref
    return norm(p.get("name")) or str(p.get("product_id") or "")


def unique_models(items):
    seen = set()
    out = []
    for item in items:
        key = model_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def model_count(items):
    return len({model_key(item) for item in items if model_key(item)})


def sample(items, limit=3):
    out = []
    for p in unique_models(items)[:limit]:
        name = p.get("name") or "товар"
        ref = p.get("ref") or ""
        color = p.get("color") or ""
        status = " · скоро в продаже" if not sizes(p) else ""
        out.append(f"    • {name} · {ref} · {color}{status}")
    return out


def balance_lines():
    try:
        with open(BALANCE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    rows = [
        "Баланс ScrapingFish:",
        f"  осталось: {data.get('left')} из {data.get('total')} ({data.get('percent')}%)",
    ]
    packs = data.get("packs") or []
    for pack in packs[:3]:
        rows.append(f"  пакет: {pack.get('left')}/{pack.get('total')}, до {pack.get('expires')}")
    return rows


def main():
    lines = ["🔄 ЗАРАЕКБ — обновление каталогов", ""]
    balance = balance_lines()
    if balance:
        lines.extend(balance)
        lines.append("")
    any_change = False
    for bid, name in BRANDS.items():
        path = f"products-{bid}.json"
        new = load(path)
        if not new:
            continue
        old = git_head(path)
        pairs, added, removed = match_catalogs(old, new)
        sold_out = [
            after for before, after in pairs
            if before.get("in_stock") is not False and after.get("in_stock") is False
        ]
        sales = [
            after for before, after in pairs
            if not before.get("price_old_rub") and after.get("price_old_rub")
        ]
        size_added, size_removed = [], []
        for before_item, after_item in pairs:
            before = sizes(before_item)
            after = sizes(after_item)
            appeared = sorted(after - before)
            gone = sorted(before - after)
            if appeared:
                size_added.append((after_item, appeared))
            if gone:
                size_removed.append((after_item, gone))
        block = [f"{name}: {model_count(new)} товаров"]
        if added:
            block.append(f"  🆕 новинок: {model_count(added)}")
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
            block.append(f"  ❌ снято с продажи: {model_count(removed)}")
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
