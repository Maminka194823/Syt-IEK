#!/bin/bash

# Aviation Girl V4 Discord Bot - Startup Script
# This script handles the complete startup process with validation and monitoring

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/aviationgirl.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if bot is already running
check_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            error "Aviation Girl V4 is already running (PID: $pid)"
            echo "Use './scripts/stop.sh' to stop the bot first"
            exit 1
        else
            warning "Stale PID file found, removing..."
            rm -f "$PID_FILE"
        fi
    fi
}

# Validate environment
validate_environment() {
    log "Validating environment..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed"
        exit 1
    fi
    
    local python_version=$(python3 --version | cut -d' ' -f2)
    local major_version=$(echo "$python_version" | cut -d'.' -f1)
    local minor_version=$(echo "$python_version" | cut -d'.' -f2)
    
    if [ "$major_version" -lt 3 ] || ([ "$major_version" -eq 3 ] && [ "$minor_version" -lt 9 ]); then
        error "Python 3.9 or higher is required (found: $python_version)"
        exit 1
    fi
    
    success "Python version: $python_version"
    
    # Check virtual environment
    if [ ! -d "$VENV_PATH" ]; then
        warning "Virtual environment not found, creating..."
        python3 -m venv "$VENV_PATH"
        source "$VENV_PATH/bin/activate"
        pip install --upgrade pip
        pip install -r "$PROJECT_DIR/requirements.txt"
        success "Virtual environment created and dependencies installed"
    else
        success "Virtual environment found"
    fi
    
    # Check environment file
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        if [ -f "$PROJECT_DIR/.env.example" ]; then
            warning ".env file not found, copying from .env.example"
            cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
            warning "Please edit .env file with your configuration before starting"
            exit 1
        else
            error ".env file not found and no .env.example available"
            exit 1
        fi
    fi
    
    success "Environment file found"
}

# Validate configuration
validate_configuration() {
    log "Validating configuration..."
    
    source "$VENV_PATH/bin/activate"
    
    # Run configuration validator
    if python -m src.bot.config_validator; then
        success "Configuration validation passed"
    else
        error "Configuration validation failed"
        exit 1
    fi
}

# Check system resources
check_resources() {
    log "Checking system resources..."
    
    # Check available memory (require at least 1GB free)
    local available_mem=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    if [ "$available_mem" -lt 1024 ]; then
        warning "Low available memory: ${available_mem}MB (recommended: 1GB+)"
    else
        success "Available memory: ${available_mem}MB"
    fi
    
    # Check disk space (require at least 1GB free)
    local available_disk=$(df "$PROJECT_DIR" | awk 'NR==2{printf "%.0f", $4/1024}')
    if [ "$available_disk" -lt 1024 ]; then
        warning "Low disk space: ${available_disk}MB (recommended: 1GB+)"
    else
        success "Available disk space: ${available_disk}MB"
    fi
}

# Test external connections
test_connections() {
    log "Testing external connections..."
    
    # Test Discord API
    if curl -s --max-time 10 https://discord.com/api/v10/gateway > /dev/null; then
        success "Discord API connection: OK"
    else
        warning "Discord API connection: FAILED"
    fi
    
    # Test internet connectivity
    if curl -s --max-time 5 https://www.google.com > /dev/null; then
        success "Internet connectivity: OK"
    else
        warning "Internet connectivity: FAILED"
    fi
}

# Setup logging
setup_logging() {
    log "Setting up logging..."
    
    # Create log directory if it doesn't exist
    mkdir -p "$LOG_DIR"
    
    # Create log files if they don't exist
    touch "$LOG_DIR/aviationgirl.log"
    touch "$LOG_DIR/error.log"
    touch "$LOG_DIR/access.log"
    
    success "Logging setup complete"
}

# Start the bot
start_bot() {
    log "Starting Aviation Girl V4 Discord Bot..."
    
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Start the bot in background
    nohup python -m src.bot.discord_client > "$LOG_DIR/aviationgirl.log" 2>&1 &
    local bot_pid=$!
    
    # Save PID
    echo "$bot_pid" > "$PID_FILE"
    
    # Wait a moment and check if process is still running
    sleep 3
    if ps -p "$bot_pid" > /dev/null 2>&1; then
        success "Aviation Girl V4 started successfully (PID: $bot_pid)"
        
        # Wait for health check to be available
        log "Waiting for health check endpoint..."
        local health_check_attempts=0
        local max_attempts=30
        
        while [ $health_check_attempts -lt $max_attempts ]; do
            if curl -s --max-time 5 http://localhost:8081/health > /dev/null 2>&1; then
                success "Health check endpoint is responding"
                break
            fi
            
            health_check_attempts=$((health_check_attempts + 1))
            sleep 2
            echo -n "."
        done
        
        if [ $health_check_attempts -eq $max_attempts ]; then
            warning "Health check endpoint not responding after ${max_attempts} attempts"
        fi
        
        echo
        success "Aviation Girl V4 is now running!"
        echo
        echo "Useful commands:"
        echo "  - View logs: tail -f $LOG_DIR/aviationgirl.log"
        echo "  - Check status: ./scripts/status.sh"
        echo "  - Stop bot: ./scripts/stop.sh"
        echo "  - Health check: curl http://localhost:8081/health"
        echo
        
    else
        error "Failed to start Aviation Girl V4"
        rm -f "$PID_FILE"
        echo "Check the log file for details: $LOG_DIR/aviationgirl.log"
        exit 1
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "Aviation Girl V4 Discord Bot - Startup"
    echo "=========================================="
    echo
    
    check_running
    validate_environment
    validate_configuration
    check_resources
    test_connections
    setup_logging
    start_bot
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --no-checks    Skip environment and connection checks"
        echo "  --force        Force start even if checks fail"
        echo
        echo "This script starts the Aviation Girl V4 Discord Bot with full"
        echo "environment validation and health checks."
        exit 0
        ;;
    --no-checks)
        log "Skipping environment and connection checks..."
        check_running
        setup_logging
        start_bot
        ;;
    --force)
        log "Force mode: starting with minimal checks..."
        check_running
        setup_logging
        start_bot
        ;;
    "")
        main
        ;;
    *)
        error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac