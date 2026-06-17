#!/bin/bash

# Aviation Girl V4 Discord Bot - Monitoring Script
# Continuous monitoring with alerting and automatic recovery

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/aviationgirl.pid"
LOG_DIR="$PROJECT_DIR/logs"
MONITOR_LOG="$LOG_DIR/monitor.log"

# Monitoring configuration
CHECK_INTERVAL=30  # seconds
HEALTH_CHECK_URL="http://localhost:8081/health"
METRICS_URL="http://localhost:8080/metrics"
MAX_MEMORY_PERCENT=85
MAX_CPU_PERCENT=80
MAX_RESPONSE_TIME=5000  # milliseconds
RESTART_THRESHOLD=3  # consecutive failures before restart

# Alert configuration
ENABLE_ALERTS=true
ALERT_EMAIL=""  # Set email for alerts
WEBHOOK_URL=""  # Set webhook URL for alerts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${BLUE}$message${NC}"
    echo "$message" >> "$MONITOR_LOG"
}

error() {
    local message="[ERROR] $1"
    echo -e "${RED}$message${NC}" >&2
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$MONITOR_LOG"
}

warning() {
    local message="[WARNING] $1"
    echo -e "${YELLOW}$message${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$MONITOR_LOG"
}

success() {
    local message="[SUCCESS] $1"
    echo -e "${GREEN}$message${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$MONITOR_LOG"
}

# Initialize monitoring
init_monitoring() {
    log "Initializing Aviation Girl V4 monitoring..."
    
    # Create log directory if it doesn't exist
    mkdir -p "$LOG_DIR"
    
    # Initialize monitor log
    echo "Aviation Girl V4 Monitoring Started - $(date)" >> "$MONITOR_LOG"
    echo "=========================================" >> "$MONITOR_LOG"
    
    success "Monitoring initialized"
}

# Check if bot process is running
check_process() {
    if [ ! -f "$PID_FILE" ]; then
        return 1
    fi
    
    local pid=$(cat "$PID_FILE")
    if ps -p "$pid" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check health endpoint
check_health_endpoint() {
    local response=$(curl -s --max-time 10 -w "%{http_code}:%{time_total}" "$HEALTH_CHECK_URL" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        local http_code=$(echo "$response" | cut -d':' -f1)
        local response_time=$(echo "$response" | cut -d':' -f2)
        
        if [ "$http_code" = "200" ]; then
            # Convert response time to milliseconds
            local response_time_ms=$(echo "$response_time * 1000" | bc -l | cut -d'.' -f1)
            
            if [ "$response_time_ms" -gt "$MAX_RESPONSE_TIME" ]; then
                warning "Health endpoint slow response: ${response_time_ms}ms"
                return 2  # Slow response
            else
                return 0  # Healthy
            fi
        else
            error "Health endpoint returned HTTP $http_code"
            return 1  # Unhealthy
        fi
    else
        error "Health endpoint not responding"
        return 1  # Unreachable
    fi
}

# Check system resources
check_system_resources() {
    local issues=0
    
    # Check memory usage
    local memory_percent=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [ "$memory_percent" -gt "$MAX_MEMORY_PERCENT" ]; then
        warning "High memory usage: ${memory_percent}%"
        issues=$((issues + 1))
    fi
    
    # Check CPU usage
    local cpu_percent=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    local cpu_int=$(echo "$cpu_percent" | cut -d'.' -f1)
    if [ "$cpu_int" -gt "$MAX_CPU_PERCENT" ]; then
        warning "High CPU usage: ${cpu_percent}%"
        issues=$((issues + 1))
    fi
    
    # Check disk space
    local disk_percent=$(df "$PROJECT_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_percent" -gt 90 ]; then
        warning "High disk usage: ${disk_percent}%"
        issues=$((issues + 1))
    fi
    
    return $issues
}

# Check bot-specific metrics
check_bot_metrics() {
    local metrics_response=$(curl -s --max-time 5 "$METRICS_URL" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Parse metrics for issues
        local error_count=$(echo "$metrics_response" | grep "aviationgirl_errors_total" | awk '{print $2}')
        local request_count=$(echo "$metrics_response" | grep "aviationgirl_requests_total" | awk '{print $2}')
        
        if [ -n "$error_count" ] && [ -n "$request_count" ] && [ "$request_count" -gt 0 ]; then
            local error_rate=$(echo "scale=2; $error_count / $request_count * 100" | bc -l)
            local error_rate_int=$(echo "$error_rate" | cut -d'.' -f1)
            
            if [ "$error_rate_int" -gt 10 ]; then  # More than 10% error rate
                warning "High error rate: ${error_rate}%"
                return 1
            fi
        fi
        
        return 0
    else
        warning "Could not retrieve bot metrics"
        return 1
    fi
}

# Send alert
send_alert() {
    local alert_type="$1"
    local message="$2"
    
    if [ "$ENABLE_ALERTS" != "true" ]; then
        return
    fi
    
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local alert_message="[ALERT] Aviation Girl V4 - $alert_type at $timestamp: $message"
    
    # Send email alert if configured
    if [ -n "$ALERT_EMAIL" ] && command -v mail >/dev/null 2>&1; then
        echo "$alert_message" | mail -s "Aviation Girl V4 Alert: $alert_type" "$ALERT_EMAIL"
        log "Alert email sent to $ALERT_EMAIL"
    fi
    
    # Send webhook alert if configured
    if [ -n "$WEBHOOK_URL" ] && command -v curl >/dev/null 2>&1; then
        curl -s -X POST -H "Content-Type: application/json" \
            -d "{\"text\":\"$alert_message\"}" \
            "$WEBHOOK_URL" >/dev/null 2>&1
        log "Alert webhook sent"
    fi
    
    # Log alert
    error "ALERT: $alert_type - $message"
}

# Attempt automatic recovery
attempt_recovery() {
    local issue="$1"
    
    log "Attempting automatic recovery for: $issue"
    
    case "$issue" in
        "process_dead")
            log "Restarting bot process..."
            if "$SCRIPT_DIR/start.sh" --no-checks; then
                success "Bot restarted successfully"
                send_alert "RECOVERY" "Bot process restarted successfully"
                return 0
            else
                error "Failed to restart bot process"
                send_alert "RECOVERY_FAILED" "Failed to restart bot process"
                return 1
            fi
            ;;
        "health_check_failed")
            log "Restarting bot due to health check failure..."
            "$SCRIPT_DIR/stop.sh" --force
            sleep 5
            if "$SCRIPT_DIR/start.sh" --no-checks; then
                success "Bot restarted after health check failure"
                send_alert "RECOVERY" "Bot restarted after health check failure"
                return 0
            else
                error "Failed to restart bot after health check failure"
                send_alert "RECOVERY_FAILED" "Failed to restart bot after health check failure"
                return 1
            fi
            ;;
        "high_resource_usage")
            log "Restarting bot due to high resource usage..."
            "$SCRIPT_DIR/stop.sh"
            sleep 10  # Give more time for cleanup
            if "$SCRIPT_DIR/start.sh" --no-checks; then
                success "Bot restarted due to high resource usage"
                send_alert "RECOVERY" "Bot restarted due to high resource usage"
                return 0
            else
                error "Failed to restart bot due to high resource usage"
                send_alert "RECOVERY_FAILED" "Failed to restart bot due to high resource usage"
                return 1
            fi
            ;;
        *)
            warning "No automatic recovery available for: $issue"
            return 1
            ;;
    esac
}

# Main monitoring loop
monitor_loop() {
    local consecutive_failures=0
    local last_alert_time=0
    local alert_cooldown=300  # 5 minutes between similar alerts
    
    log "Starting monitoring loop (check interval: ${CHECK_INTERVAL}s)"
    
    while true; do
        local current_time=$(date +%s)
        local issues_found=false
        
        # Check if process is running
        if ! check_process; then
            error "Bot process is not running"
            consecutive_failures=$((consecutive_failures + 1))
            issues_found=true
            
            if [ $consecutive_failures -ge $RESTART_THRESHOLD ]; then
                if [ $((current_time - last_alert_time)) -gt $alert_cooldown ]; then
                    send_alert "PROCESS_DOWN" "Bot process is not running"
                    last_alert_time=$current_time
                fi
                
                if attempt_recovery "process_dead"; then
                    consecutive_failures=0
                fi
            fi
        else
            # Process is running, check health endpoint
            local health_status
            check_health_endpoint
            health_status=$?
            
            if [ $health_status -ne 0 ]; then
                if [ $health_status -eq 1 ]; then
                    error "Health check failed"
                elif [ $health_status -eq 2 ]; then
                    warning "Health check slow"
                fi
                
                consecutive_failures=$((consecutive_failures + 1))
                issues_found=true
                
                if [ $consecutive_failures -ge $RESTART_THRESHOLD ]; then
                    if [ $((current_time - last_alert_time)) -gt $alert_cooldown ]; then
                        send_alert "HEALTH_CHECK_FAILED" "Health check failing consistently"
                        last_alert_time=$current_time
                    fi
                    
                    if attempt_recovery "health_check_failed"; then
                        consecutive_failures=0
                    fi
                fi
            else
                # Health check passed, check system resources
                local resource_issues
                check_system_resources
                resource_issues=$?
                
                if [ $resource_issues -gt 0 ]; then
                    warning "System resource issues detected"
                    
                    if [ $resource_issues -gt 2 ]; then  # Multiple resource issues
                        consecutive_failures=$((consecutive_failures + 1))
                        issues_found=true
                        
                        if [ $consecutive_failures -ge $RESTART_THRESHOLD ]; then
                            if [ $((current_time - last_alert_time)) -gt $alert_cooldown ]; then
                                send_alert "HIGH_RESOURCE_USAGE" "Multiple system resource issues"
                                last_alert_time=$current_time
                            fi
                            
                            if attempt_recovery "high_resource_usage"; then
                                consecutive_failures=0
                            fi
                        fi
                    fi
                else
                    # Check bot-specific metrics
                    if ! check_bot_metrics; then
                        warning "Bot metrics indicate issues"
                        consecutive_failures=$((consecutive_failures + 1))
                        issues_found=true
                    else
                        # All checks passed
                        if [ $consecutive_failures -gt 0 ]; then
                            success "All checks passed - system recovered"
                            consecutive_failures=0
                        fi
                    fi
                fi
            fi
        fi
        
        # Log status every 10 minutes if no issues
        if [ ! "$issues_found" = true ] && [ $((current_time % 600)) -eq 0 ]; then
            log "Monitoring status: All systems healthy"
        fi
        
        # Sleep until next check
        sleep $CHECK_INTERVAL
    done
}

# Cleanup function
cleanup() {
    log "Monitoring stopped"
    exit 0
}

# Signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    echo "=========================================="
    echo "Aviation Girl V4 Discord Bot - Monitor"
    echo "=========================================="
    echo
    
    init_monitoring
    monitor_loop
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --config       Show current monitoring configuration"
        echo "  --test         Run a single monitoring check"
        echo
        echo "This script continuously monitors the Aviation Girl V4 Discord Bot"
        echo "and performs automatic recovery when issues are detected."
        echo
        echo "Configuration:"
        echo "  Check interval: ${CHECK_INTERVAL}s"
        echo "  Health check URL: $HEALTH_CHECK_URL"
        echo "  Restart threshold: $RESTART_THRESHOLD failures"
        echo "  Max memory: ${MAX_MEMORY_PERCENT}%"
        echo "  Max CPU: ${MAX_CPU_PERCENT}%"
        exit 0
        ;;
    --config)
        echo "Current monitoring configuration:"
        echo "  Check interval: ${CHECK_INTERVAL}s"
        echo "  Health check URL: $HEALTH_CHECK_URL"
        echo "  Metrics URL: $METRICS_URL"
        echo "  Restart threshold: $RESTART_THRESHOLD failures"
        echo "  Max memory: ${MAX_MEMORY_PERCENT}%"
        echo "  Max CPU: ${MAX_CPU_PERCENT}%"
        echo "  Max response time: ${MAX_RESPONSE_TIME}ms"
        echo "  Alerts enabled: $ENABLE_ALERTS"
        echo "  Alert email: ${ALERT_EMAIL:-'Not configured'}"
        echo "  Webhook URL: ${WEBHOOK_URL:-'Not configured'}"
        exit 0
        ;;
    --test)
        log "Running single monitoring check..."
        init_monitoring
        
        if check_process; then
            success "Process check: PASSED"
        else
            error "Process check: FAILED"
        fi
        
        check_health_endpoint
        case $? in
            0) success "Health check: PASSED" ;;
            1) error "Health check: FAILED" ;;
            2) warning "Health check: SLOW" ;;
        esac
        
        check_system_resources
        local resource_issues=$?
        if [ $resource_issues -eq 0 ]; then
            success "Resource check: PASSED"
        else
            warning "Resource check: $resource_issues issues found"
        fi
        
        if check_bot_metrics; then
            success "Metrics check: PASSED"
        else
            warning "Metrics check: ISSUES DETECTED"
        fi
        
        exit 0
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