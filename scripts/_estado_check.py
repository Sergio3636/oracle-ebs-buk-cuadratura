"""Temporary diagnostic: distribution of estado_reporte in Oracle for 062026."""
import sys
sys.path.insert(0, "/app")

from src.database.connection import get_connection, init_oracle_client
from src.oracle.queries import get_all_haberes

init_oracle_client()
with get_connection() as conn:
    recs = get_all_haberes(conn, "062026")

from collections import Counter
estados = Counter(r.estado_reporte for r in recs)
cod_by_estado: dict[str, Counter] = {}
for r in recs:
    cod_by_estado.setdefault(r.estado_reporte, Counter())[r.cod_haber] += 1

print("=== DISTRIBUCIÓN DE ESTADO REPORTE (062026) ===\n")
for estado, total in sorted(estados.items(), key=lambda x: -x[1]):
    print(f"  {estado:25s} → {total:3d} registros")
    for cod, cnt in sorted(cod_by_estado[estado].items()):
        print(f"      {cod:12s} {cnt}")
    print()

print(f"Total: {sum(estados.values())} registros")
