#!/usr/bin/env python
"""Inspects raw Buk API response for 052026 — looking for RUT 10064121-6 / l260."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import requests
from src.config.settings import settings

base = settings.buk_api_url.rstrip("/") + "/"
session = requests.Session()
session.headers.update({"auth_token": settings.buk_api_token, "Accept": "application/json"})

TARGET_RUT = "10064121-6"
TARGET_ITEM = "l260"

page = 1
total_pages = 1
found = []
sample_keys = None

while page <= total_pages:
    r = session.get(f"{base}payroll_detail/month", params={"month": 5, "year": 2026, "page": page}, timeout=30)
    data = r.json()
    pagination = data.get("pagination", {})
    total_pages = pagination.get("total_pages", 1)
    print(f"Page {page}/{total_pages} — {len(data.get('data', []))} liquidaciones")

    for liq in data.get("data", []):
        # Print top-level keys on first record
        if sample_keys is None:
            sample_keys = list(liq.keys())
            print(f"\nLiquidacion keys: {sample_keys}")
            # Show month/year raw values from first record
            print(f"  month={liq.get('month')!r}  year={liq.get('year')!r}  rut={liq.get('rut')!r}\n")

        rut_raw = str(liq.get("rut", ""))
        # Normalise dots for comparison
        rut_norm = rut_raw.replace(".", "")
        if rut_norm == TARGET_RUT or rut_raw == TARGET_RUT:
            print(f"=== FOUND TARGET RUT {rut_raw} ===")
            for line in liq.get("lines_settlement", []):
                if line.get("type") == "haber":
                    print(f"  item_code={line.get('item_code')!r:30s}  amount={line.get('amount')}  desc={line.get('description')!r}")
            found.append(liq)

    page += 1

print(f"\nTotal pages scanned: {total_pages}")
print(f"Target RUT found in: {len(found)} liquidaciones")
if not found:
    # Show first liquidacion month/year to understand the structure
    r2 = session.get(f"{base}payroll_detail/month", params={"month": 5, "year": 2026, "page": 1}, timeout=30)
    d2 = r2.json()
    records = d2.get("data", [])
    if records:
        first = records[0]
        print(f"\nFirst record raw (keys only): {list(first.keys())}")
        print(f"  month={first.get('month')!r}  year={first.get('year')!r}  rut={first.get('rut')!r}")
    else:
        print("\nAPI returned 0 records for month=5, year=2026")
        print("Raw pagination:", d2.get("pagination"))
