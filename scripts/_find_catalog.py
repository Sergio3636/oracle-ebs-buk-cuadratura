"""Busca tablas catálogo de haberes en Oracle."""
import sys
sys.path.insert(0, "/app")
from src.database.connection import get_connection, init_oracle_client

# Buscar tablas con 'haber' o 'concepto' en el nombre
SQL_TABLES = """
SELECT owner, table_name, num_rows
FROM all_tables
WHERE (LOWER(table_name) LIKE '%haber%'
    OR LOWER(table_name) LIKE '%concepto%'
    OR LOWER(table_name) LIKE '%element%'
    OR LOWER(table_name) LIKE '%catalog%'
    OR LOWER(table_name) LIKE '%catalogo%')
  AND owner IN ('APPS','XXHR','XXGL')
ORDER BY owner, table_name
"""

# También buscar columnas 'nom_haber' o 'nombre_haber' en cualquier tabla XXGL
SQL_COLS = """
SELECT table_name, column_name
FROM all_tab_columns
WHERE owner IN ('APPS','XXGL','XXHR')
  AND (LOWER(column_name) LIKE '%nom%haber%'
    OR LOWER(column_name) LIKE '%desc%haber%'
    OR LOWER(column_name) LIKE '%nombre%haber%'
    OR LOWER(column_name) LIKE '%concepto%')
ORDER BY table_name, column_name
"""

# Columnas de xxgl_carga_remu_detalle
SQL_DETAIL_COLS = """
SELECT column_name, data_type, data_length
FROM all_tab_columns
WHERE table_name = 'XXGL_CARGA_REMU_DETALLE'
ORDER BY column_id
"""

init_oracle_client()
with get_connection() as conn:
    cur = conn.cursor()

    print("=== COLUMNAS DE XXGL_CARGA_REMU_DETALLE ===\n")
    cur.execute(SQL_DETAIL_COLS)
    for col, dtype, length in cur.fetchall():
        print(f"  {str(col):35} {str(dtype):15} {length}")

    print("\n=== TABLAS CON 'HABER'/'CONCEPTO' EN EL NOMBRE ===\n")
    try:
        cur.execute(SQL_TABLES)
        rows = cur.fetchall()
        for owner, table, nrows in rows:
            print(f"  {owner}.{table} ({nrows} rows)")
    except Exception as e:
        print(f"Error: {e}")

    print("\n=== COLUMNAS CON 'NOM_HABER'/'CONCEPTO' EN TABLAS XXGL/XXHR ===\n")
    try:
        cur.execute(SQL_COLS)
        rows = cur.fetchall()
        for table, col in rows:
            print(f"  {table}.{col}")
    except Exception as e:
        print(f"Error: {e}")
