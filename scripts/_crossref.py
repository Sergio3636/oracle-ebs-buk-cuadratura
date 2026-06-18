"""Temporary diagnostic script: cross-reference Oracle vs Buk codes by RUT."""
import sys
import urllib.request
import json

sys.path.insert(0, "/app")

from src.database.connection import get_connection, init_oracle_client
from src.oracle.queries import get_all_haberes
from src.utils import normalize_rut

TOKEN = "cM95brFqLnnmhTChCCaiFphA"
PERIODO = "062026"

# 1. Oracle data
init_oracle_client()
with get_connection() as conn:
    oracle_recs = get_all_haberes(conn, PERIODO)

oracle_by_rut: dict[str, dict] = {}
for r in oracle_recs:
    oracle_by_rut.setdefault(r.rut, {})[r.cod_haber] = float(r.monto)

print(f"Oracle personas con haberes: {len(oracle_by_rut)}")

# 2. Buk pages 1-3 (sample)
buk_by_rut: dict[str, dict] = {}
for page in range(1, 4):
    url = f"https://linkeschile.buk.cl/api/v1/chile/payroll_detail/month?month=6&year=2026&page={page}"
    req = urllib.request.Request(url, headers={"auth_token": TOKEN, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    for rec in data["data"]:
        if rec["month"] != 6 or rec["year"] != 2026:
            continue
        rut = normalize_rut(rec["rut"])
        haberes = {}
        for line in rec.get("lines_settlement", []):
            if line["type"] == "haber" and line.get("item_code"):
                haberes[line["item_code"]] = (line["name"], line["amount"])
        buk_by_rut[rut] = haberes

print(f"Buk personas (pág 1-3): {len(buk_by_rut)}\n")

# 3. Cross-reference
print("=== PERSONAS EN AMBOS SISTEMAS ===\n")
matched = 0
for rut, oracle_codes in sorted(oracle_by_rut.items()):
    if rut not in buk_by_rut:
        continue
    buk_codes = buk_by_rut[rut]
    print(f"RUT {rut}")
    print(f"  Oracle bonos/HE : {list(oracle_codes.keys())}")
    print(f"  Buk item_codes  : {[(k, v[0]) for k, v in buk_codes.items()]}")
    print()
    matched += 1
    if matched >= 15:
        break

print(f"Total personas en ambos (muestra): {matched}")
