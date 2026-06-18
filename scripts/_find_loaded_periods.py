"""Find periods that have Oracle records with estado 'Cargado en RRHH' (05)."""
import sys
sys.path.insert(0, "/app")

from src.database.connection import get_connection, init_oracle_client

SQL = """
SELECT TO_CHAR(c.periodo, 'MMyyyy') periodo,
       COUNT(*) total,
       SUM(CASE WHEN c.estado = '05' THEN 1 ELSE 0 END) cargados
FROM apps.xxgl_carga_remu_detalle d
JOIN apps.xxgl_carga_remu c
  ON c.carga_remuneraciones_id = d.carga_remuneraciones_id
WHERE (d.cod_haber LIKE 'B%' OR d.cod_haber LIKE 'H%')
  AND c.periodo >= ADD_MONTHS(TRUNC(SYSDATE,'MM'), -12)
GROUP BY TO_CHAR(c.periodo, 'MMyyyy')
ORDER BY 1 DESC
"""

init_oracle_client()
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute(SQL)
    rows = cur.fetchall()

print(f"{'Periodo':12} {'Total':8} {'Cargados':10}")
print("-" * 32)
for periodo, total, cargados in rows:
    mark = " ←" if cargados > 0 else ""
    print(f"{periodo:12} {total:8} {cargados:10}{mark}")
