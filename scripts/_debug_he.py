#!/usr/bin/env python
"""Debug HE 50% comparison for specific RUTs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decimal import Decimal
from src.buk.client import BukClient
from src.database.connection import close_pool, get_connection, init_oracle_client
from src.oracle.queries import (
    HABER_DESCRIPTIONS, HE_50_PERCENT, HE_CANONICAL,
    aggregate_he_records, get_all_haberes, get_buk_to_oracle_map, get_haber_descriptions,
)
from src.reconciliation.engine import reconcile

TARGETS = ["12425857-K", "12227294-K"]
PERIODO = "052026"

init_oracle_client()
with get_connection() as conn:
    oracle_records    = get_all_haberes(conn, PERIODO)
    buk_to_oracle_map = get_buk_to_oracle_map(conn)
    oracle_hab_desc   = get_haber_descriptions(conn)
close_pool()

# Show RAW oracle HE lines before aggregation
print("=== Oracle HE raw (antes de agregar) ===")
for rut in TARGETS:
    recs = [r for r in oracle_records if r.rut == rut and r.cod_haber.startswith("H")]
    print(f"\n  RUT {rut}:")
    if recs:
        for r in recs:
            canonical = HE_CANONICAL.get(r.cod_haber, r.cod_haber)
            print(f"    cod_haber={r.cod_haber:<10}  → canónico={canonical:<10}  horas={float(r.monto):.2f}")
    else:
        print("    (sin HE en Oracle)")

oracle_records   = aggregate_he_records(oracle_records)
all_descriptions = {**oracle_hab_desc, **HABER_DESCRIPTIONS}

print("\n=== Oracle HE después de agregar ===")
for rut in TARGETS:
    recs = [r for r in oracle_records if r.rut == rut and r.cod_haber.startswith("H")]
    print(f"\n  RUT {rut}:")
    for r in recs:
        print(f"    cod_haber={r.cod_haber:<10}  horas={float(r.monto):.2f}")

buk_records = BukClient(oracle_map=buk_to_oracle_map).get_payroll_records(PERIODO)

print("\n=== Buk HE para estos RUTs ===")
for rut in TARGETS:
    recs = [r for r in buk_records if r.rut == rut and r.cod_concepto.startswith("H")]
    print(f"\n  RUT {rut}:")
    if recs:
        for r in recs:
            print(f"    cod_concepto={r.cod_concepto:<10}  horas={float(r.monto):.2f}  nombre={r.nombre_concepto}")
    else:
        print("    (sin HE en Buk)")

print("\n=== Cuadratura HE ===")
for rut in TARGETS:
    o = [r for r in oracle_records if r.rut == rut and r.cod_haber.startswith("H")]
    b = [r for r in buk_records    if r.rut == rut and r.cod_concepto.startswith("H")]
    rows = reconcile(o, b, haber_descriptions=all_descriptions)
    print(f"\n  RUT {rut}:")
    if rows:
        for r in rows:
            estado = "✓ OK" if not r.tiene_diferencia else "⚠️  DIFERENCIA"
            print(f"    {r.cod_haber:<10}  Oracle={float(r.monto_oracle):>8.2f} HH  Buk={float(r.monto_buk):>8.2f} HH  Dif={float(r.diferencia):>8.2f}  {estado}")
    else:
        print("    (sin filas)")
