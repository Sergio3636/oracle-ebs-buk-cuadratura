from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class OracleRecord:
    periodo: str
    nom_sitio: str
    num_reporte: int
    estado_reporte: str
    aprobador: Optional[str]
    rut: str
    nombre: Optional[str]
    cargo: Optional[str]
    cod_haber: str
    monto: Decimal


@dataclass
class BukRecord:
    rut: str
    nombre: str
    cod_concepto: str       # Oracle cod_haber after translation
    nombre_concepto: str
    monto: Decimal
    periodo: str = ""


@dataclass
class ReconciliationRow:
    periodo: str
    nom_sitio: str
    num_reporte: int
    estado_reporte: str
    rut: str
    nombre: str
    cargo: str
    cod_haber: str
    descripcion_haber: str
    monto_oracle: Decimal
    monto_buk: Decimal
    diferencia: Decimal

    @property
    def tiene_diferencia(self) -> bool:
        return abs(self.diferencia) > Decimal("0.01")
