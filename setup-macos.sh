#!/bin/bash

# Scalable Hash API System - macOS Setup Script
# This script sets up the entire system optimized for macOS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Check if running on macOS
check_macos() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_error "This script is designed for macOS only!"
        exit 1
    fi
    print_status "macOS detected"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        print_status "Please install Docker Desktop for Mac from: https://www.docker.com/products/docker-desktop"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker is not running!"
        print_status "Please start Docker Desktop and try again"
        exit 1
    fi

    print_status "Docker is installed and running"
}

# Check if Docker Compose is installed
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed!"
        print_status "Please install Docker Compose or use Docker Desktop which includes it"
        exit 1
    fi
    print_status "Docker Compose is installed"
}

# Optimize Docker Desktop for macOS
optimize_docker_macos() {
    print_header "Optimizing Docker for macOS"

    print_status "Recommended Docker Desktop settings for optimal performance:"
    echo "  - CPU: 4+ cores"
    echo "  - Memory: 8GB+"
    echo "  - Swap: 2GB"
    echo "  - Disk image size: 64GB+"
    echo "  - Enable VirtioFS for file sharing (if available)"
    echo "  - Enable experimental features"

    print_warning "Please adjust these settings in Docker Desktop > Preferences > Resources"
    read -p "Press Enter to continue once you've optimized Docker settings..."
}

# Create necessary directories
create_directories() {
    print_header "Creating necessary directories"

    mkdir -p monitoring
    mkdir -p logs
    mkdir -p backup

    print_status "Directories created"
}

# Create monitoring configuration
create_monitoring_config() {
    print_header "Creating monitoring configuration"

    cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'loadbalancer'
    static_configs:
      - targets: ['loadbalancer:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['db:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
EOF

    print_status "Monitoring configuration created"
}

# Create database initialization script
create_db_init() {
    print_header "Creating database initialization script"

    mkdir -p db
    cat > db/init.sql << EOF
-- Database initialization script
-- Create indexes for better performance

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries(expires_at);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);

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

-- Set up some basic PostgreSQL optimizations
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET log_statement = 'none';
ALTER SYSTEM SET log_min_duration_statement = 1000;
EOF

    print_status "Database initialization script created"
}

# Build Docker images
build_images() {
    print_header "Building Docker images"

    print_status "Building main application image..."
    docker build -t hash-api:latest .

    print_status "Building load balancer image..."
    docker build -t hash-lb:latest -f loadbalancer/Dockerfile .

    print_status "Docker images built successfully"
}

# Start the system
start_system() {
    print_header "Starting the system"

    print_status "Starting core services..."
    docker-compose -f docker-compose.production.yml up -d db redis

    print_status "Waiting for database to be ready..."
    sleep 10

    print_status "Starting application services..."
    docker-compose -f docker-compose.production.yml up -d

    print_status "System started successfully!"
}

# Check system health
check_health() {
    print_header "Checking system health"

    sleep 15  # Wait for services to start

    # Check load balancer
    if curl -f http://localhost:8000/lb/health &> /dev/null; then
        print_status "✓ Load balancer is healthy"
    else
        print_warning "✗ Load balancer health check failed"
    fi

    # Check database
    if docker-compose -f docker-compose.production.yml exec -T db pg_isready -U hashuser -d hashdb &> /dev/null; then
        print_status "✓ Database is healthy"
    else
        print_warning "✗ Database health check failed"
    fi

    # Check Redis
    if docker-compose -f docker-compose.production.yml exec -T redis redis-cli ping &> /dev/null; then
        print_status "✓ Redis is healthy"
    else
        print_warning "✗ Redis health check failed"
    fi
}

# Display system information
display_info() {
    print_header "System Information"

    echo "🌐 Application URL: http://localhost:8000"
    echo "📊 Grafana Dashboard: http://localhost:3000 (admin/admin)"
    echo "📈 Prometheus: http://localhost:9090"
    echo "🗄️  Database: localhost:5432"
    echo "🔴 Redis: localhost:6379"
    echo ""
    echo "📚 API Documentation:"
    echo "  - Health Check: GET /health"
    echo "  - MD5 Hash: POST /hash/md5"
    echo "  - SHA256 Hash: POST /hash/sha256"
    echo "  - Task Status: GET /task/{id}"
    echo "  - Load Balancer Stats: GET /lb/stats"
    echo ""
    echo "🛠️  Management Commands:"
    echo "  - Scale apps: docker-compose -f docker-compose.production.yml up -d --scale app1=5"
    echo "  - Scale workers: docker-compose -f docker-compose.production.yml up -d --scale worker1=10"
    echo "  - View logs: docker-compose -f docker-compose.production.yml logs -f"
    echo "  - Stop system: docker-compose -f docker-compose.production.yml down"
}

# Performance testing function
run_performance_test() {
    print_header "Running Performance Test"

    print_status "Testing system performance..."

    # Test basic functionality
    echo "Testing MD5 endpoint..."
    curl -X POST "http://localhost:8000/hash/md5" \
         -H "Content-Type: application/json" \
         -d '{"string": "test"}' || print_warning "MD5 test failed"

    echo ""
    echo "Testing SHA256 endpoint..."
    curl -X POST "http://localhost:8000/hash/sha256" \
         -H "Content-Type: application/json" \
         -d '{"string": "test"}' || print_warning "SHA256 test failed"

    echo ""
    print_status "Performance test completed"
}

# Main execution
main() {
    print_header "macOS Scalable Hash API Setup"

    check_macos
    check_docker
    check_docker_compose
    optimize_docker_macos
    create_directories
    create_monitoring_config
    create_db_init
    build_images
    start_system
    check_health
    display_info

    print_status "Setup completed successfully!"

    read -p "Would you like to run a performance test? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_performance_test
    fi
}

# Run main function
main "$@"