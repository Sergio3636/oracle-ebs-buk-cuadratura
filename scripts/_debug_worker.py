#!/usr/bin/env python
"""Shows Oracle vs Buk for a specific RUT in the reconciliation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.buk.client import BukClient
from src.database.connection import close_pool, get_connection, init_oracle_client
from src.oracle.queries import (
    HABER_DESCRIPTIONS, aggregate_he_records,
    get_all_haberes, get_buk_to_oracle_map, get_haber_descriptions,
)
from src.reconciliation.engine import reconcile

TARGET = "10064121-6"
PERIODO = "052026"

init_oracle_client()
with get_connection() as conn:
    oracle_records    = get_all_haberes(conn, PERIODO)
    buk_to_oracle_map = get_buk_to_oracle_map(conn)
    oracle_hab_desc   = get_haber_descriptions(conn)
close_pool()

oracle_records    = aggregate_he_records(oracle_records)
all_descriptions  = {**oracle_hab_desc, **HABER_DESCRIPTIONS}

buk_records = BukClient(oracle_map=buk_to_oracle_map).get_payroll_records(PERIODO)

# Filter to target
oracle_t = [r for r in oracle_records if r.rut == TARGET]
buk_t    = [r for r in buk_records    if r.rut == TARGET]

print(f"\n=== Oracle {PERIODO} para RUT {TARGET} ===")
for r in oracle_t:
    print(f"  cod_haber={r.cod_haber:<12}  monto={float(r.monto):>12,.0f}")

print(f"\n=== Buk (período devuelto por API) para RUT {TARGET} ===")
print(f"  (Nota: Buk retorna período actual 062026, no 052026)")
for r in buk_t:
    print(f"  cod_concepto={r.cod_concepto:<12}  monto={float(r.monto):>12,.0f}")

rows = reconcile(oracle_t, buk_t, haber_descriptions=all_descriptions)
print(f"\n=== Cuadratura ===")
for r in rows:
    dif = "⚠️ DIFERENCIA" if r.tiene_diferencia else "✓ OK"
    print(f"  {r.cod_haber:<12}  Oracle={float(r.monto_oracle):>12,.0f}  Buk={float(r.monto_buk):>12,.0f}  Dif={float(r.diferencia):>12,.0f}  {dif}")

# Also show what Buk codes map to for this worker
print(f"\n=== item_codes Buk del trabajador (raw, sin mapear) ===")
import requests
from src.config.settings import settings
session = requests.Session()
session.headers.update({"auth_token": settings.buk_api_token, "Accept": "application/json"})
base = settings.buk_api_url.rstrip("/") + "/"
r = session.get(f"{base}payroll_detail/month", params={"month": 5, "year": 2026, "page": 16}, timeout=30)
for liq in r.json().get("data", []):
    rut = str(liq.get("rut","")).replace(".","")
    if rut == TARGET:
        for line in liq.get("lines_settlement", []):
            if line.get("type") == "haber":
                ic = line.get("item_code")
                oracle_eq = buk_to_oracle_map.get(ic or "", "(sin mapeo)")
                print(f"  item_code={ic!r:<30}  amount={line.get('amount')}  → Oracle={oracle_eq}")
