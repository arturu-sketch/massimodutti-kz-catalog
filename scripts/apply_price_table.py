#!/usr/bin/env python3
"""Apply price_table.json to existing catalog JSON files."""
from __future__ import annotations

import json
from pathlib import Path

from pricing import retail_price


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "products-zara.json",
    "products-zara-women.json",
    "products-zara-men.json",
    "products-zara-kids.json",
    "products-massimodutti.json",
    "products-bershka.json",
    "products-stradivarius.json",
    "products-oysho.json",
    "products-zarahome.json",
]


def brand_from_filename(name: str) -> str:
    return name.removeprefix("products-").removesuffix(".json")


def update_item(item: dict, brand: str) -> bool:
    changed = False
    for kzt_key, rub_key in (("price_kzt", "price_rub"), ("price_old_kzt", "price_old_rub")):
        kzt = item.get(kzt_key)
        if kzt is None:
            continue
        rub = retail_price(kzt, brand)
        if rub is not None and item.get(rub_key) != rub:
            item[rub_key] = rub
            changed = True
    return changed


def main() -> None:
    total = 0
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            continue
        brand = brand_from_filename(name)
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = sum(1 for item in data if update_item(item, brand))
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[price] {name}: updated={changed}")
        total += changed
    print(f"[price] total updated={total}")


if __name__ == "__main__":
    main()
