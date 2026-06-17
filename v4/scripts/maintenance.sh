#!/bin/bash

# Aviation Girl V4 Discord Bot - Maintenance Script
# Automated maintenance tasks including cleanup, backups, and updates

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
DATA_DIR="$PROJECT_DIR/data"
BACKUP_DIR="$PROJECT_DIR/backups"
MAINTENANCE_LOG="$LOG_DIR/maintenance.log"

# Maintenance configuration
BACKUP_RETENTION_DAYS=30
LOG_RETENTION_DAYS=90
DATA_CLEANUP_DAYS=180
BACKUP_COMPRESS=true

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
    echo "$message" >> "$MAINTENANCE_LOG"
}

error() {
    local message="[ERROR] $1"
    echo -e "${RED}$message${NC}" >&2
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$MAINTENANCE_LOG"
}

warning() {
    local message="[WARNING] $1"
    echo -e "${YELLOW}$message${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$MAINTENANCE_LOG"
}

success() {
    local message="[SUCCESS] $1"
    echo -e "${GREEN}$message${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$MAINTENANCE_LOG"
}

# Initialize maintenance
init_maintenance() {
    log "Initializing maintenance tasks..."
    
    # Create directories if they don't exist
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Initialize maintenance log
    echo "Aviation Girl V4 Maintenance Started - $(date)" >> "$MAINTENANCE_LOG"
    echo "=============================================" >> "$MAINTENANCE_LOG"
    
    success "Maintenance initialized"
}

# Check if bot is running
is_bot_running() {
    local pid_file="$PROJECT_DIR/aviationgirl.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    
    return 1
}

# Create backup
create_backup() {
    log "Creating backup..."
    
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_name="aviationgirl_backup_$timestamp"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    # Create backup directory
    mkdir -p "$backup_path"
    
    # Backup data directory
    if [ -d "$DATA_DIR" ]; then
        log "Backing up data directory..."
        cp -r "$DATA_DIR" "$backup_path/data"
        success "Data directory backed up"
    else
        warning "Data directory not found: $DATA_DIR"
    fi
    
    # Backup configuration files
    log "Backing up configuration files..."
    mkdir -p "$backup_path/config"
    
    if [ -f "$PROJECT_DIR/.env" ]; then
        cp "$PROJECT_DIR/.env" "$backup_path/config/"
    fi
    
    if [ -d "$PROJECT_DIR/config" ]; then
        cp -r "$PROJECT_DIR/config"/* "$backup_path/config/" 2>/dev/null || true
    fi
    
    # Backup recent logs
    log "Backing up recent logs..."
    mkdir -p "$backup_path/logs"
    
    if [ -d "$LOG_DIR" ]; then
        # Only backup logs from last 7 days
        find "$LOG_DIR" -name "*.log" -mtime -7 -exec cp {} "$backup_path/logs/" \; 2>/dev/null || true
    fi
    
    # Compress backup if enabled
    if [ "$BACKUP_COMPRESS" = true ]; then
        log "Compressing backup..."
        cd "$BACKUP_DIR"
        tar -czf "${backup_name}.tar.gz" "$backup_name"
        rm -rf "$backup_name"
        backup_path="${backup_path}.tar.gz"
        success "Backup compressed: $(basename "$backup_path")"
    else
        success "Backup created: $(basename "$backup_path")"
    fi
    
    # Calculate backup size
    local backup_size=$(du -h "$backup_path" | cut -f1)
    log "Backup size: $backup_size"
    
    return 0
}

# Clean old backups
cleanup_old_backups() {
    log "Cleaning up old backups..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        warning "Backup directory not found: $BACKUP_DIR"
        return 0
    fi
    
    local deleted_count=0
    
    # Find and delete old backups
    while IFS= read -r -d '' backup_file; do
        rm -rf "$backup_file"
        deleted_count=$((deleted_count + 1))
        log "Deleted old backup: $(basename "$backup_file")"
    done < <(find "$BACKUP_DIR" -name "aviationgirl_backup_*" -mtime +$BACKUP_RETENTION_DAYS -print0 2>/dev/null)
    
    if [ $deleted_count -gt 0 ]; then
        success "Deleted $deleted_count old backups"
    else
        log "No old backups to delete"
    fi
    
    return 0
}

# Clean old logs
cleanup_old_logs() {
    log "Cleaning up old logs..."
    
    if [ ! -d "$LOG_DIR" ]; then
        warning "Log directory not found: $LOG_DIR"
        return 0
    fi
    
    local deleted_count=0
    
    # Find and delete old log files
    while IFS= read -r -d '' log_file; do
        rm -f "$log_file"
        deleted_count=$((deleted_count + 1))
        log "Deleted old log: $(basename "$log_file")"
    done < <(find "$LOG_DIR" -name "*.log" -mtime +$LOG_RETENTION_DAYS -print0 2>/dev/null)
    
    # Clean up empty log directories
    find "$LOG_DIR" -type d -empty -delete 2>/dev/null || true
    
    if [ $deleted_count -gt 0 ]; then
        success "Deleted $deleted_count old log files"
    else
        log "No old logs to delete"
    fi
    
    return 0
}

# Clean old data
cleanup_old_data() {
    log "Cleaning up old data..."
    
    if [ ! -d "$DATA_DIR" ]; then
        warning "Data directory not found: $DATA_DIR"
        return 0
    fi
    
    # This is a placeholder for data cleanup logic
    # In a real implementation, you would:
    # 1. Clean old conversation data
    # 2. Clean old user profiles that haven't been accessed
    # 3. Clean temporary files
    # 4. Optimize database files
    
    log "Data cleanup completed (placeholder - implement specific cleanup logic)"
    
    return 0
}

# Update dependencies
update_dependencies() {
    log "Updating dependencies..."
    
    local venv_path="$PROJECT_DIR/venv"
    
    if [ ! -d "$venv_path" ]; then
        error "Virtual environment not found: $venv_path"
        return 1
    fi
    
    # Activate virtual environment
    source "$venv_path/bin/activate"
    
    # Update pip
    log "Updating pip..."
    pip install --upgrade pip
    
    # Update dependencies
    log "Updating Python packages..."
    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        pip install --upgrade -r "$PROJECT_DIR/requirements.txt"
        success "Dependencies updated"
    else
        warning "requirements.txt not found"
    fi
    
    # Deactivate virtual environment
    deactivate
    
    return 0
}

# Check system health
check_system_health() {
    log "Checking system health..."
    
    local issues=0
    
    # Check disk space
    local disk_usage=$(df "$PROJECT_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 85 ]; then
        warning "High disk usage: ${disk_usage}%"
        issues=$((issues + 1))
    else
        log "Disk usage: ${disk_usage}%"
    fi
    
    # Check memory usage
    local memory_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [ "$memory_usage" -gt 85 ]; then
        warning "High memory usage: ${memory_usage}%"
        issues=$((issues + 1))
    else
        log "Memory usage: ${memory_usage}%"
    fi
    
    # Check log file sizes
    if [ -d "$LOG_DIR" ]; then
        local large_logs=$(find "$LOG_DIR" -name "*.log" -size +100M 2>/dev/null | wc -l)
        if [ "$large_logs" -gt 0 ]; then
            warning "Found $large_logs large log files (>100MB)"
            issues=$((issues + 1))
        fi
    fi
    
    # Check backup directory size
    if [ -d "$BACKUP_DIR" ]; then
        local backup_size_mb=$(du -sm "$BACKUP_DIR" 2>/dev/null | cut -f1)
        if [ "$backup_size_mb" -gt 1000 ]; then  # More than 1GB
            warning "Backup directory is large: ${backup_size_mb}MB"
            issues=$((issues + 1))
        fi
    fi
    
    if [ $issues -eq 0 ]; then
        success "System health check passed"
    else
        warning "System health check found $issues issues"
    fi
    
    return $issues
}

# Optimize system
optimize_system() {
    log "Optimizing system..."
    
    # Clear Python cache files
    log "Clearing Python cache files..."
    find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Clear temporary files
    log "Clearing temporary files..."
    find "$PROJECT_DIR" -name "*.tmp" -delete 2>/dev/null || true
    find "$PROJECT_DIR" -name ".DS_Store" -delete 2>/dev/null || true
    
    # Rotate large log files
    if [ -d "$LOG_DIR" ]; then
        log "Rotating large log files..."
        find "$LOG_DIR" -name "*.log" -size +50M -exec gzip {} \; 2>/dev/null || true
    fi
    
    success "System optimization completed"
    
    return 0
}

# Generate maintenance report
generate_report() {
    log "Generating maintenance report..."
    
    local report_file="$LOG_DIR/maintenance_report_$(date '+%Y%m%d_%H%M%S').txt"
    
    {
        echo "Aviation Girl V4 Maintenance Report"
        echo "Generated: $(date)"
        echo "========================================"
        echo
        
        echo "System Information:"
        echo "- Uptime: $(uptime)"
        echo "- Disk usage: $(df -h "$PROJECT_DIR" | tail -1)"
        echo "- Memory usage: $(free -h | grep Mem)"
        echo
        
        echo "Bot Status:"
        if is_bot_running; then
            echo "- Status: Running"
            local pid_file="$PROJECT_DIR/aviationgirl.pid"
            local pid=$(cat "$pid_file")
            echo "- PID: $pid"
            echo "- Memory: $(ps -p "$pid" -o rss= | awk '{printf "%.1f MB", $1/1024}')"
        else
            echo "- Status: Not running"
        fi
        echo
        
        echo "Directory Sizes:"
        if [ -d "$LOG_DIR" ]; then
            echo "- Logs: $(du -sh "$LOG_DIR" | cut -f1)"
        fi
        if [ -d "$DATA_DIR" ]; then
            echo "- Data: $(du -sh "$DATA_DIR" | cut -f1)"
        fi
        if [ -d "$BACKUP_DIR" ]; then
            echo "- Backups: $(du -sh "$BACKUP_DIR" | cut -f1)"
        fi
        echo
        
        echo "Recent Maintenance Activities:"
        tail -n 20 "$MAINTENANCE_LOG" 2>/dev/null || echo "No recent activities"
        
    } > "$report_file"
    
    success "Maintenance report generated: $(basename "$report_file")"
    
    return 0
}

# Full maintenance routine
full_maintenance() {
    log "Starting full maintenance routine..."
    
    local bot_was_running=false
    
    # Check if bot is running
    if is_bot_running; then
        bot_was_running=true
        log "Bot is currently running"
    fi
    
    # Create backup
    if ! create_backup; then
        error "Backup creation failed"
        return 1
    fi
    
    # Clean up old files
    cleanup_old_backups
    cleanup_old_logs
    cleanup_old_data
    
    # System optimization
    optimize_system
    
    # Check system health
    check_system_health
    
    # Update dependencies (only if bot is not running)
    if [ "$bot_was_running" = false ]; then
        log "Bot is not running, updating dependencies..."
        update_dependencies
    else
        log "Skipping dependency update (bot is running)"
    fi
    
    # Generate report
    generate_report
    
    success "Full maintenance routine completed"
    
    return 0
}

# Quick maintenance routine
quick_maintenance() {
    log "Starting quick maintenance routine..."
    
    # Clean up old files
    cleanup_old_backups
    cleanup_old_logs
    
    # System optimization
    optimize_system
    
    # Check system health
    check_system_health
    
    success "Quick maintenance routine completed"
    
    return 0
}

# Main execution
main() {
    echo "=========================================="
    echo "Aviation Girl V4 Discord Bot - Maintenance"
    echo "=========================================="
    echo
    
    init_maintenance
    full_maintenance
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --quick        Run quick maintenance (no backup, no updates)"
        echo "  --backup-only  Create backup only"
        echo "  --cleanup-only Clean up old files only"
        echo "  --update-only  Update dependencies only"
        echo "  --report-only  Generate maintenance report only"
        echo "  --config       Show maintenance configuration"
        echo
        echo "This script performs automated maintenance tasks for the"
        echo "Aviation Girl V4 Discord Bot including backups, cleanup,"
        echo "and system optimization."
        exit 0
        ;;
    --quick)
        init_maintenance
        quick_maintenance
        ;;
    --backup-only)
        init_maintenance
        create_backup
        ;;
    --cleanup-only)
        init_maintenance
        cleanup_old_backups
        cleanup_old_logs
        cleanup_old_data
        ;;
    --update-only)
        init_maintenance
        update_dependencies
        ;;
    --report-only)
        init_maintenance
        generate_report
        ;;
    --config)
        echo "Current maintenance configuration:"
        echo "  Backup retention: $BACKUP_RETENTION_DAYS days"
        echo "  Log retention: $LOG_RETENTION_DAYS days"
        echo "  Data cleanup: $DATA_CLEANUP_DAYS days"
        echo "  Backup compression: $BACKUP_COMPRESS"
        echo "  Backup directory: $BACKUP_DIR"
        echo "  Log directory: $LOG_DIR"
        echo "  Data directory: $DATA_DIR"
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