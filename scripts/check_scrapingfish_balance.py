#!/usr/bin/env python3
"""
Проверяет доступность и остаток запросов ScrapingFish.
ENV:
  SF_KEY - API key ScrapingFish
  SF_MIN_LEFT - минимальный остаток запросов, по умолчанию 1
"""
import os
import sys
import json


USAGE_URL = "https://api.scrapingfish.com/api/v1/usage/"


def main():
    api_key = os.environ.get("SF_KEY", "").strip()
    min_left = int(os.environ.get("SF_MIN_LEFT", "1"))
    if not api_key:
        print("[scrapingfish] SF_KEY не задан", file=sys.stderr)
        return 1

    try:
        import requests
    except ModuleNotFoundError:
        print("[scrapingfish] не установлен пакет requests: pip install requests", file=sys.stderr)
        return 1

    try:
        response = requests.get(USAGE_URL, params={"api_key": api_key}, timeout=30)
    except Exception as exc:
        print(f"[scrapingfish] не удалось проверить баланс: {exc}", file=sys.stderr)
        return 1

    if response.status_code != 200:
        print(f"[scrapingfish] usage вернул HTTP {response.status_code}: {response.text[:300]}", file=sys.stderr)
        return 1

    try:
        packs = response.json()
    except Exception as exc:
        print(f"[scrapingfish] некорректный JSON usage: {exc}", file=sys.stderr)
        return 1

    if not packs:
        print("[scrapingfish] активных пакетов запросов нет", file=sys.stderr)
        return 1

    total = sum(int(pack.get("total") or 0) for pack in packs)
    left = sum(int(pack.get("left") or 0) for pack in packs)
    used = max(total - left, 0)
    percent = round((left / total) * 100, 1) if total else 0
    print(f"[scrapingfish] осталось запросов: {left} из {total} ({percent}%), использовано: {used}")
    for pack in packs:
        print(f"  pack: left={pack.get('left')} total={pack.get('total')} expires={pack.get('expires')}")

    balance_file = os.environ.get("SF_BALANCE_FILE", "").strip()
    if balance_file:
        with open(balance_file, "w", encoding="utf-8") as f:
            json.dump({
                "left": left,
                "total": total,
                "used": used,
                "percent": percent,
                "packs": packs,
            }, f, ensure_ascii=False, indent=2)

    if left < min_left:
        print(f"[scrapingfish] остаток ниже порога SF_MIN_LEFT={min_left}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
