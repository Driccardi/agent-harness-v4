#!/bin/bash
# scripts/init_postgres.sh
# Initializes PostgreSQL data directory, creates atlas database,
# applies schema, then hands off to supervisord.

set -e

PGDATA=/data/postgres
PGUSER=atlas
PGDB=atlas
PGPASSWORD="${MC_DB_PASSWORD:-dev}"

# Initialize cluster if not already done
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "[init] Initializing PostgreSQL cluster at $PGDATA"
    su postgres -c "initdb -D $PGDATA --encoding=UTF8 --locale=C"

    # Configure pg_hba for local auth
    cat > "$PGDATA/pg_hba.conf" << 'EOF'
local   all             postgres                                trust
local   all             all                                     md5
host    all             all             127.0.0.1/32            md5
EOF

    # Start postgres temporarily to create user and database
    su postgres -c "pg_ctl -D $PGDATA -l /tmp/pg_init.log start"
    sleep 3

    su postgres -c "psql -c \"CREATE USER $PGUSER WITH PASSWORD '$PGPASSWORD';\""
    su postgres -c "psql -c \"CREATE DATABASE $PGDB OWNER $PGUSER;\""
    su postgres -c "psql -d $PGDB -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
    su postgres -c "psql -d $PGDB -c 'CREATE EXTENSION IF NOT EXISTS pgcrypto;'"

    # Apply schema
    PGPASSWORD="$PGPASSWORD" psql -h 127.0.0.1 -U $PGUSER -d $PGDB < /app/db/schema.sql
    echo "[init] Schema applied"

    su postgres -c "pg_ctl -D $PGDATA stop"
    echo "[init] PostgreSQL initialized"
else
    echo "[init] PostgreSQL already initialized"
fi

# Create log directory
mkdir -p /var/log/mc /var/log/supervisor

# Hand off to supervisord
echo "[init] Starting supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/memory-core.conf
