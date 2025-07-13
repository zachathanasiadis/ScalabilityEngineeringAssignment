#!/bin/bash
set -e

# Use environment variables with defaults
DB_USER=${DB_USER:-}
DB_PASSWORD=${DB_PASSWORD:-}
DB_NAME=${DB_NAME:-}
DB_USER_CONNECTION_LIMIT=${DB_USER_CONNECTION_LIMIT:-}

echo "Initializing database with user: $DB_USER, database: $DB_NAME"
echo "Setting user connection limit to: $DB_USER_CONNECTION_LIMIT"

# Create the custom database and user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
-- Database initialization script

-- Create the custom database if it doesn't exist
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Create the database user if it doesn't exist
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD' CONNECTION LIMIT $DB_USER_CONNECTION_LIMIT;
        RAISE NOTICE 'Created user $DB_USER with connection limit $DB_USER_CONNECTION_LIMIT';
    ELSE
        -- User exists, update connection limit
        ALTER USER $DB_USER CONNECTION LIMIT $DB_USER_CONNECTION_LIMIT;
        RAISE NOTICE 'Updated connection limit for existing user $DB_USER to $DB_USER_CONNECTION_LIMIT';
    END IF;
END
\$\$;

-- Grant necessary privileges to the user
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOSQL

# Now connect to the custom database to set up tables and grant schema privileges
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
-- Grant schema privileges and set up default privileges
GRANT ALL PRIVILEGES ON SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO $DB_USER;

-- Drop existing tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS workers CASCADE;
DROP TABLE IF EXISTS cache_entries CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;

-- Create required tables with correct schema
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    task_type TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    parameters JSONB,
    result JSONB,
    error TEXT
);

CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key VARCHAR(64) PRIMARY KEY,
    value_data TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workers (
    id SERIAL PRIMARY KEY,
    worker_id VARCHAR(50) NOT NULL UNIQUE,
    status VARCHAR(20) DEFAULT 'idle',
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_task_id INTEGER REFERENCES tasks(id)
);

-- Transfer ownership of all objects to the custom user
ALTER TABLE tasks OWNER TO $DB_USER;
ALTER TABLE cache_entries OWNER TO $DB_USER;
ALTER TABLE workers OWNER TO $DB_USER;

-- Transfer ownership of sequences
ALTER SEQUENCE tasks_id_seq OWNER TO $DB_USER;
ALTER SEQUENCE workers_id_seq OWNER TO $DB_USER;

-- Grant all privileges to ensure full access
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_workers_worker_id ON workers(worker_id);

-- Create function for cleanup
CREATE OR REPLACE FUNCTION cleanup_old_tasks()
RETURNS void AS \$\$
BEGIN
    DELETE FROM tasks WHERE
        status = 'completed' AND
        completed_at < NOW() - INTERVAL '7 days';
END;
\$\$ LANGUAGE plpgsql;

-- Create function for cache cleanup
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS \$\$
BEGIN
    DELETE FROM cache_entries WHERE expires_at < NOW();
END;
\$\$ LANGUAGE plpgsql;

-- Transfer ownership of functions to the custom user
ALTER FUNCTION cleanup_old_tasks() OWNER TO $DB_USER;
ALTER FUNCTION cleanup_expired_cache() OWNER TO $DB_USER;

-- Set up some basic PostgreSQL optimizations
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET log_statement = 'none';
ALTER SYSTEM SET log_min_duration_statement = 1000;

EOSQL

echo "Database initialization completed successfully!"