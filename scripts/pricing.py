"""ZARAEKB retail price rules.

Exact KZT prices from price_table.json win. Missing prices between two known
table rows are linearly interpolated and rounded to the nearest 10 rubles.
Everything outside the known table keeps the legacy formula.
"""
from __future__ import annotations

import json
from bisect import bisect_left
from pathlib import Path


MARKUP = 1.35
USD_TO_RUB = 5.4
ROOT = Path(__file__).resolve().parents[1]
TABLE_PATH = ROOT / "price_table.json"


def _load_table() -> dict[int, int]:
    try:
        raw = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    table: dict[int, int] = {}
    for kzt, rub in raw.items():
        try:
            table[int(float(kzt))] = int(round(float(rub)))
        except Exception:
            continue
    return table


PRICE_TABLE = _load_table()
PRICE_POINTS = sorted(PRICE_TABLE)


def formula_price(kzt: float) -> int:
    return round(kzt * MARKUP / USD_TO_RUB)


def round_to_10(value: float) -> int:
    return int(round(value / 10.0) * 10)


def retail_price(kzt: float | int | None) -> int | None:
    if kzt is None:
        return None
    kzt_int = int(round(float(kzt)))
    if kzt_int in PRICE_TABLE:
        return PRICE_TABLE[kzt_int]
    if len(PRICE_POINTS) >= 2:
        pos = bisect_left(PRICE_POINTS, kzt_int)
        if 0 < pos < len(PRICE_POINTS):
            lo = PRICE_POINTS[pos - 1]
            hi = PRICE_POINTS[pos]
            lo_rub = PRICE_TABLE[lo]
            hi_rub = PRICE_TABLE[hi]
            ratio = (kzt_int - lo) / (hi - lo)
            return round_to_10(lo_rub + (hi_rub - lo_rub) * ratio)
    return formula_price(kzt_int)


def parse_price(raw) -> tuple[float | None, int | None]:
    if raw is None:
        return None, None
    try:
        kzt = int(raw) / 100
        return kzt, retail_price(kzt)
    except Exception:
        return None, None
