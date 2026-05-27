#!/usr/bin/env python3
"""Incremental Zara sync for ZARAEKB.

The script still scans Zara category listings, but it reuses existing product
records when the product/color signature did not change. Full product details
are fetched only for new or changed product-color pairs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

import zara_parse as zp


ROOT = Path(os.environ.get("OUT_DIR", Path(__file__).resolve().parents[1]))


def load_old() -> list[dict]:
    path = ROOT / "products-zara.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def product_key(item: dict) -> tuple[str, str, str]:
    pid = item.get("product_id")
    cid = item.get("color_id")
    if pid and cid:
        return ("id", str(pid), str(cid))
    return ("ref", str(item.get("ref") or ""), str(item.get("color") or ""))


def listing_signature(prod: dict) -> dict | None:
    det = prod.get("detail", {}) or {}
    colors = det.get("colors", []) or []
    if not colors:
        return None
    color = colors[0]
    sizes = color.get("sizes", []) or []
    price_kzt, price_rub = zp.parse_price(color.get("price") or prod.get("price"))
    old_kzt, old_rub = zp.parse_price(color.get("oldPrice"))
    on_sale = bool(old_kzt and price_kzt and old_kzt > price_kzt)
    section = zp.SECTION_FIX.get((prod.get("sectionName") or "").upper(), prod.get("sectionName") or "")
    return {
        "product_id": prod.get("id"),
        "color_id": color.get("id"),
        "ref": det.get("displayReference") or det.get("reference") or str(prod.get("id") or ""),
        "name": zp.clean(prod.get("name") or ""),
        "section": section,
        "family": zp.clean((prod.get("familyName") or "").upper()),
        "subfamily": zp.clean((prod.get("subfamilyName") or "").upper()),
        "color": zp.clean(color.get("name") or ""),
        "price_rub": price_rub,
        "price_old_rub": old_rub if on_sale else None,
        "sizes": sorted(zp.buyable_sizes(sizes)),
    }


def unchanged(old: dict, sig: dict) -> bool:
    return (
        sorted(str(s) for s in (old.get("sizes") or [])) == sig["sizes"]
        and old.get("price_rub") == sig["price_rub"]
        and old.get("price_old_rub") == sig["price_old_rub"]
        and (old.get("name") or "") == sig["name"]
        and (old.get("section") or "") == sig["section"]
        and (old.get("family") or "") == sig["family"]
    )


def main() -> None:
    if not zp.API_KEY:
        print("[zara-incremental] SF_KEY не задан", file=sys.stderr)
        sys.exit(1)
    zp.requests = requests
    t0 = time.time()
    old = load_old()
    old_by_key = {product_key(p): p for p in old}
    print(f"[zara-incremental] старых товаров: {len(old_by_key)}", flush=True)

    cats = zp.get_leaf_categories()
    print(f"[zara-incremental] категорий: {len(cats)}", flush=True)
    out: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    reused = rebuilt = added = 0

    for i, cid in enumerate(cats, 1):
        prods = zp.products_in_category(cid)
        changed_in_category = 0
        for prod in prods:
            sig = listing_signature(prod)
            if not sig:
                continue
            k = product_key(sig)
            if k in seen:
                continue
            seen.add(k)
            old_item = old_by_key.get(k)
            if old_item and unchanged(old_item, sig):
                out.append(old_item)
                reused += 1
                continue
            entry = zp.safe_build_entry(prod)
            if entry and entry.get("images"):
                out.append(entry)
                rebuilt += 1
                changed_in_category += 1
                if not old_item:
                    added += 1
        if changed_in_category or i % 50 == 0:
            print(
                f"  [{i}/{len(cats)}] кат {cid}: обновлено {changed_in_category}; "
                f"всего {len(out)}",
                flush=True,
            )
        time.sleep(0.2)

    removed = len([k for k in old_by_key if k not in seen])
    if len(out) < 100:
        print(f"[zara-incremental] СБОЙ: собрано {len(out)} товаров — файлы не перезаписаны", flush=True)
        sys.exit(1)
    zp.write_outputs(out, str(ROOT))
    print(
        f"[zara-incremental] ГОТОВО за {time.time()-t0:.0f}с. "
        f"товаров={len(out)}, reused={reused}, rebuilt={rebuilt}, "
        f"new={added}, removed={removed}",
        flush=True,
    )


if __name__ == "__main__":
    main()
