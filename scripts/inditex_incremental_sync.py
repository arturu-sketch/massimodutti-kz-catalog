#!/usr/bin/env python3
"""Incremental sync for non-Zara Inditex brands.

The script scans category product IDs, fetches product batches, and rewrites
only records whose visible catalog signature changed. Unchanged records keep
their existing image/order data, while new IDs are added and missing IDs are
removed from the output catalog.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import inditex_parse as ip


ROOT = Path(os.environ.get("OUT_DIR", Path(__file__).resolve().parents[1]))


def load_old(brand_id: str) -> list[dict]:
    path = ROOT / f"products-{brand_id}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def product_key(item: dict) -> tuple[str, str, str]:
    pid = item.get("product_id")
    cid = item.get("color_id")
    if pid and cid:
        return ("id", str(pid), str(cid))
    return ("ref", str(item.get("ref") or ""), str(item.get("color") or ""))


def visible_signature(item: dict) -> dict:
    return {
        "ref": item.get("ref") or "",
        "name": item.get("name") or "",
        "section": item.get("section") or "",
        "family": item.get("family") or "",
        "subfamily": item.get("subfamily") or "",
        "color": item.get("color") or "",
        "price_rub": item.get("price_rub"),
        "price_old_rub": item.get("price_old_rub"),
        "sizes": sorted(str(s) for s in (item.get("sizes") or []) if s),
    }


def unchanged(old: dict, new: dict) -> bool:
    return visible_signature(old) == visible_signature(new)


def write_catalog(brand_id: str, rows: list[dict]) -> None:
    path = ROOT / f"products-{brand_id}.json"
    path.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ip.BRANDS:
        print("Использование: python3 inditex_incremental_sync.py <" + "|".join(ip.BRANDS) + ">")
        sys.exit(1)

    brand_id = sys.argv[1]
    bycat = "--bycat" in sys.argv
    brand = ip.BRANDS[brand_id]
    t0 = time.time()

    old = load_old(brand_id)
    old_by_id = {product_key(p): p for p in old if p.get("product_id") and p.get("color_id")}
    old_by_ref = {("ref", str(p.get("ref") or ""), str(p.get("color") or "")): p for p in old}
    print(
        f"[{brand_id}-incremental] старых товаров: {len(old)}, "
        f"с product_id: {len(old_by_id)}",
        flush=True,
    )

    cmap = ip.get_category_tree_map(brand) if bycat else {}
    if bycat:
        print(f"[{brand_id}-incremental] карта категорий из дерева: {len(cmap)}", flush=True)

    cats = ip.get_view_category_ids(brand)
    print(f"[{brand_id}-incremental] категорий: {len(cats)}", flush=True)

    all_ids: list[int] = []
    seen_ids: set[int] = set()
    pid_cat: dict[int, int] = {}
    for i, cid in enumerate(cats, 1):
        pids = ip.get_product_ids(brand, cid)
        added_in_cat = 0
        for pid in pids:
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            all_ids.append(pid)
            pid_cat[pid] = cid
            added_in_cat += 1
        if added_in_cat or i % 25 == 0:
            print(
                f"  [{i}/{len(cats)}] кат {cid}: ids +{added_in_cat}; всего {len(all_ids)}",
                flush=True,
            )
        time.sleep(0.2)

    out: list[dict] = []
    seen_output: set[tuple[str, str, str]] = set()
    reused = rebuilt = added = changed = 0

    for i in range(0, len(all_ids), ip.BATCH):
        batch = all_ids[i:i + ip.BATCH]
        prods = ip.get_products(brand, batch)
        for prod in prods:
            try:
                entry = ip.build_entry(prod)
            except Exception as exc:
                print(f"   parse error {prod.get('id')}: {exc}", flush=True)
                entry = None
            if not entry or not entry.get("images"):
                continue
            if bycat:
                grp = cmap.get(pid_cat.get(prod.get("id")))
                if grp:
                    entry["section"], entry["family"] = grp[0], grp[1]

            key = product_key(entry)
            if key in seen_output:
                continue
            ref_key = ("ref", str(entry.get("ref") or ""), str(entry.get("color") or ""))
            old_item = old_by_id.get(key) or old_by_ref.get(ref_key)
            if old_item and unchanged(old_item, entry):
                merged = dict(old_item)
                merged["product_id"] = entry.get("product_id")
                merged["color_id"] = entry.get("color_id")
                out.append(merged)
                reused += 1
            else:
                out.append(entry)
                rebuilt += 1
                if old_item:
                    changed += 1
                else:
                    added += 1
            seen_output.add(key)
        print(
            f"  товаров {min(i + ip.BATCH, len(all_ids))}/{len(all_ids)} -> "
            f"итого {len(out)}",
            flush=True,
        )
        time.sleep(0.2)

    removed = max(len(old) - reused - changed, 0)
    if len(out) < 10:
        print(f"[{brand_id}-incremental] СБОЙ: собрано {len(out)} товаров — файл не перезаписан", flush=True)
        sys.exit(1)

    write_catalog(brand_id, out)
    ip.print_fetch_stats(f"[{brand_id}-incremental]")
    print(
        f"[{brand_id}-incremental] ГОТОВО за {time.time()-t0:.0f}с. "
        f"товаров={len(out)}, reused={reused}, rebuilt={rebuilt}, "
        f"new={added}, changed={changed}, removed≈{removed}",
        flush=True,
    )


if __name__ == "__main__":
    main()
