#!/bin/sh
# Prepara la base de datos antes de arrancar el backend.
set -eu

echo "Aplicando migraciones..."
alembic upgrade head

# Los datos de demostración solo se cargan en desarrollo. El seed es
# idempotente, así que puede ejecutarse en cada arranque.
if [ "${ENVIRONMENT:-}" = "development" ]; then
  echo "Cargando datos de demostración..."
  python -m seeds.seed
fi

exec "$@"
