#!/bin/bash
# Aviation Girl V4 Deployment Script

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="aviation-girl-v4"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ENVIRONMENT="${ENVIRONMENT:-production}"

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check if .env file exists
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        log_warning ".env file not found. Creating from template..."
        if [[ -f "$PROJECT_DIR/.env.example" ]]; then
            cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
            log_warning "Please edit .env file with your configuration before running again"
            exit 1
        else
            log_error ".env.example file not found"
            exit 1
        fi
    fi
    
    log_success "Prerequisites check passed"
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."
    
    cd "$PROJECT_DIR"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker build -f Dockerfile.dev -t "${IMAGE_NAME}:${IMAGE_TAG}-dev" .
        log_success "Development image built: ${IMAGE_NAME}:${IMAGE_TAG}-dev"
    else
        docker build -f Dockerfile -t "${IMAGE_NAME}:${IMAGE_TAG}" .
        log_success "Production image built: ${IMAGE_NAME}:${IMAGE_TAG}"
    fi
}

# Deploy with Docker Compose
deploy_docker_compose() {
    log_info "Deploying with Docker Compose..."
    
    cd "$PROJECT_DIR"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker-compose -f docker-compose.dev.yml up -d
        log_success "Development deployment started"
        log_info "Health check: http://localhost:8080/health"
        log_info "Metrics: http://localhost:8080/metrics"
    else
        docker-compose up -d
        log_success "Production deployment started"
        log_info "Health check: http://localhost:8080/health"
        log_info "Metrics: http://localhost:8080/metrics"
    fi
}

# Deploy to Kubernetes
deploy_kubernetes() {
    log_info "Deploying to Kubernetes..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    cd "$PROJECT_DIR"
    
    # Apply Kubernetes manifests
    log_info "Creating namespace..."
    kubectl apply -f k8s/namespace.yaml
    
    log_info "Creating persistent volume claims..."
    kubectl apply -f k8s/pvc.yaml
    
    log_info "Creating config map..."
    kubectl apply -f k8s/configmap.yaml
    
    log_info "Creating services..."
    kubectl apply -f k8s/service.yaml
    
    log_info "Creating deployment..."
    kubectl apply -f k8s/deployment.yaml
    
    log_success "Kubernetes deployment completed"
    log_info "Check status: kubectl get pods -n aviation-bot"
    log_info "View logs: kubectl logs -n aviation-bot -l app=aviation-girl-v4"
}

# Health check
health_check() {
    log_info "Performing health check..."
    
    local max_attempts=30
    local attempt=1
    local health_url="http://localhost:8080/health"
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s "$health_url" > /dev/null 2>&1; then
            log_success "Health check passed"
            return 0
        fi
        
        log_info "Health check attempt $attempt/$max_attempts failed, retrying in 10 seconds..."
        sleep 10
        ((attempt++))
    done
    
    log_error "Health check failed after $max_attempts attempts"
    return 1
}

# Show deployment status
show_status() {
    log_info "Deployment Status:"
    
    if [[ "$DEPLOYMENT_TYPE" == "kubernetes" ]]; then
        echo "Kubernetes Pods:"
        kubectl get pods -n aviation-bot -l app=aviation-girl-v4
        echo ""
        echo "Services:"
        kubectl get services -n aviation-bot
    else
        echo "Docker Containers:"
        docker-compose ps
    fi
    
    echo ""
    log_info "Health Check:"
    if curl -f -s "http://localhost:8080/health" | jq . 2>/dev/null; then
        log_success "Service is healthy"
    else
        log_warning "Service health check failed or service not ready"
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    
    if [[ "$DEPLOYMENT_TYPE" == "kubernetes" ]]; then
        kubectl delete -f k8s/ --ignore-not-found=true
        log_success "Kubernetes resources cleaned up"
    else
        if [[ "$ENVIRONMENT" == "development" ]]; then
            docker-compose -f docker-compose.dev.yml down -v
        else
            docker-compose down -v
        fi
        log_success "Docker Compose deployment cleaned up"
    fi
}

# Main deployment function
main() {
    local command="${1:-deploy}"
    
    case "$command" in
        "build")
            check_prerequisites
            build_image
            ;;
        "deploy")
            check_prerequisites
            build_image
            if [[ "$DEPLOYMENT_TYPE" == "kubernetes" ]]; then
                deploy_kubernetes
            else
                deploy_docker_compose
            fi
            health_check
            show_status
            ;;
        "status")
            show_status
            ;;
        "cleanup")
            cleanup
            ;;
        "health")
            health_check
            ;;
        *)
            echo "Usage: $0 {build|deploy|status|cleanup|health}"
            echo ""
            echo "Environment variables:"
            echo "  ENVIRONMENT=development|production (default: production)"
            echo "  DEPLOYMENT_TYPE=docker|kubernetes (default: docker)"
            echo "  IMAGE_TAG=tag (default: latest)"
            echo ""
            echo "Examples:"
            echo "  $0 build"
            echo "  ENVIRONMENT=development $0 deploy"
            echo "  DEPLOYMENT_TYPE=kubernetes $0 deploy"
            echo "  $0 status"
            echo "  $0 cleanup"
            exit 1
            ;;
    esac
}

# Set deployment type
DEPLOYMENT_TYPE="${DEPLOYMENT_TYPE:-docker}"

# Run main function
main "$@"