#!/bin/bash
set -e

echo "🚀 Starting GyanSaathiAI container..."

# Create data directories if they don't exist
mkdir -p /var/lib/postgresql/data /var/lib/mongodb /var/log/supervisor

# Fix permissions
chown -R postgres:postgres /var/lib/postgresql
chown -R mongodb:mongodb /var/lib/mongodb

# Initialize PostgreSQL if needed
if [ ! -f /var/lib/postgresql/data/PG_VERSION ]; then
    echo "📊 Initializing PostgreSQL..."
    su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/lib/postgresql/data"
    echo "host all all 127.0.0.1/32 trust" >> /var/lib/postgresql/data/pg_hba.conf
    echo "listen_addresses = '127.0.0.1'" >> /var/lib/postgresql/data/postgresql.conf
fi

# Start PostgreSQL temporarily to run migrations
echo "🗄️ Starting PostgreSQL for migrations..."
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/data -l /var/log/postgresql.log start"

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
until su postgres -c "psql -c 'SELECT 1'" >/dev/null 2>&1; do
    sleep 1
done

# Create database and run migrations
echo "🔧 Running database setup..."
su postgres -c "createdb aitutor" 2>/dev/null || true
su postgres -c "psql -d aitutor -c 'CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"; CREATE EXTENSION IF NOT EXISTS vector;'" 2>/dev/null || true

# Run migrations
if [ -f /app/backend/migrations/0001_init.sql ]; then
    su postgres -c "psql -d aitutor -f /app/backend/migrations/0001_init.sql"
fi

# Stop PostgreSQL to let supervisor manage it
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/data stop"

# Initialize MongoDB data directory
if [ ! -d /var/lib/mongodb/aitutor ]; then
    echo "🍃 Initializing MongoDB..."
    mkdir -p /var/lib/mongodb
    chown -R mongodb:mongodb /var/lib/mongodb
fi

echo "✅ Initialization complete. Starting all services..."

# Start supervisor to manage all processes
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
