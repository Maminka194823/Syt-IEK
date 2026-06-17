#!/bin/bash

# Aviation Girl V4 Discord Bot - Stop Script
# This script handles graceful shutdown of the bot

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/aviationgirl.pid"
LOG_DIR="$PROJECT_DIR/logs"

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

# Check if bot is running
check_running() {
    if [ ! -f "$PID_FILE" ]; then
        warning "PID file not found - bot may not be running"
        return 1
    fi
    
    local pid=$(cat "$PID_FILE")
    if ! ps -p "$pid" > /dev/null 2>&1; then
        warning "Bot process not found (PID: $pid) - cleaning up stale PID file"
        rm -f "$PID_FILE"
        return 1
    fi
    
    return 0
}

# Graceful shutdown
graceful_shutdown() {
    local pid=$(cat "$PID_FILE")
    log "Attempting graceful shutdown of Aviation Girl V4 (PID: $pid)..."
    
    # Send SIGTERM for graceful shutdown
    kill -TERM "$pid"
    
    # Wait for process to terminate
    local wait_time=0
    local max_wait=30  # 30 seconds
    
    while [ $wait_time -lt $max_wait ]; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            success "Bot stopped gracefully"
            rm -f "$PID_FILE"
            return 0
        fi
        
        sleep 1
        wait_time=$((wait_time + 1))
        echo -n "."
    done
    
    echo
    warning "Graceful shutdown timed out after ${max_wait} seconds"
    return 1
}

# Force shutdown
force_shutdown() {
    local pid=$(cat "$PID_FILE")
    warning "Force stopping Aviation Girl V4 (PID: $pid)..."
    
    # Send SIGKILL
    kill -KILL "$pid" 2>/dev/null || true
    
    # Wait a moment and verify
    sleep 2
    if ps -p "$pid" > /dev/null 2>&1; then
        error "Failed to force stop the bot"
        return 1
    else
        success "Bot force stopped"
        rm -f "$PID_FILE"
        return 0
    fi
}

# Stop all related processes
stop_all() {
    log "Stopping all Aviation Girl V4 processes..."
    
    # Find all python processes related to the bot
    local pids=$(pgrep -f "src.bot.discord_client" || true)
    
    if [ -z "$pids" ]; then
        log "No Aviation Girl V4 processes found"
        return 0
    fi
    
    for pid in $pids; do
        log "Stopping process $pid..."
        kill -TERM "$pid" 2>/dev/null || true
    done
    
    # Wait for processes to terminate
    sleep 5
    
    # Force kill any remaining processes
    local remaining_pids=$(pgrep -f "src.bot.discord_client" || true)
    if [ -n "$remaining_pids" ]; then
        warning "Force killing remaining processes..."
        for pid in $remaining_pids; do
            kill -KILL "$pid" 2>/dev/null || true
        done
    fi
    
    # Clean up PID file
    rm -f "$PID_FILE"
    success "All processes stopped"
}

# Show status before stopping
show_status() {
    if check_running; then
        local pid=$(cat "$PID_FILE")
        log "Current status:"
        echo "  PID: $pid"
        echo "  Memory usage: $(ps -p "$pid" -o rss= | awk '{printf "%.1f MB", $1/1024}')"
        echo "  CPU usage: $(ps -p "$pid" -o pcpu= | awk '{printf "%.1f%%", $1}')"
        echo "  Start time: $(ps -p "$pid" -o lstart= | awk '{print $2, $3, $4}')"
        echo
    fi
}

# Save final logs
save_final_logs() {
    if [ -d "$LOG_DIR" ]; then
        log "Saving final log snapshot..."
        local timestamp=$(date '+%Y%m%d_%H%M%S')
        local shutdown_log="$LOG_DIR/shutdown_${timestamp}.log"
        
        {
            echo "Aviation Girl V4 Shutdown Log - $(date)"
            echo "=========================================="
            echo
            echo "Last 50 lines of main log:"
            tail -n 50 "$LOG_DIR/aviationgirl.log" 2>/dev/null || echo "Main log not found"
            echo
            echo "Last 20 lines of error log:"
            tail -n 20 "$LOG_DIR/error.log" 2>/dev/null || echo "Error log not found"
        } > "$shutdown_log"
        
        success "Shutdown log saved to: $shutdown_log"
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "Aviation Girl V4 Discord Bot - Shutdown"
    echo "=========================================="
    echo
    
    if ! check_running; then
        success "Aviation Girl V4 is not running"
        exit 0
    fi
    
    show_status
    save_final_logs
    
    if graceful_shutdown; then
        success "Aviation Girl V4 stopped successfully"
    else
        warning "Graceful shutdown failed, attempting force stop..."
        if force_shutdown; then
            success "Aviation Girl V4 force stopped"
        else
            error "Failed to stop Aviation Girl V4"
            exit 1
        fi
    fi
    
    echo
    success "Shutdown complete"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --force        Force stop without graceful shutdown"
        echo "  --all          Stop all related processes"
        echo
        echo "This script stops the Aviation Girl V4 Discord Bot gracefully."
        echo "If graceful shutdown fails, it will attempt force stop."
        exit 0
        ;;
    --force)
        log "Force stop requested..."
        if check_running; then
            show_status
            save_final_logs
            if force_shutdown; then
                success "Aviation Girl V4 force stopped"
            else
                error "Failed to force stop Aviation Girl V4"
                exit 1
            fi
        else
            success "Aviation Girl V4 is not running"
        fi
        ;;
    --all)
        log "Stopping all related processes..."
        save_final_logs
        stop_all
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