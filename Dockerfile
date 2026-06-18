FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema necesarias para Oracle Instant Client
RUN apt-get update && apt-get install -y \
    libaio1t64 \
    wget \
    unzip \
    && ln -s /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1 \
    && rm -rf /var/lib/apt/lists/*

# --- OPCIÓN A: Descargar Oracle Instant Client durante el build (requiere acceso a internet) ---
ENV ORACLE_HOME=/opt/oracle/instantclient_21_13

RUN mkdir -p /opt/oracle && \
    cd /opt/oracle && \
    wget -q https://download.oracle.com/otn_software/linux/instantclient/2113000/instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip && \
    unzip -q instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip && \
    rm instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip

# --- OPCIÓN B (sin internet): Comentar OPCIÓN A y descomentar estas líneas ---
# Descargar el zip manualmente desde Oracle y colocarlo en docker/oracle/
# COPY docker/oracle/instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip /tmp/
# RUN unzip -q /tmp/instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip -d /opt/oracle/ && \
#     rm /tmp/instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip

ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_21_13
ENV ORACLE_CLIENT_LIB_DIR=/opt/oracle/instantclient_21_13

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "-m", "src.main"]
