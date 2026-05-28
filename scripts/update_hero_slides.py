#!/usr/bin/env python3
"""Build homepage hero slides from the freshest Zara women catalog images."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "products-zara-women.json"
DEST = ROOT / "hero-slides.json"
PREFERRED_FAMILIES = ["DRESS", "BLAZER", "COATS", "SKIRT", "TOPS", "SHIRT"]
SLIDE_COUNT = 5


def image_for(product: dict) -> str:
    images = product.get("images") or []
    if images:
        return images[0]
    return product.get("image") or ""


def make_slide(product: dict) -> dict:
    return {
        "image": image_for(product),
        "title": product.get("name") or "Zara",
        "ref": product.get("ref") or "",
    }


def main() -> None:
    products = json.loads(SOURCE.read_text(encoding="utf-8"))
    slides: list[dict] = []
    seen: set[str] = set()

    def add(product: dict) -> None:
        image = image_for(product)
        if not image or image in seen or len(slides) >= SLIDE_COUNT:
            return
        seen.add(image)
        slides.append(make_slide(product))

    for family in PREFERRED_FAMILIES:
        for product in products:
            if product.get("section") == "WOMEN" and product.get("family") == family:
                add(product)
                break

    for product in products:
        if product.get("section") == "WOMEN":
            add(product)
        if len(slides) >= SLIDE_COUNT:
            break

    if not slides:
        raise SystemExit("No hero slides found")
    DEST.write_text(json.dumps(slides, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[hero] {DEST.name}: slides={len(slides)}")


if __name__ == "__main__":
    main()
