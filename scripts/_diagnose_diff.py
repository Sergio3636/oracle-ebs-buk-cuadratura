"""Diagnóstico de la cuadratura 062026: qué coincide y qué no."""
import sys
sys.path.insert(0, "/app")

from collections import Counter
from src.database.connection import get_connection, init_oracle_client
from src.oracle.queries import get_all_haberes, get_buk_to_oracle_map
from src.buk.client import BukClient
from src.reconciliation.engine import reconcile

PERIODO = "062026"

init_oracle_client()
with get_connection() as conn:
    oracle_recs   = get_all_haberes(conn, PERIODO)
    buk_to_oracle = get_buk_to_oracle_map(conn, {r.cod_haber for r in oracle_recs})

buk_recs = BukClient(oracle_map=buk_to_oracle).get_payroll_records(PERIODO)
rows     = reconcile(oracle_recs, buk_recs)

print(f"Oracle: {len(oracle_recs)} | Buk: {len(buk_recs)} | Rows: {len(rows)}")
print(f"Con diferencia: {sum(1 for r in rows if r.tiene_diferencia)}")
print(f"Sin diferencia: {sum(1 for r in rows if not r.tiene_diferencia)}\n")

# Resumen por cod_haber
print("=== FILAS SIN DIFERENCIA (coinciden exactamente) ===")
exact = [r for r in rows if not r.tiene_diferencia]
for r in sorted(exact, key=lambda x: (x.rut, x.cod_haber))[:20]:
    print(f"  {r.rut:14} {r.cod_haber:12} Oracle={r.monto_oracle:>12,.0f}  Buk={r.monto_buk:>12,.0f}")

print(f"\n=== DIFERENCIAS POR cod_haber ===")
from collections import defaultdict
diffs = defaultdict(list)
for r in rows:
    if r.tiene_diferencia:
        key = (r.cod_haber, bool(r.monto_oracle), bool(r.monto_buk))
        diffs[key].append(r)

for (cod, has_oracle, has_buk), recs in sorted(diffs.items()):
    where = "SOLO ORACLE" if has_oracle and not has_buk else ("SOLO BUK" if not has_oracle and has_buk else "AMBOS")
    print(f"  {cod:12} {where:12} → {len(recs)} personas")

print("\n=== MUESTRA BONO QUE EXISTE EN AMBOS PERO DIFIERE ===")
both = [r for r in rows if r.tiene_diferencia and r.monto_oracle and r.monto_buk]
for r in sorted(both, key=lambda x: (x.rut, x.cod_haber))[:10]:
    print(f"  {r.rut:14} {r.cod_haber:12} Oracle={r.monto_oracle:>12,.0f}  Buk={r.monto_buk:>12,.0f}  Dif={r.diferencia:>12,.0f}")

print("\n=== MAPA BUK→ORACLE ACTIVO (52 entradas) ===")
for buk_code, oracle_code in sorted(buk_to_oracle.items()):
    print(f"  {buk_code:10} → {oracle_code}")
