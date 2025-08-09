#!/bin/bash

# TaronaTop Bot Deployment Script
set -e

# Enable debug mode if DEBUG=1 is set
if [[ "${DEBUG}" == "1" ]]; then
    set -x
    echo "Debug mode enabled"
fi

echo "🚀 Starting TaronaTop Bot deployment..."

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

print_debug() {
    if [[ "${DEBUG}" == "1" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Check if Docker is installed
print_status "Checking Docker installation..."
print_debug "PATH: $PATH"
print_debug "USER: $(whoami)"

DOCKER_PATH=$(command -v docker 2>/dev/null || which docker 2>/dev/null || echo "")
if [ -z "$DOCKER_PATH" ]; then
    print_error "Docker is not found in PATH. Please ensure Docker is installed and accessible."
    print_error "Try running: docker --version"
    print_debug "Attempted to find docker using 'command -v' and 'which'"
    exit 1
fi
print_status "Docker found at: $DOCKER_PATH"

# Test Docker functionality
print_debug "Testing Docker functionality..."
if ! docker --version &>/dev/null; then
    print_error "Docker is installed but not working properly."
    print_error "You might need to start Docker daemon or check permissions."
    print_error "Try running: sudo systemctl start docker"
    exit 1
fi
DOCKER_VERSION=$(docker --version)
print_status "Docker version: $DOCKER_VERSION"

# Check if Docker Compose is installed
print_status "Checking Docker Compose installation..."
DOCKER_COMPOSE_PATH=$(command -v docker-compose 2>/dev/null || which docker-compose 2>/dev/null || echo "")
if [ -z "$DOCKER_COMPOSE_PATH" ]; then
    # Try Docker Compose V2 syntax
    print_debug "docker-compose not found, trying Docker Compose V2..."
    if docker compose version &>/dev/null; then
        DOCKER_COMPOSE_VERSION=$(docker compose version)
        print_status "Docker Compose V2 found (using 'docker compose')"
        print_status "Version: $DOCKER_COMPOSE_VERSION"
        DOCKER_COMPOSE_CMD="docker compose"
    else
        print_error "Docker Compose is not found. Please install Docker Compose."
        print_error "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
else
    DOCKER_COMPOSE_VERSION=$(docker-compose --version)
    print_status "Docker Compose found at: $DOCKER_COMPOSE_PATH"
    print_status "Version: $DOCKER_COMPOSE_VERSION"
    DOCKER_COMPOSE_CMD="docker-compose"
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from template..."
    cp .env.example .env
    print_warning "Please edit .env file with your configuration before continuing."
    read -p "Press Enter after editing .env file..."
fi

# Validate required environment variables
print_status "Validating environment configuration..."

# Source .env file with better error handling
if [ -f .env ]; then
    # Export variables from .env while handling quoted values
    set -a  # automatically export all variables
    source .env 2>/dev/null || {
        print_error "Failed to source .env file. Please check for syntax errors."
        print_error "Common issues: unquoted special characters, missing quotes"
        exit 1
    }
    set +a  # stop automatically exporting
else
    print_error ".env file not found!"
    exit 1
fi

required_vars=("BOT_TOKEN" "DJANGO_SECRET_KEY" "YOUTUBE_API_KEY" "DB_NAME" "DB_USER" "DB_PASSWORD")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    print_error "Missing required environment variables: ${missing_vars[*]}"
    print_error "Please configure these variables in .env file"
    exit 1
fi

print_status "Environment validation passed ✓"

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
chmod 755 logs

# Stop existing containers if running
print_status "Stopping existing containers..."
$DOCKER_COMPOSE_CMD down 2>/dev/null || true

# Check for PostgreSQL version conflicts
print_status "Checking for database version conflicts..."
if docker volume ls | grep -q "postgres_data"; then
    print_warning "Existing PostgreSQL volume detected."
    print_warning "If you experience database compatibility issues, you may need to:"
    print_warning "1. Backup your data: docker-compose exec db pg_dump -U postgres tarona > backup.sql"
    print_warning "2. Remove old volume: docker volume rm taronatop_bot_postgres_data"
    print_warning "3. Restart deployment"
    
    read -p "Do you want to remove the existing database volume? (y/N): " remove_volume
    if [[ $remove_volume =~ ^[Yy]$ ]]; then
        print_status "Removing existing database volume..."
        docker volume rm taronatop_bot_postgres_data 2>/dev/null || true
    fi
fi

# Build and start services
print_status "Building and starting services..."
$DOCKER_COMPOSE_CMD up -d --build

# Wait for database to be ready
print_status "Waiting for database to be ready..."
timeout=60
while ! $DOCKER_COMPOSE_CMD exec -T db pg_isready -U "${DB_USER}" >/dev/null 2>&1; do
    timeout=$((timeout - 1))
    if [ $timeout -eq 0 ]; then
        print_error "Database failed to start within 60 seconds"
        exit 1
    fi
    sleep 1
done

print_status "Database is ready ✓"

# Run migrations
print_status "Running database migrations..."
$DOCKER_COMPOSE_CMD exec -T web python manage.py migrate

# Create superuser (optional)
read -p "Do you want to create a Django superuser? (y/N): " create_superuser
if [[ $create_superuser =~ ^[Yy]$ ]]; then
    print_status "Creating Django superuser..."
    $DOCKER_COMPOSE_CMD exec web python manage.py createsuperuser
fi

# Check if services are running
print_status "Checking service status..."
if $DOCKER_COMPOSE_CMD ps | grep -q "Up"; then
    print_status "Services are running ✓"
else
    print_error "Some services failed to start"
    $DOCKER_COMPOSE_CMD logs
    exit 1
fi

# Display service URLs
print_status "Deployment completed successfully! 🎉"
echo ""
echo "Service URLs:"
echo "- Web Interface: http://localhost:8000"
echo "- Admin Panel: http://localhost:8000/admin"
echo "- Database: localhost:5454"
echo ""
echo "Useful commands:"
echo "- View logs: $DOCKER_COMPOSE_CMD logs -f"
echo "- Stop services: $DOCKER_COMPOSE_CMD down"
echo "- Restart services: $DOCKER_COMPOSE_CMD restart"
echo "- View status: $DOCKER_COMPOSE_CMD ps"
echo ""
print_status "Your TaronaTop Bot is now running!"
