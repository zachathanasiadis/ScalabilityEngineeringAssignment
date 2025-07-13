-- Database initialization script
-- Create indexes for better performance

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries(expires_at);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);

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
