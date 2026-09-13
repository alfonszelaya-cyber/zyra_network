# ZYRA Network — Runbook de Producción

Guía completa de despliegue del sistema de confianza digital.
Todo en orden: si sigues los pasos de arriba a abajo, la red queda viva,
persistente, con biometría activa y respaldos automáticos.

## 1. REQUISITOS DEL SERVIDOR

- Linux (Ubuntu 22.04+ recomendado)
- Python 3.11 (o Docker)
- Mínimo: 2 CPU, 4 GB RAM (con el ojo facial activo)
- Disco: 10 GB + espacio para backups (crece con la red)
- Carpeta de datos FUERA de /tmp (ejemplo: /data/zyra)
- Carpeta de backups FUERA del servidor si es posible

## 2. PREPARAR EL SERVIDOR (sin Docker)

git clone https://github.com/alfonszel/zyra_network.git
cd zyra_network

sudo mkdir -p /data/zyra /data/models /backups
sudo chown -R $USER:$USER /data /backups

pip install --upgrade pip
pip install -r requirements.txt

Nota: instalar insightface compila código y tarda unos minutos. Es normal.

## 3. VARIABLES DE ENTORNO (obligatorias)

export ZYRA_ROOT_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
echo "GUARDA ESTA LLAVE: $ZYRA_ROOT_KEY"

export ZYRA_API_TOKEN="cambia-esto-por-un-token-largo-y-seguro"

export ZYRA_DATA_DIR=/data/zyra

export ZYRA_PORT=8000

export ZYRA_BIOMETRICS_PROVIDER=insightface
export ZYRA_BIOMETRICS_MODELS_DIR=/data/models

Recomendación: pon estas variables en /etc/environment para que sobrevivan reinicios.

## 4. PRIMER ARRANQUE

python main.py

Qué esperar en el log, en orden:

1. data directory: /data/zyra — datos en ruta persistente
2. root authority: ... fingerprint=... — autoridad criptográfica creada
3. biometrics engine wired — motor montado
4. Zyra Network is LIVE — red viva
5. combined surface on port 8000 — API escuchando

El primer arranque con el ojo activo descarga el modelo (~300 MB) a /data/models. Solo pasa una vez.

## 5. VERIFICACIÓN DE SALUD

curl -s http://localhost:8000/health

Checklist:
- "overall" → HEALTHY
- En components debe aparecer: storage, identity, verification, tokens, currency, biometrics
- biometrics con detail: engine wired

Si biometrics NO aparece: falta ZYRA_ROOT_KEY en el entorno.

## 6. REGISTRO OFICIAL DE IDENTIDAD (prueba de humo)

curl -s -X POST http://localhost:8000/identity/enroll -H "Authorization: Bearer $ZYRA_API_TOKEN" -H "Content-Type: application/json" -d '{"kind":"person","display_name":"Prueba","actor":"operador","doc_image_b64":"aW1hZ2Vu","selfie_image_b64":"aW1hZ2Vu"}'

Respuestas posibles:
- 422 biometrics_gate → correcto: la bóveda analizó y rechazó. LA PUERTA FUNCIONA.
- 400 template_quality → correcto: el ojo no encontró rostro. LA PUERTA FUNCIONA.
- 503 biometrics_unavailable → el ojo no está activo: revisa ZYRA_BIOMETRICS_PROVIDER

En producción real con documento y selfie de una persona:
- Aprobada → 201 con su ZID y nivel L1/L2
- Duplicada → 422 con duplicate_of (fraude bloqueado)
- Dudosa → 422 con case_id → revisión humana con /proofing/review

## 7. BACKUP AUTOMÁTICO DIARIO

Probar una vez a mano:
python scripts/backup.py --data-dir /data/zyra --snapshot-dir /backups --keep 60

Programar diario a las 3 AM (comando: crontab -e):
0 3 * * * cd /ruta/real/a/zyra_network && python scripts/backup.py --data-dir /data/zyra --snapshot-dir /backups --keep 60 >> /backups/backup.log 2>&1

Regla de oro: un backup SOLO en el servidor no es un backup. Sincroniza /backups hacia otro disco o ubicación externa.

## 8. DESPLIEGUE CON DOCKER (alternativa)

cd zyra_network
export ZYRA_ROOT_KEY="$(python -c "import secrets; print(secrets.token_hex(32))")"
export ZYRA_API_TOKEN="cambia-esto-por-un-token-largo-y-seguro"
export ZYRA_BIOMETRICS_PROVIDER=insightface

docker compose -f docker/docker-compose.yml up -d --build
docker logs -f zyra_network_core

Los volúmenes zyra_data y zyra_models ya están configurados: datos y modelo sobreviven a la recreación del contenedor.

## 9. SI ALGO FALLA (los 4 más comunes)

1. DATA DIR IS EPHEMERAL en el log → ZYRA_DATA_DIR apunta a /tmp → Cámbiala a /data/zyra y reinicia
2. biometrics_unavailable en enroll → Ojo no activo o sin llave → Revisa ZYRA_ROOT_KEY y ZYRA_BIOMETRICS_PROVIDER
3. libGL.so.1: cannot open → OpenCV pide librería gráfica → comando: sudo apt install -y libgl1 y reinicia
4. Health sin componente biometrics → Motor sin ZYRA_ROOT_KEY → Exporta la llave y reinicia

## 10. CHECKLIST FINAL DE PRODUCCIÓN

- ZYRA_ROOT_KEY generada y guardada en lugar seguro (fuera del servidor también)
- ZYRA_API_TOKEN configurado (mínimo 16 caracteres)
- Datos en /data/zyra (sin warning de /tmp en el log)
- Health en verde con componente biometrics
- Ojo activo: enroll responde 422/400, nunca 503
- Backup a mano probado y archivo visible en /backups
- Cron de backup instalado
- /backups sincronizado a ubicación externa
- Puerto expuesto detrás de HTTPS en producción pública

Red lista. Confianza digital en producción.
