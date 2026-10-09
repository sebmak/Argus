#!/bin/sh
set -e

PUID=${PUID:-99}
PGID=${PGID:-100}
UMASK=${UMASK:-002}
CONFIG_DIR=${CONFIG_DIR:-/config}

umask "$UMASK"

ORT_NUM_THREADS=${ORT_NUM_THREADS:-8}
export OMP_NUM_THREADS=${ORT_NUM_THREADS}
export OPENBLAS_NUM_THREADS=${ORT_NUM_THREADS}
export MKL_NUM_THREADS=${ORT_NUM_THREADS}
export VECLIB_MAXIMUM_THREADS=${ORT_NUM_THREADS}
export NUMEXPR_NUM_THREADS=${ORT_NUM_THREADS}

echo "========================================================"
echo " Household Face Detection API (Unraid / Docker)"
echo " PUID:       ${PUID}"
echo " PGID:       ${PGID}"
echo " UMASK:      ${UMASK}"
echo " CONFIG_DIR: ${CONFIG_DIR}"
echo " THREADS:    ${ORT_NUM_THREADS}"
echo "========================================================"

# Ensure configuration & persistence directories exist
mkdir -p "${CONFIG_DIR}" \
         "${CONFIG_DIR}/thumbnails" \
         "${CONFIG_DIR}/snapshots" \
         "${CONFIG_DIR}/models"

# Create group if missing
if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd -g "$PGID" appgroup 2>/dev/null || true
fi

# Create user if missing
if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -d /app -s /bin/sh -M appuser 2>/dev/null || true
fi

# Update ownership of the config directory to match Unraid permissions
chown -R "${PUID}:${PGID}" "${CONFIG_DIR}" 2>/dev/null || true

# If running as root, drop privileges to PUID:PGID via gosu
if [ "$(id -u)" = "0" ]; then
    exec gosu "${PUID}:${PGID}" "$@"
else
    exec "$@"
fi
