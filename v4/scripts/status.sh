#!/bin/bash

# Aviation Girl V4 Discord Bot - Status Script
# This script provides comprehensive status information about the bot

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
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

header() {
    echo -e "${CYAN}$1${NC}"
}

# Check if bot is running
check_process_status() {
    header "Process Status"
    echo "=============="
    
    if [ ! -f "$PID_FILE" ]; then
        error "PID file not found - bot is not running"
        return 1
    fi
    
    local pid=$(cat "$PID_FILE")
    if ps -p "$pid" > /dev/null 2>&1; then
        success "Bot is running (PID: $pid)"
        
        # Get process details
        local process_info=$(ps -p "$pid" -o pid,ppid,user,pcpu,pmem,vsz,rss,tty,stat,start,time,comm --no-headers)
        echo "Process details:"
        echo "  PID: $(echo $process_info | awk '{print $1}')"
        echo "  User: $(echo $process_info | awk '{print $3}')"
        echo "  CPU: $(echo $process_info | awk '{print $4}')%"
        echo "  Memory: $(echo $process_info | awk '{print $5}')% ($(echo $process_info | awk '{printf "%.1f MB", $7/1024}'))"
        echo "  Status: $(echo $process_info | awk '{print $9}')"
        echo "  Started: $(echo $process_info | awk '{print $10}')"
        echo "  Runtime: $(echo $process_info | awk '{print $11}')"
        
        return 0
    else
        error "Bot process not found (stale PID: $pid)"
        return 1
    fi
}

# Check health endpoints
check_health_endpoints() {
    header "Health Endpoints"
    echo "================"
    
    # Health check endpoint
    if curl -s --max-time 5 http://localhost:8081/health > /dev/null 2>&1; then
        success "Health endpoint: http://localhost:8081/health"
        local health_response=$(curl -s --max-time 5 http://localhost:8081/health)
        echo "  Response: $health_response"
    else
        error "Health endpoint not responding: http://localhost:8081/health"
    fi
    
    # Detailed health endpoint
    if curl -s --max-time 5 http://localhost:8081/health/detailed > /dev/null 2>&1; then
        success "Detailed health endpoint: http://localhost:8081/health/detailed"
    else
        warning "Detailed health endpoint not responding: http://localhost:8081/health/detailed"
    fi
    
    # Metrics endpoint
    if curl -s --max-time 5 http://localhost:8080/metrics > /dev/null 2>&1; then
        success "Metrics endpoint: http://localhost:8080/metrics"
    else
        warning "Metrics endpoint not responding: http://localhost:8080/metrics"
    fi
}

# Check system resources
check_system_resources() {
    header "System Resources"
    echo "================"
    
    # Memory usage
    local memory_info=$(free -h | grep "Mem:")
    local total_mem=$(echo $memory_info | awk '{print $2}')
    local used_mem=$(echo $memory_info | awk '{print $3}')
    local free_mem=$(echo $memory_info | awk '{print $4}')
    local available_mem=$(echo $memory_info | awk '{print $7}')
    
    echo "Memory:"
    echo "  Total: $total_mem"
    echo "  Used: $used_mem"
    echo "  Free: $free_mem"
    echo "  Available: $available_mem"
    
    # Disk usage
    local disk_info=$(df -h "$PROJECT_DIR" | tail -1)
    local disk_total=$(echo $disk_info | awk '{print $2}')
    local disk_used=$(echo $disk_info | awk '{print $3}')
    local disk_available=$(echo $disk_info | awk '{print $4}')
    local disk_percent=$(echo $disk_info | awk '{print $5}')
    
    echo "Disk (project directory):"
    echo "  Total: $disk_total"
    echo "  Used: $disk_used ($disk_percent)"
    echo "  Available: $disk_available"
    
    # CPU load
    local load_avg=$(uptime | awk -F'load average:' '{print $2}')
    echo "CPU Load Average:$load_avg"
    
    # Check if resources are concerning
    local available_mem_mb=$(echo $available_mem | sed 's/[^0-9]//g')
    if [ "$available_mem_mb" -lt 500 ]; then
        warning "Low available memory: $available_mem"
    fi
    
    local disk_percent_num=$(echo $disk_percent | sed 's/%//')
    if [ "$disk_percent_num" -gt 90 ]; then
        warning "High disk usage: $disk_percent"
    fi
}

# Check log files
check_logs() {
    header "Log Files"
    echo "========="
    
    if [ -d "$LOG_DIR" ]; then
        for log_file in "$LOG_DIR"/*.log; do
            if [ -f "$log_file" ]; then
                local file_name=$(basename "$log_file")
                local file_size=$(du -h "$log_file" | cut -f1)
                local last_modified=$(stat -c %y "$log_file" | cut -d'.' -f1)
                
                echo "$file_name:"
                echo "  Size: $file_size"
                echo "  Last modified: $last_modified"
                
                # Check for recent errors
                local recent_errors=$(grep -i "error\|exception\|failed" "$log_file" 2>/dev/null | tail -5 | wc -l)
                if [ "$recent_errors" -gt 0 ]; then
                    warning "  Recent errors found: $recent_errors"
                fi
            fi
        done
    else
        warning "Log directory not found: $LOG_DIR"
    fi
}

# Check external connections
check_connections() {
    header "External Connections"
    echo "===================="
    
    # Discord API
    if curl -s --max-time 10 https://discord.com/api/v10/gateway > /dev/null; then
        success "Discord API: Connected"
    else
        error "Discord API: Connection failed"
    fi
    
    # Internet connectivity
    if curl -s --max-time 5 https://www.google.com > /dev/null; then
        success "Internet: Connected"
    else
        error "Internet: Connection failed"
    fi
    
    # DNS resolution
    if nslookup discord.com > /dev/null 2>&1; then
        success "DNS: Working"
    else
        error "DNS: Resolution failed"
    fi
}

# Check configuration
check_configuration() {
    header "Configuration"
    echo "============="
    
    # Environment file
    if [ -f "$PROJECT_DIR/.env" ]; then
        success "Environment file: Found"
        local env_size=$(du -h "$PROJECT_DIR/.env" | cut -f1)
        echo "  Size: $env_size"
    else
        error "Environment file: Not found"
    fi
    
    # Configuration files
    local config_dir="$PROJECT_DIR/config"
    if [ -d "$config_dir" ]; then
        success "Configuration directory: Found"
        local config_count=$(find "$config_dir" -name "*.json" | wc -l)
        echo "  JSON config files: $config_count"
    else
        warning "Configuration directory: Not found"
    fi
    
    # Virtual environment
    local venv_path="$PROJECT_DIR/venv"
    if [ -d "$venv_path" ]; then
        success "Virtual environment: Found"
        if [ -f "$venv_path/bin/python" ]; then
            local python_version=$("$venv_path/bin/python" --version 2>&1)
            echo "  Python version: $python_version"
        fi
    else
        error "Virtual environment: Not found"
    fi
}

# Show recent activity
show_recent_activity() {
    header "Recent Activity"
    echo "==============="
    
    local main_log="$LOG_DIR/aviationgirl.log"
    if [ -f "$main_log" ]; then
        echo "Last 10 log entries:"
        tail -n 10 "$main_log" | while read line; do
            echo "  $line"
        done
    else
        warning "Main log file not found"
    fi
    
    echo
    local error_log="$LOG_DIR/error.log"
    if [ -f "$error_log" ] && [ -s "$error_log" ]; then
        echo "Recent errors (last 5):"
        tail -n 5 "$error_log" | while read line; do
            echo "  $line"
        done
    else
        success "No recent errors found"
    fi
}

# Show performance metrics
show_performance_metrics() {
    header "Performance Metrics"
    echo "==================="
    
    if check_process_status > /dev/null 2>&1; then
        local pid=$(cat "$PID_FILE")
        
        # Process uptime
        local start_time=$(ps -p "$pid" -o lstart= | awk '{print $2, $3, $4}')
        echo "Uptime: Started $start_time"
        
        # File descriptors
        local fd_count=$(ls /proc/$pid/fd 2>/dev/null | wc -l)
        echo "Open file descriptors: $fd_count"
        
        # Network connections
        local net_connections=$(netstat -p 2>/dev/null | grep "$pid" | wc -l)
        echo "Network connections: $net_connections"
        
        # Memory details
        if [ -f "/proc/$pid/status" ]; then
            local vm_peak=$(grep VmPeak /proc/$pid/status | awk '{print $2, $3}')
            local vm_size=$(grep VmSize /proc/$pid/status | awk '{print $2, $3}')
            local vm_rss=$(grep VmRSS /proc/$pid/status | awk '{print $2, $3}')
            
            echo "Memory details:"
            echo "  Peak virtual memory: $vm_peak"
            echo "  Current virtual memory: $vm_size"
            echo "  Resident set size: $vm_rss"
        fi
    else
        warning "Cannot get performance metrics - bot is not running"
    fi
}

# Main status check
main() {
    echo "=========================================="
    echo "Aviation Girl V4 Discord Bot - Status"
    echo "=========================================="
    echo
    
    local overall_status="OK"
    
    # Check process status
    if ! check_process_status; then
        overall_status="ERROR"
    fi
    echo
    
    # Check health endpoints (only if process is running)
    if [ "$overall_status" = "OK" ]; then
        check_health_endpoints
        echo
    fi
    
    # Check system resources
    check_system_resources
    echo
    
    # Check configuration
    check_configuration
    echo
    
    # Check external connections
    check_connections
    echo
    
    # Check logs
    check_logs
    echo
    
    # Show recent activity (only if process is running)
    if [ "$overall_status" = "OK" ]; then
        show_recent_activity
        echo
    fi
    
    # Overall status
    header "Overall Status"
    echo "=============="
    if [ "$overall_status" = "OK" ]; then
        success "Aviation Girl V4 is running normally"
    else
        error "Aviation Girl V4 has issues that need attention"
    fi
    
    echo
    echo "Useful commands:"
    echo "  - View live logs: tail -f $LOG_DIR/aviationgirl.log"
    echo "  - Restart bot: ./scripts/stop.sh && ./scripts/start.sh"
    echo "  - Health check: curl http://localhost:8081/health"
    echo "  - Metrics: curl http://localhost:8080/metrics"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --brief        Show brief status only"
        echo "  --performance  Show detailed performance metrics"
        echo "  --logs         Show recent log activity"
        echo
        echo "This script provides comprehensive status information about"
        echo "the Aviation Girl V4 Discord Bot."
        exit 0
        ;;
    --brief)
        check_process_status
        if [ $? -eq 0 ]; then
            check_health_endpoints
        fi
        ;;
    --performance)
        show_performance_metrics
        ;;
    --logs)
        show_recent_activity
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