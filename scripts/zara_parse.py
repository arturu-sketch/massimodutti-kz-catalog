#!/usr/bin/env python3
"""
Парсер каталога Zara KZ для сайта ЗАРАЕКБ.
У Zara свой API (ajax=true), отличный от младших брендов Inditex.
  1. categories?ajax=true -> дерево категорий
  2. category/{id}/products?ajax=true -> productGroups с полными данными
Цена: (тенге * 1.35) / 5.4 = рубли
"""
import os, re, sys, json, time, requests
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

API_KEY = os.environ.get("SF_KEY", "")
SF_BASE = "https://api.scrapingfish.com/api/v1/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Accept": "application/json,text/plain,*/*",
}
BUYABLE_AVAILABILITY = {"in_stock", "low_on_stock", "few_items_left"}
DETAIL_CACHE = {}
DETAIL_LOCK = Lock()
DETAIL_WORKERS = int(os.environ.get("ZARA_DETAIL_WORKERS", "8"))


def clean(s):
    """Чистит UTF-8-кракозябры (Â) и неразрывные пробелы."""
    if not isinstance(s, str):
        return s
    s = s.replace('Â ', ' ').replace('\xa0', ' ').replace('Â', ' ')
    return re.sub(r'\s+', ' ', s).strip()
HOST = "https://www.zara.com/kz/ru"
MARKUP = 1.35
USD_TO_RUB = 5.4
HERE = os.path.dirname(os.path.abspath(__file__))
SECTION_FIX = {"WOMAN": "WOMEN", "MAN": "MEN", "KID": "KIDS", "KIDS": "KIDS"}
SECTION_FILES = {
    "WOMEN": "products-zara-women.json",
    "MEN": "products-zara-men.json",
    "KIDS": "products-zara-kids.json",
}


def fetch_url(url, tries=8, use_sf=True):
    for t in range(tries):
        try:
            if use_sf and API_KEY:
                r = requests.get(SF_BASE, params={"api_key": API_KEY, "url": url}, timeout=240)
            else:
                r = requests.get(url, headers=HEADERS, timeout=240)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
        except Exception as exc:
            print(f"   fetch error: {exc}", flush=True)
        time.sleep(min(3 + 2 * t, 20))
    return None


def sf(url, tries=8):
    return fetch_url(url, tries=tries, use_sf=True)


def get_leaf_categories():
    txt = sf(f"{HOST}/categories?ajax=true")
    if not txt:
        return []
    tree = json.loads(txt)
    leaves = []

    def walk(cats):
        for c in cats:
            subs = c.get("subcategories") or []
            if subs:
                walk(subs)
            else:
                name = (c.get("name") or "").upper()
                if c.get("id") and "DIVIDER" not in name and c.get("name"):
                    leaves.append(c["id"])
    walk(tree.get("categories", []))
    return list(dict.fromkeys(leaves))


def parse_price(raw):
    if raw is None:
        return None, None
    try:
        kzt = int(raw) / 100
        return kzt, round(kzt * MARKUP / USD_TO_RUB)
    except Exception:
        return None, None


def buyable_sizes(sizes):
    names = [
        s.get("name") for s in sizes
        if s.get("name") and (s.get("availability") in BUYABLE_AVAILABILITY or s.get("isBuyable") is True)
    ]
    if not names:
        names = [s.get("name") for s in sizes if s.get("name")]
    return [s for s in names if s]


def product_details(product_id):
    if not product_id:
        return None
    product_id = str(product_id)
    with DETAIL_LOCK:
        if product_id in DETAIL_CACHE:
            return DETAIL_CACHE[product_id]

    # Этот endpoint отдаёт полную карточку Zara: все цвета, размеры, sku и наличие.
    # Запрашиваем напрямую: так GitHub Actions не тратит ScrapingFish-кредиты на тысячи detail-запросов.
    url = f"{HOST}/products-details?productIds={product_id}&ajax=true"
    txt = fetch_url(url, tries=3, use_sf=False)
    if not txt:
        txt = sf(url, tries=3)
    try:
        data = json.loads(txt) if txt else []
    except Exception:
        data = []
    detail = data[0] if data else None

    with DETAIL_LOCK:
        if detail:
            for color in ((detail.get("detail") or {}).get("colors") or []):
                pid = color.get("productId")
                if pid:
                    DETAIL_CACHE[str(pid)] = detail
        DETAIL_CACHE[product_id] = detail
    return detail


def safe_build_entry(prod):
    try:
        return build_entry(prod)
    except Exception:
        return None


def detail_color(prod, base_color):
    detail = product_details(prod.get("id"))
    colors = ((detail or {}).get("detail") or {}).get("colors") or []
    product_id = prod.get("id")
    color_id = str(base_color.get("id") or "")
    for color in colors:
        if color.get("productId") == product_id:
            return color
    for color in colors:
        if str(color.get("id") or "") == color_id:
            return color
    return None


def build_images(color, prod, limit=10):
    urls = []

    def add_media(media):
        if media.get("type") != "image":
            return
        candidates = [
            (media.get("extraInfo") or {}).get("deliveryUrl"),
            media.get("url"),
        ]
        for layer in media.get("layers") or []:
            candidates.append((layer.get("extraInfo") or {}).get("deliveryUrl"))
            candidates.append(layer.get("url"))
        for u in candidates:
            if not u:
                continue
            u = u.replace("{width}", "1024")
            if u and u not in urls:
                urls.append(u)

    for src in (color.get("xmedia") or [], prod.get("xmedia") or []):
        for m in src:
            add_media(m)
        if urls:
            break
    return urls[:limit]


def build_entry(prod):
    det = prod.get("detail", {}) or {}
    colors = det.get("colors", []) or []
    if not colors:
        return None
    c0 = colors[0]
    dcolor = detail_color(prod, c0) or {}
    source_color = dcolor or c0
    sizes = source_color.get("sizes", []) or c0.get("sizes", []) or []
    size_names = buyable_sizes(sizes)
    price_kzt, price_rub = parse_price(source_color.get("price") or c0.get("price") or prod.get("price"))
    old_kzt, old_rub = parse_price(source_color.get("oldPrice") or c0.get("oldPrice"))
    on_sale = bool(old_kzt and price_kzt and old_kzt > price_kzt)
    images = build_images(source_color, prod)[:6]
    section = SECTION_FIX.get((prod.get("sectionName") or "").upper(),
                              prod.get("sectionName") or "")
    return {
        "product_id": prod.get("id"),
        "color_id": source_color.get("id") or c0.get("id"),
        "ref": det.get("displayReference") or det.get("reference") or str(prod.get("id") or ""),
        "name": clean(prod.get("name") or ""),
        "section": section,
        "family": clean((prod.get("familyName") or "").upper()),
        "subfamily": clean((prod.get("subfamilyName") or "").upper()),
        "color": clean(source_color.get("name") or c0.get("name", "")),
        "price_kzt": price_kzt,
        "price_old_kzt": old_kzt if on_sale else None,
        "price_rub": price_rub,
        "price_old_rub": old_rub if on_sale else None,
        "sizes": size_names,
        "in_stock": True,
        "image": images[0] if images else "",
        "images": images,
    }


def products_in_category(cat_id):
    txt = sf(f"{HOST}/category/{cat_id}/products?ajax=true")
    if not txt:
        return []
    try:
        d = json.loads(txt)
    except Exception:
        return []
    out = []
    for g in d.get("productGroups", []) or []:
        for el in g.get("elements", []) or []:
            for cc in el.get("commercialComponents", []) or []:
                if cc.get("type") == "Product":
                    out.append(cc)
    return out


def write_outputs(out, dst_dir):
    out = [
        p for p in out
        if (p.get("family") or "").upper() not in {"GIFT CARD", "ПОДАРОЧНАЯ КАРТА"}
    ]
    full = os.path.join(dst_dir, "products-zara.json")
    with open(full, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    manifest = {"brand": "zara", "sections": []}
    for section, filename in SECTION_FILES.items():
        items = [p for p in out if p.get("section") == section]
        if not items:
            continue
        with open(os.path.join(dst_dir, filename), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, separators=(",", ":"))
        manifest["sections"].append({
            "id": section,
            "label": section,
            "count": len(items),
            "file": filename,
        })

    with open(os.path.join(dst_dir, "products-zara-manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))


def main():
    t0 = time.time()
    print("[zara] дерево категорий ...", flush=True)
    cats = get_leaf_categories()
    print(f"[zara] категорий: {len(cats)}", flush=True)

    out, seen = [], set()
    for i, cid in enumerate(cats, 1):
        prods = products_in_category(cid)
        added = 0
        entries = []
        if DETAIL_WORKERS > 1 and len(prods) > 1:
            with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as pool:
                entries = list(pool.map(safe_build_entry, prods))
        else:
            entries = [safe_build_entry(p) for p in prods]
        for e in entries:
            if e and e["images"]:
                rc = (e["ref"], e["color"])
                if rc in seen:
                    continue
                seen.add(rc)
                out.append(e)
                added += 1
        if added or i % 50 == 0:
            print(f"  [{i}/{len(cats)}] кат {cid}: +{added} (всего {len(out)})", flush=True)
        time.sleep(0.2)

    if len(out) < 100:
        print(f"[zara] СБОЙ: получено {len(out)} товаров — файл не перезаписан", flush=True)
        sys.exit(1)
    dst_dir = os.environ.get("OUT_DIR", HERE)
    write_outputs(out, dst_dir)
    print(f"\n[zara] ГОТОВО за {time.time()-t0:.0f}с. Товаров: {len(out)}", flush=True)


if __name__ == "__main__":
    main()
