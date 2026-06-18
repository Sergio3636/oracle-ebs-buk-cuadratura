#!/usr/bin/env python
"""Busca los RUTs objetivo en Buk 052026 — todos los tipos de línea."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from src.config.settings import settings

TARGETS = {"12425857-K", "12227294-K"}
PERIODO_DATE = "01-05-2026"

base = settings.buk_api_url.rstrip("/") + "/"
session = requests.Session()
session.headers.update({"auth_token": settings.buk_api_token, "Accept": "application/json"})

page = 1
total_pages = 1
found = {}

while page <= total_pages:
    r = session.get(f"{base}payroll_detail/month", params={"date": PERIODO_DATE, "page": page}, timeout=30)
    data = r.json()
    total_pages = data.get("pagination", {}).get("total_pages", 1)

    for liq in data.get("data", []):
        rut_raw  = str(liq.get("rut", ""))
        rut_norm = rut_raw.replace(".", "")
        if rut_norm in TARGETS:
            found[rut_norm] = liq

    if found.keys() == TARGETS:
        break
    page += 1

print(f"Páginas escaneadas: {page}/{total_pages}")

if not found:
    print(f"\nNinguno de los RUTs {TARGETS} aparece en Buk para {PERIODO_DATE}")
    print("→ Estos trabajadores no tienen liquidación en Buk para ese período")
else:
    for rut, liq in found.items():
        print(f"\n=== RUT {rut} encontrado ===")
        print(f"  liquidacion_id={liq.get('liquidacion_id')}  month={liq.get('month')}  year={liq.get('year')}")
        lines = liq.get("lines_settlement", [])
        print(f"  Total líneas: {len(lines)}")
        for l in lines:
            print(f"    type={l.get('type'):<12} item_code={str(l.get('item_code')):<30} name={l.get('name')}  amount={l.get('amount')}  desc={l.get('description')!r}")
