# Cuadratura Oracle EBS vs Buk — v1.0

Proceso mensual de reconciliación (cuadratura) que compara los haberes registrados en el módulo de remuneraciones custom de **Oracle EBS** contra las liquidaciones de **Buk HR**, persona a persona y código a código.

Genera un reporte Excel con diferencias marcadas en rojo y se ejecuta 100% dentro de Docker con Oracle thick client.

---

## Qué hace

- Extrae haberes y horas extras del módulo Oracle (`APPS.XXGL_CARGA_REMU_DETALLE`) filtrados por período
- Consulta el juego de valores `XX_FORM_HAB_PAYROLL` (tabla `APPLSYS.FND_FLEX_VALUES`) para obtener el mapeo Oracle cohade ↔ Buk item_code, filtrado a los haberes presentes en el período
- Descarga liquidaciones del período desde la API REST de Buk (`payroll_detail/month?date=DD-MM-YYYY`)
- Cruza ambos sistemas por **RUT + código de haber**
- Agrega sub-códigos de horas extras Oracle (HEX051-059, HEX060, HEX062 → HEX051 al 50%, etc.)
- Genera un Excel de 5 hojas con el detalle completo
- (Opcional) Envía el reporte por correo

---

## Estructura del proyecto

```
oracle_python_docker/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── scripts/
│   └── run_cuadratura.py        # Punto de entrada principal
├── src/
│   ├── buk/
│   │   └── client.py            # Cliente API Buk (paginación, mapeo HE, normalización RUT)
│   ├── config/
│   │   └── settings.py          # Variables de entorno (pydantic-settings)
│   ├── database/
│   │   └── connection.py        # Pool Oracle thick client
│   ├── notifications/
│   │   └── email.py             # Envío de reporte por SMTP
│   ├── oracle/
│   │   └── queries.py           # Queries Oracle + agregación HE + mapa XX_FORM_HAB_PAYROLL
│   ├── reconciliation/
│   │   ├── engine.py            # Motor de cuadratura Oracle vs Buk
│   │   └── models.py            # Dataclasses OracleRecord, BukRecord, ReconciliationRow
│   ├── reports/
│   │   └── excel.py             # Generador Excel (5 hojas, openpyxl)
│   └── utils.py                 # normalize_rut (puntos, mayúsculas)
└── tests/
    └── test_reconciliation.py   # 12 tests unitarios
```

---

## Reporte Excel — 5 hojas

| Hoja | Contenido |
|---|---|
| **Haberes** | Códigos `B%` — montos en CLP. Diferencias en rojo. |
| **Horas Extras HH** | Códigos `H%` — valores en horas. Diferencias en rojo. |
| **Solo Diferencias** | Filas con diferencia de ambos tipos agrupadas. |
| **Resumen** | Totales por sitio y por código haber. |
| **Códigos Haber** | Tabla de equivalencia Oracle `cohade` ↔ Buk `item_code`, con totales y estado del período. |

---

## Mapeo Oracle ↔ Buk

### Bonos (B%)

El mapeo se obtiene en tiempo de ejecución desde el juego de valores Oracle **`XX_FORM_HAB_PAYROLL`** (`APPLSYS.FND_FLEX_VALUES`). Cada entrada del juego tiene:

- `flex_value` con formato `ESN-<cohade>` (ej. `ESN-BONOBR`) — se extrae el código después del `-`
- `attribute1` con el código Winper de Buk — se prefija con `l` (ej. `l260`)

```
flex_value       →  cohade    →  Buk item_code
ESN-BONOBR       →  BONOBR    →  l260
ESN-BOGEMA       →  BOGEMA    →  l160
...
```

El mapeo se filtra automáticamente a los haberes que existen en el período consultado: primero se obtienen los `cod_haber` de Oracle para el período y luego se consulta el juego de valores solo para esos códigos.

### Horas Extras (H%)

Los sub-códigos Oracle se agregan a un código canónico y se comparan contra el `item_code` Buk:

| Oracle (subcódigos sumados) | Buk item_code | Horas en |
|---|---|---|
| HEX051-059, HEX060, HEX062 → **HEX051** | `horas_extras_50percent` | `description`: `"(28)"` |
| HEX100, HEX101, HEX064 → **HEX100** | `horas_extras_100percent` | `description` |
| HEX102 → **HEX102** | `l102` | `description` |
| HEX103 → **HEX103** | `l103` | `description` |

> Los valores de horas se extraen del campo `description` de Buk (`"(28)"` = 28 HH), nunca del campo `amount` (que es CLP).

---

## Instalación en Linux

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd oracle_python_docker
```

### 2. Crear el directorio de reportes

El directorio `reportes/` está en `.gitignore` y no se incluye en el repositorio. Créalo antes de levantar Docker para evitar que sea creado como `root`:

```bash
mkdir -p reportes
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con los valores reales (ver sección [Variables de entorno](#variables-de-entorno)).

### 4. Oracle Instant Client

**Opción A — Descarga automática durante el build** *(requiere internet)*

El `Dockerfile` descarga el Instant Client 21.13 desde Oracle. No requiere acción adicional.

**Opción B — Copia local** *(sin internet / red corporativa sin acceso a Oracle)*

1. Descargar `instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip` desde [Oracle](https://www.oracle.com/database/technologies/instant-client/linux-x86-64-downloads.html)
2. Colocar el ZIP en `docker/oracle/`:
   ```bash
   mkdir -p docker/oracle
   cp instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip docker/oracle/
   ```
3. En el `Dockerfile`, comentar la sección **OPCIÓN A** y descomentar la **OPCIÓN B**

### 5. Build y ejecución

```bash
docker compose build
docker compose run --rm app python scripts/run_cuadratura.py --periodo 052026 --no-email
```

---

## Uso

### Generar reporte (sin enviar correo)

```bash
docker compose run --rm app python scripts/run_cuadratura.py --periodo 052026 --no-email
```

El Excel se guarda en `./reportes/Cuadratura_052026_YYYYMMDD_HHMMSS.xlsx`.

### Generar y enviar por correo

```bash
docker compose run --rm app python scripts/run_cuadratura.py --periodo 052026 --emails rrhh@empresa.cl,finanzas@empresa.cl
```

### Parámetros

| Parámetro | Descripción | Default |
|---|---|---|
| `--periodo MMYYYY` | Período a procesar, ej: `052026` | obligatorio |
| `--no-email` | Genera Excel sin enviar correo | — |
| `--emails EMAIL,...` | Destinatarios del reporte | — |
| `--output DIR` | Directorio de salida | `./reportes` |

### Tests

```bash
docker compose run --rm app python -m pytest tests/ -v
```

12 tests unitarios que cubren: cuadratura OK/diferencia/solo Oracle/solo Buk, agregación HE, parseo de horas, normalización RUT.

---

## Configuración

### Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `DB_USER` | Usuario Oracle | — |
| `DB_PASSWORD` | Contraseña Oracle | — |
| `DB_HOST` | Host/IP Oracle | — |
| `DB_PORT` | Puerto Oracle | `1521` |
| `DB_SERVICE_NAME` | SERVICE_NAME Oracle | — |
| `ORACLE_CLIENT_LIB_DIR` | Ruta Instant Client en el contenedor | `/opt/oracle/instantclient_21_13` |
| `BUK_API_URL` | Base URL API Buk | — |
| `BUK_API_TOKEN` | Token de autenticación Buk | — |
| `SMTP_HOST` | Host SMTP para envío de correo | — |
| `SMTP_PORT` | Puerto SMTP | `587` |
| `SMTP_USER` | Usuario SMTP | — |
| `SMTP_PASSWORD` | Contraseña SMTP | — |
| `EMAIL_FROM` / `SMTP_FROM` | Dirección remitente | — |

---

## Tablas Oracle utilizadas

| Tabla | Schema | Uso |
|---|---|---|
| `XXGL_CARGA_REMU_DETALLE` | `APPS` | Registros de haberes del módulo custom de remuneraciones |
| `XXGL_CARGA_REMU` | `APPS` | Encabezado de carga (período, estado, aprobador) |
| `XXGL_SITIO` | `APPS` | Nombre del sitio/faena |
| `XXHR_PERSONAL_JDC` | — | Nombre y cargo del trabajador |
| `PER_ALL_PEOPLE_F` | `APPS` | Nombre del aprobador |
| `FND_FLEX_VALUES` | `APPLSYS` | Juego de valores `XX_FORM_HAB_PAYROLL` — mapeo cohade ↔ Buk item_code |
| `FND_FLEX_VALUES_TL` | `APPLSYS` | Descripción multilenguaje del juego de valores |
| `FND_FLEX_VALUE_SETS` | `APPLSYS` | Lookup del set por nombre (`XX_FORM_HAB_PAYROLL`) |
| `FND_FLEX_VALUES` | `APPS` | Juego de valores `XX_HABERES_PAYROLL` (ID=1010039) — descripciones oficiales de haberes |
