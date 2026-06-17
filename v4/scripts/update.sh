#!/bin/bash
# Aviation Girl V4 Update Script with Zero-Downtime Deployment

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="aviation-girl-v4"
NEW_IMAGE_TAG="${NEW_IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"
ENVIRONMENT="${ENVIRONMENT:-production}"
DEPLOYMENT_TYPE="${DEPLOYMENT_TYPE:-docker}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Backup current deployment
backup_deployment() {
    log_info "Creating deployment backup..."
    
    local backup_dir="$PROJECT_DIR/backups/$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    
    # Backup configuration
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        cp "$PROJECT_DIR/.env" "$backup_dir/"
    fi
    
    if [[ -f "$PROJECT_DIR/docker-compose.yml" ]]; then
        cp "$PROJECT_DIR/docker-compose.yml" "$backup_dir/"
    fi
    
    # Backup data (if using Docker volumes)
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        log_info "Backing up Docker volumes..."
        docker run --rm -v aviation_data:/data -v "$backup_dir":/backup alpine tar czf /backup/data.tar.gz -C /data .
        docker run --rm -v aviation_logs:/logs -v "$backup_dir":/backup alpine tar czf /backup/logs.tar.gz -C /logs .
    fi
    
    log_success "Backup created at: $backup_dir"
    echo "$backup_dir" > "$PROJECT_DIR/.last_backup"
}

# Prepare for update
prepare_update() {
    log_info "Preparing for update..."
    
    # Check if service is running
    if ! curl -f -s "http://localhost:8080/health" > /dev/null 2>&1; then
        log_warning "Service is not responding to health checks"
    fi
    
    # Trigger graceful preparation in the application
    log_info "Notifying application about upcoming update..."
    curl -X POST -f -s "http://localhost:8080/prepare-update" > /dev/null 2>&1 || log_warning "Could not notify application about update"
    
    # Wait for application to prepare
    sleep 10
    
    log_success "Update preparation completed"
}

# Build new image
build_new_image() {
    log_info "Building new image with tag: $NEW_IMAGE_TAG"
    
    cd "$PROJECT_DIR"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker build -f Dockerfile.dev -t "${IMAGE_NAME}:${NEW_IMAGE_TAG}-dev" .
        log_success "New development image built: ${IMAGE_NAME}:${NEW_IMAGE_TAG}-dev"
    else
        docker build -f Dockerfile -t "${IMAGE_NAME}:${NEW_IMAGE_TAG}" .
        log_success "New production image built: ${IMAGE_NAME}:${NEW_IMAGE_TAG}"
    fi
}

# Rolling update for Docker Compose
rolling_update_docker() {
    log_info "Performing rolling update with Docker Compose..."
    
    cd "$PROJECT_DIR"
    
    # Update image tag in docker-compose file
    local compose_file="docker-compose.yml"
    if [[ "$ENVIRONMENT" == "development" ]]; then
        compose_file="docker-compose.dev.yml"
    fi
    
    # Create temporary compose file with new image
    local temp_compose="/tmp/docker-compose-update.yml"
    sed "s|image: ${IMAGE_NAME}:.*|image: ${IMAGE_NAME}:${NEW_IMAGE_TAG}|g" "$compose_file" > "$temp_compose"
    
    # Perform rolling update
    log_info "Starting new container..."
    docker-compose -f "$temp_compose" up -d --no-deps aviation-bot
    
    # Wait for new container to be healthy
    log_info "Waiting for new container to be healthy..."
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s "http://localhost:8080/health" > /dev/null 2>&1; then
            log_success "New container is healthy"
            break
        fi
        
        log_info "Health check attempt $attempt/$max_attempts, waiting..."
        sleep 10
        ((attempt++))
        
        if [[ $attempt -gt $max_attempts ]]; then
            log_error "New container failed to become healthy"
            rollback_docker
            exit 1
        fi
    done
    
    # Clean up old containers
    log_info "Cleaning up old containers..."
    docker system prune -f
    
    # Update the original compose file
    cp "$temp_compose" "$compose_file"
    rm "$temp_compose"
    
    log_success "Rolling update completed successfully"
}

# Rolling update for Kubernetes
rolling_update_kubernetes() {
    log_info "Performing rolling update in Kubernetes..."
    
    # Update deployment with new image
    kubectl set image deployment/aviation-girl-v4 aviation-bot="${IMAGE_NAME}:${NEW_IMAGE_TAG}" -n aviation-bot
    
    # Wait for rollout to complete
    log_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/aviation-girl-v4 -n aviation-bot --timeout=300s
    
    if [[ $? -eq 0 ]]; then
        log_success "Kubernetes rolling update completed successfully"
    else
        log_error "Kubernetes rolling update failed"
        rollback_kubernetes
        exit 1
    fi
}

# Rollback Docker deployment
rollback_docker() {
    log_warning "Rolling back Docker deployment..."
    
    # Get previous image tag
    local previous_image=$(docker images "${IMAGE_NAME}" --format "table {{.Tag}}" | grep -v TAG | grep -v "$NEW_IMAGE_TAG" | head -1)
    
    if [[ -n "$previous_image" ]]; then
        log_info "Rolling back to image: ${IMAGE_NAME}:${previous_image}"
        
        # Update compose file with previous image
        local compose_file="docker-compose.yml"
        if [[ "$ENVIRONMENT" == "development" ]]; then
            compose_file="docker-compose.dev.yml"
        fi
        
        sed -i "s|image: ${IMAGE_NAME}:.*|image: ${IMAGE_NAME}:${previous_image}|g" "$compose_file"
        docker-compose up -d --no-deps aviation-bot
        
        log_success "Rollback completed"
    else
        log_error "No previous image found for rollback"
    fi
}

# Rollback Kubernetes deployment
rollback_kubernetes() {
    log_warning "Rolling back Kubernetes deployment..."
    
    kubectl rollout undo deployment/aviation-girl-v4 -n aviation-bot
    kubectl rollout status deployment/aviation-girl-v4 -n aviation-bot --timeout=300s
    
    log_success "Kubernetes rollback completed"
}

# Verify update
verify_update() {
    log_info "Verifying update..."
    
    # Health check
    if ! curl -f -s "http://localhost:8080/health" > /dev/null 2>&1; then
        log_error "Health check failed after update"
        return 1
    fi
    
    # Check version endpoint
    local version_info=$(curl -s "http://localhost:8080/metrics" | jq -r '.version' 2>/dev/null || echo "unknown")
    log_info "Current version: $version_info"
    
    # Basic functionality test
    log_info "Running basic functionality tests..."
    
    # Test metrics endpoint
    if curl -f -s "http://localhost:8080/metrics" > /dev/null 2>&1; then
        log_success "Metrics endpoint is working"
    else
        log_warning "Metrics endpoint is not responding"
    fi
    
    # Test readiness endpoint
    if curl -f -s "http://localhost:8080/ready" > /dev/null 2>&1; then
        log_success "Readiness endpoint is working"
    else
        log_warning "Readiness endpoint is not responding"
    fi
    
    log_success "Update verification completed"
}

# Cleanup old images
cleanup_old_images() {
    log_info "Cleaning up old images..."
    
    # Keep last 3 images
    local old_images=$(docker images "${IMAGE_NAME}" --format "table {{.Tag}}" | grep -v TAG | tail -n +4)
    
    if [[ -n "$old_images" ]]; then
        for tag in $old_images; do
            log_info "Removing old image: ${IMAGE_NAME}:${tag}"
            docker rmi "${IMAGE_NAME}:${tag}" || log_warning "Failed to remove ${IMAGE_NAME}:${tag}"
        done
    fi
    
    # Clean up dangling images
    docker image prune -f
    
    log_success "Image cleanup completed"
}

# Main update function
main() {
    local command="${1:-update}"
    
    case "$command" in
        "update")
            log_info "Starting zero-downtime update process..."
            backup_deployment
            prepare_update
            build_new_image
            
            if [[ "$DEPLOYMENT_TYPE" == "kubernetes" ]]; then
                rolling_update_kubernetes
            else
                rolling_update_docker
            fi
            
            verify_update
            cleanup_old_images
            log_success "Update process completed successfully!"
            ;;
        "rollback")
            log_info "Starting rollback process..."
            if [[ "$DEPLOYMENT_TYPE" == "kubernetes" ]]; then
                rollback_kubernetes
            else
                rollback_docker
            fi
            verify_update
            log_success "Rollback completed successfully!"
            ;;
        "verify")
            verify_update
            ;;
        "cleanup")
            cleanup_old_images
            ;;
        *)
            echo "Usage: $0 {update|rollback|verify|cleanup}"
            echo ""
            echo "Environment variables:"
            echo "  ENVIRONMENT=development|production (default: production)"
            echo "  DEPLOYMENT_TYPE=docker|kubernetes (default: docker)"
            echo "  NEW_IMAGE_TAG=tag (default: timestamp)"
            echo ""
            echo "Examples:"
            echo "  $0 update"
            echo "  DEPLOYMENT_TYPE=kubernetes $0 update"
            echo "  $0 rollback"
            echo "  $0 verify"
            echo "  $0 cleanup"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"