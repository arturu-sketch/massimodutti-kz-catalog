#!/usr/bin/env python3
"""Build lightweight storefront catalogs and lazy-loaded image chunks."""
from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path


ROOT = Path(os.environ.get("OUT_DIR", Path(__file__).resolve().parents[1]))
DETAIL_DIR = ROOT / "product-details"
KEEP_IMAGES = int(os.environ.get("LITE_KEEP_IMAGES", "3"))
CHUNK_SIZE = int(os.environ.get("DETAIL_CHUNK_SIZE", "250"))

BRAND_FILES = {
    "massimodutti": ["products-massimodutti.json"],
    "bershka": ["products-bershka.json"],
    "stradivarius": ["products-stradivarius.json"],
    "oysho": ["products-oysho.json"],
    "zarahome": ["products-zarahome.json"],
    "zara": [
        "products-zara.json",
        "products-zara-women.json",
        "products-zara-men.json",
        "products-zara-kids.json",
    ],
}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def detail_key(product: dict) -> str:
    return f"{product.get('ref') or ''}\u0000{product.get('color') or ''}"


def build_lite_file(brand: str, src: Path) -> tuple[str, int]:
    products = json.loads(src.read_text(encoding="utf-8"))
    stem = src.stem
    detail_brand_dir = DETAIL_DIR / brand / stem
    if detail_brand_dir.exists():
        shutil.rmtree(detail_brand_dir)
    detail_brand_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[list[dict]] = []
    for index in range(0, len(products), CHUNK_SIZE):
        chunks.append(products[index : index + CHUNK_SIZE])

    chunk_files: list[str] = []
    for chunk_index, chunk in enumerate(chunks, 1):
        detail_items = []
        for product in chunk:
            images = [img for img in product.get("images", []) if img]
            if len(images) > KEEP_IMAGES:
                detail_items.append({
                    "ref": product.get("ref") or "",
                    "color": product.get("color") or "",
                    "images": images,
                })
        if detail_items:
            rel = f"product-details/{brand}/{stem}/{chunk_index:03d}.json"
            write_json(ROOT / rel, detail_items)
            chunk_files.append(rel)

    lite = []
    for index, product in enumerate(products):
        chunk_index = math.floor(index / CHUNK_SIZE)
        images = [img for img in product.get("images", []) if img]
        item = dict(product)
        item["images"] = images[:KEEP_IMAGES]
        if images and not item.get("image"):
            item["image"] = images[0]
        if len(images) > KEEP_IMAGES:
            item["image_count"] = len(images)
            item["detail_file"] = f"product-details/{brand}/{stem}/{chunk_index + 1:03d}.json"
        lite.append(item)

    lite_name = f"{stem}-lite.json"
    write_json(ROOT / lite_name, lite)
    return lite_name, len(chunk_files)


def update_zara_manifest(files_by_source: dict[str, str]) -> None:
    manifest_path = ROOT / "products-zara-manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for section in manifest.get("sections", []):
        source = section.get("file")
        if source in files_by_source:
            section["file"] = files_by_source[source]
            section["full_file"] = source
    write_json(manifest_path, manifest)


def main() -> None:
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    generated = {}
    total_chunks = 0
    for brand, files in BRAND_FILES.items():
        for name in files:
            src = ROOT / name
            if not src.exists():
                continue
            lite_name, chunks = build_lite_file(brand, src)
            generated[name] = lite_name
            total_chunks += chunks
            print(f"[lite] {name} -> {lite_name}; chunks={chunks}")
    update_zara_manifest(generated)
    print(f"[lite] generated files={len(generated)}, detail chunks={total_chunks}")


if __name__ == "__main__":
    main()
