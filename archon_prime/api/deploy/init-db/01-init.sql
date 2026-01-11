-- ARCHON PRIME - Database Initialization Script
-- Runs on first container start (when data volume is empty)

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create application schema (optional, for multi-tenant isolation)
-- CREATE SCHEMA IF NOT EXISTS archon;

-- Grant permissions (if using separate roles)
-- GRANT ALL PRIVILEGES ON DATABASE archon_prime TO archon_app;
-- GRANT ALL PRIVILEGES ON SCHEMA public TO archon_app;

-- Performance tuning for trading workloads
-- (These are suggestions - adjust based on your instance size)

-- Connection settings
ALTER SYSTEM SET max_connections = '200';

-- Memory settings (adjust based on available RAM)
-- ALTER SYSTEM SET shared_buffers = '256MB';
-- ALTER SYSTEM SET effective_cache_size = '768MB';
-- ALTER SYSTEM SET work_mem = '16MB';
-- ALTER SYSTEM SET maintenance_work_mem = '128MB';

-- Write-ahead logging (for durability)
ALTER SYSTEM SET wal_level = 'replica';
ALTER SYSTEM SET max_wal_size = '1GB';

-- Query planner
ALTER SYSTEM SET random_page_cost = '1.1';  -- SSD optimization
ALTER SYSTEM SET effective_io_concurrency = '200';  -- SSD optimization

-- Logging (for debugging)
ALTER SYSTEM SET log_min_duration_statement = '1000';  -- Log queries > 1s
ALTER SYSTEM SET log_checkpoints = 'on';
ALTER SYSTEM SET log_connections = 'on';
ALTER SYSTEM SET log_disconnections = 'on';

-- Timezone (use UTC for trading)
ALTER SYSTEM SET timezone = 'UTC';

-- Note: Alembic migrations handle table creation
-- This script only handles PostgreSQL configuration
