#!/usr/bin/env python3
"""
Парсер каталога брендов Inditex (Bershka / Oysho / Zara Home / Stradivarius)
для мультибрендового сайта ЗАРАЕКБ.

Конвейер:
  1. дерево категорий -> все viewCategoryId
  2. category/{viewCategoryId}/product -> ccIds (id товаров)
  3. productsArray?productIds=batch -> детали товаров
  4. сборка products-<brand>.json в формате сайта

Цена: (тенге * 1.35) / 5.4 = рубли
Запуск:  python3 inditex_parse.py bershka
"""
import sys, os, json, time, requests

API_KEY = os.environ.get("SF_KEY", "")
SF_BASE = "https://api.scrapingfish.com/api/v1/"
DIRECT_FIRST = os.environ.get("SF_DIRECT_FIRST", "1").lower() not in {"0", "false", "no"}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Accept": "application/json,text/plain,*/*",
}
BATCH = 40
HERE = os.path.dirname(os.path.abspath(__file__))

BRANDS = {
    "massimodutti": {"store": "35009503", "catalog": "30359534", "host": "https://www.massimodutti.com"},
    "bershka":      {"store": "45109553", "catalog": "40259532", "host": "https://www.bershka.com"},
    "stradivarius": {"store": "55009603", "catalog": "50331078", "host": "https://www.stradivarius.com"},
    "oysho":        {"store": "65009653", "catalog": "60361120", "host": "https://www.oysho.com"},
    "zarahome":     {"store": "85009953", "catalog": "80209919", "host": "https://www.zarahome.com"},
}

SECTION_FIX = {"WOMAN": "WOMEN", "MAN": "MEN", "WOMEN": "WOMEN", "MEN": "MEN",
               "GIRL": "GIRL", "BOY": "BOY", "KIDS": "KIDS", "BABY": "KIDS",
               "HOME": "HOME", "BEAUTY": "BEAUTY"}
DIRECT_CALLS = 0
SF_CALLS = 0
SF_FALLBACKS = 0


def fetch_direct(url, tries=2):
    global DIRECT_CALLS
    for t in range(tries):
        try:
            DIRECT_CALLS += 1
            r = requests.get(url, headers=HEADERS, timeout=240)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404 and "OBSOLETE" not in r.text and "category" in r.text.lower():
                return None
        except Exception as exc:
            print(f"   direct error: {exc}", flush=True)
        time.sleep(min(2 + t, 5))
    return None


def fetch_sf(url, tries=8):
    global SF_CALLS
    for t in range(tries):
        try:
            SF_CALLS += 1
            r = requests.get(SF_BASE,
                              params={"api_key": API_KEY, "url": url}, timeout=240)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404 and "OBSOLETE" not in r.text and "category" in r.text.lower():
                return None
        except Exception as exc:
            print(f"   sf error: {exc}", flush=True)
        time.sleep(min(3 + 2 * t, 20))
    return None


def sf(url, tries=8):
    """Прямой запрос к API бренда, ScrapingFish только как fallback."""
    global SF_FALLBACKS
    if DIRECT_FIRST:
        txt = fetch_direct(url, tries=2)
        if txt:
            return txt
        SF_FALLBACKS += 1
    return fetch_sf(url, tries=tries)


def print_fetch_stats(prefix):
    print(
        f"{prefix} запросы: direct={DIRECT_CALLS}, scrapingfish={SF_CALLS}, fallback={SF_FALLBACKS}",
        flush=True,
    )


def api(b, path):
    return f"{b['host']}/itxrest/{path}"


def get_view_category_ids(b):
    txt = sf(api(b, f"2/catalog/store/{b['store']}/{b['catalog']}/category?languageId=-1&typeCatalog=1&appId=1"))
    if not txt:
        return []
    tree = json.loads(txt)
    ids = set()

    def walk(cats):
        for c in cats:
            v = c.get("viewCategoryId")
            if v:
                ids.add(v)
            walk(c.get("subcategories") or [])
    walk(tree.get("categories", []))
    return sorted(ids)


def get_category_tree_map(b):
    """viewCategoryId -> (раздел верхнего уровня, название категории). Имена на русском."""
    txt = sf(api(b, f"2/catalog/store/{b['store']}/{b['catalog']}/category?languageId=-2&typeCatalog=1&appId=1"))
    if not txt:
        return {}
    tree = json.loads(txt)
    cmap = {}

    def walk(cats, top):
        for c in cats:
            tname = top or c.get("name")
            v = c.get("viewCategoryId")
            if v and tname:
                cmap[v] = (tname, c.get("name") or tname)
            walk(c.get("subcategories") or [], tname)
    walk(tree.get("categories", []), None)
    return cmap


def get_product_ids(b, cat_id):
    txt = sf(api(b, f"3/catalog/store/{b['store']}/{b['catalog']}/category/{cat_id}/product?languageId=-1&showProducts=false&appId=1"))
    if not txt:
        return []
    try:
        d = json.loads(txt)
    except Exception:
        return []
    ids = []
    for el in d.get("gridElements", []) or []:
        if el.get("type") != "CC":
            continue
        for cc in el.get("ccIds", []) or []:
            ids.append(cc)
    return ids


def get_products(b, id_batch):
    ids = ",".join(str(x) for x in id_batch)
    # languageId=-2 -> русские названия товаров, цветов и размеров
    txt = sf(api(b, f"3/catalog/store/{b['store']}/{b['catalog']}/productsArray?productIds={ids}&languageId=-2&appId=1"))
    if not txt:
        return []
    try:
        return json.loads(txt).get("products", []) or []
    except Exception:
        return []


def parse_price(raw):
    from pricing import parse_price as parse_custom_price
    return parse_custom_price(raw)


def build_images(detail, color_code, limit=10):
    """URL фото в официальном порядке галереи (location 1 — модель первой)."""
    blocks = detail.get("xmedia") or []
    if not blocks:
        return []
    block = next((x for x in blocks if str(x.get("colorCode")) == str(color_code)), blocks[0])
    media_map = {}
    for item in block.get("xmediaItems", []) or []:
        for m in item.get("medias", []) or []:
            mid = m.get("idMedia")
            durl = (m.get("extraInfo") or {}).get("deliveryUrl")
            if mid and durl and mid not in media_map:
                media_map[mid] = durl
    order = []
    for loc_block in block.get("xmediaLocations", []) or []:
        chosen = next((l for l in loc_block.get("locations", []) if l.get("location") == 1), None)
        if chosen:
            order = chosen.get("mediaLocations", [])
            break
    urls = []
    for mid in order:
        u = media_map.get(mid)
        if u and u not in urls:
            urls.append(u)
    for u in media_map.values():
        if u not in urls:
            urls.append(u)
    return urls[:limit]


def build_entry(prod):
    """Один товар productsArray -> запись каталога сайта (по первому цвету)."""
    item = prod
    bps = prod.get("bundleProductSummaries") or []
    if bps:
        item = bps[0]
    det = item.get("detail", {}) or {}
    colors = det.get("colors", []) or []
    if not colors:
        return None
    c0 = colors[0]
    sizes = c0.get("sizes", []) or []
    size_names = [s.get("name") for s in sizes if s.get("isBuyable")]
    if not size_names:
        size_names = [s.get("name") for s in sizes]

    price_kzt = price_rub = old_kzt = old_rub = None
    if sizes:
        price_kzt, price_rub = parse_price(sizes[0].get("price"))
        old_kzt, old_rub = parse_price(sizes[0].get("oldPrice"))
    on_sale = bool(old_kzt and price_kzt and old_kzt > price_kzt)

    images = build_images(det, c0.get("id"))
    section = SECTION_FIX.get((item.get("sectionNameEN") or "").upper(),
                              item.get("sectionNameEN") or "")
    return {
        "product_id": item.get("id"),
        "color_id": c0.get("id"),
        "ref": det.get("displayReference") or str(item.get("id") or ""),
        "name": item.get("name") or "",
        "section": section,
        "family": (item.get("familyNameEN") or "").upper(),
        "subfamily": (item.get("subFamilyNameEN") or "").upper(),
        "color": c0.get("name", ""),
        "price_kzt": price_kzt,
        "price_old_kzt": old_kzt if on_sale else None,
        "price_rub": price_rub,
        "price_old_rub": old_rub if on_sale else None,
        "sizes": [s for s in size_names if s],
        "in_stock": bool(item.get("isBuyable", True)),
        "image": images[0] if images else "",
        "images": images,
    }


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in BRANDS:
        print("Использование: python3 inditex_parse.py <" + "|".join(BRANDS) + ">")
        return
    bid = sys.argv[1]
    b = BRANDS[bid]
    bycat = "--bycat" in sys.argv  # раздел/категорию брать из дерева, а не из поля товара
    t0 = time.time()

    cmap = get_category_tree_map(b) if bycat else {}
    if bycat:
        print(f"[{bid}] карта категорий из дерева: {len(cmap)}", flush=True)

    print(f"[{bid}] получаю дерево категорий ...", flush=True)
    cats = get_view_category_ids(b)
    print(f"[{bid}] категорий (viewCategoryId): {len(cats)}", flush=True)

    all_ids, seen, pid_cat = [], set(), {}
    for i, cid in enumerate(cats, 1):
        pids = get_product_ids(b, cid)
        new = [p for p in pids if p not in seen]
        for p in new:
            seen.add(p)
            all_ids.append(p)
            pid_cat[p] = cid
        if i % 25 == 0 or new:
            print(f"  [{i}/{len(cats)}] кат {cid}: +{len(new)} (всего {len(all_ids)})", flush=True)
        time.sleep(0.2)
    print(f"[{bid}] уникальных товаров: {len(all_ids)}", flush=True)

    out, failed, seen_rc = [], 0, set()
    for i in range(0, len(all_ids), BATCH):
        batch = all_ids[i:i + BATCH]
        prods = get_products(b, batch)
        if not prods:
            failed += len(batch)
        for p in prods:
            try:
                e = build_entry(p)
            except Exception as exc:
                e = None
                print(f"   parse error {p.get('id')}: {exc}", flush=True)
            if e and e["images"]:
                if bycat:
                    grp = cmap.get(pid_cat.get(p.get("id")))
                    if grp:
                        e["section"], e["family"] = grp[0], grp[1]
                rc = (e["ref"], e["color"])
                if rc in seen_rc:
                    continue
                seen_rc.add(rc)
                out.append(e)
        print(f"  товаров {min(i+BATCH,len(all_ids))}/{len(all_ids)} -> собрано {len(out)}", flush=True)
        time.sleep(0.2)

    dst = os.environ.get("OUT_DIR", HERE)
    dst = os.path.join(dst, f"products-{bid}.json")
    if len(out) < 10:
        print(f"[{bid}] СБОЙ: получено {len(out)} товаров — файл не перезаписан", flush=True)
        sys.exit(1)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print_fetch_stats(f"[{bid}]")
    print(f"\n[{bid}] ГОТОВО за {time.time()-t0:.0f}с. Товаров: {len(out)}. Файл: {dst}", flush=True)


if __name__ == "__main__":
    main()
