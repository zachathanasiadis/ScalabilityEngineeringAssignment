-- Database initialization script
<<<<<<< HEAD:db/init.sql
-- Create indexes for better performance

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries(expires_at);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
=======
-- Create the database user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'nytrez') THEN
        CREATE USER nytrez WITH PASSWORD 'postgres123';
    END IF;
END
$$;

-- Grant necessary privileges to the user
GRANT ALL PRIVILEGES ON DATABASE task_queue_db TO nytrez;
GRANT ALL PRIVILEGES ON SCHEMA public TO nytrez;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nytrez;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO nytrez;

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

-- Grant privileges on the newly created tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nytrez;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO nytrez;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_workers_worker_id ON workers(worker_id);
>>>>>>> final-version:src/backend/db/init.sql

-- Create function for cleanup
CREATE OR REPLACE FUNCTION cleanup_old_tasks()
RETURNS void AS $$
BEGIN
    DELETE FROM tasks WHERE
        status = 'completed' AND
        completed_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Create function for cache cleanup
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM cache_entries WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Set up some basic PostgreSQL optimizations
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET log_statement = 'none';
ALTER SYSTEM SET log_min_duration_statement = 1000;
