#!/usr/bin/env python3
"""
Парсер каталога Zara KZ для сайта ЗАРАЕКБ.
У Zara свой API (ajax=true), отличный от младших брендов Inditex.
  1. categories?ajax=true -> дерево категорий
  2. category/{id}/products?ajax=true -> productGroups с полными данными
Цена: (тенге * 1.35) / 5.4 = рубли
"""
import os, re, sys, json, time, requests

API_KEY = os.environ.get("SF_KEY", "")
SF_BASE = "https://api.scrapingfish.com/api/v1/"


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


def sf(url, tries=8):
    for t in range(tries):
        try:
            r = requests.get(SF_BASE, params={"api_key": API_KEY, "url": url}, timeout=240)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
        except Exception as exc:
            print(f"   sf error: {exc}", flush=True)
        time.sleep(min(3 + 2 * t, 20))
    return None


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


def build_images(color, prod, limit=10):
    urls = []
    for src in (color.get("xmedia") or [], prod.get("xmedia") or []):
        for m in src:
            if m.get("type") != "image":
                continue
            u = (m.get("extraInfo") or {}).get("deliveryUrl")
            if u and u not in urls:
                urls.append(u)
        if urls:
            break
    return urls[:limit]


def build_entry(prod):
    det = prod.get("detail", {}) or {}
    colors = det.get("colors", []) or []
    if not colors:
        return None
    c0 = colors[0]
    sizes = c0.get("sizes", []) or []
    size_names = [s.get("name") for s in sizes if s.get("name")]
    price_kzt, price_rub = parse_price(c0.get("price") or prod.get("price"))
    old_kzt, old_rub = parse_price(c0.get("oldPrice"))
    on_sale = bool(old_kzt and price_kzt and old_kzt > price_kzt)
    images = build_images(c0, prod)[:6]
    section = SECTION_FIX.get((prod.get("sectionName") or "").upper(),
                              prod.get("sectionName") or "")
    return {
        "ref": det.get("displayReference") or det.get("reference") or str(prod.get("id") or ""),
        "name": clean(prod.get("name") or ""),
        "section": section,
        "family": clean((prod.get("familyName") or "").upper()),
        "subfamily": clean((prod.get("subfamilyName") or "").upper()),
        "color": clean(c0.get("name", "")),
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


def main():
    t0 = time.time()
    print("[zara] дерево категорий ...", flush=True)
    cats = get_leaf_categories()
    print(f"[zara] категорий: {len(cats)}", flush=True)

    out, seen = [], set()
    for i, cid in enumerate(cats, 1):
        prods = products_in_category(cid)
        added = 0
        for p in prods:
            try:
                e = build_entry(p)
            except Exception:
                e = None
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
    dst = os.path.join(os.environ.get("OUT_DIR", HERE), "products-zara.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n[zara] ГОТОВО за {time.time()-t0:.0f}с. Товаров: {len(out)}", flush=True)


if __name__ == "__main__":
    main()
