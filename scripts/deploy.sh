#!/bin/bash
set -e

# =============================================================================
# Blue-Green Deployment Script for Logit Server
#
# Usage:
#   ./scripts/deploy.sh         # Deploy with blue-green swap
#   ./scripts/deploy.sh init    # First-time setup (starts blue)
# =============================================================================

COMPOSE_FILE="docker-compose.prod.yml"
CADDYFILE="Caddyfile.prod"
STATE_FILE=".active-color"
HEALTH_CHECK_RETRIES=30
HEALTH_CHECK_INTERVAL=5
DRAIN_WAIT=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

get_active_color() {
    if [ -f "$STATE_FILE" ]; then
        cat "$STATE_FILE"
    else
        echo "blue"
    fi
}

get_inactive_color() {
    local active
    active=$(get_active_color)
    if [ "$active" = "blue" ]; then
        echo "green"
    else
        echo "blue"
    fi
}

wait_for_healthy() {
    local service=$1
    local retries=$HEALTH_CHECK_RETRIES
    local interval=$HEALTH_CHECK_INTERVAL

    log_info "Waiting for $service to become healthy..."

    for i in $(seq 1 "$retries"); do
        local health
        health=$(docker inspect --format='{{.State.Health.Status}}' "logit-app-${service}" 2>/dev/null || echo "not_found")

        if [ "$health" = "healthy" ]; then
            log_success "$service is healthy!"
            return 0
        fi

        echo "  Attempt $i/$retries - status: $health"
        sleep "$interval"
    done

    log_error "$service failed to become healthy after $((retries * interval)) seconds"
    return 1
}

update_caddyfile() {
    local target=$1
    log_info "Updating Caddyfile to point to app-${target}..."

    cat > "$CADDYFILE" << EOF
# Caddyfile for Production Server (Blue-Green Deployment)
# Active upstream: app-${target}

{\$DOMAIN:api.logit.ai.kr} {
    # Reverse proxy to active app
    reverse_proxy app-${target}:8000

    # Enable compression
    encode gzip

    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
    }

    # Logging
    log {
        output stdout
        format console
    }
}

# Health check endpoint (for load balancer)
:80 {
    respond /health "OK" 200
}
EOF

    log_success "Caddyfile updated to app-${target}"
}

reload_caddy() {
    log_info "Reloading Caddy configuration..."
    docker compose -f "$COMPOSE_FILE" exec caddy caddy reload --config /etc/caddy/Caddyfile
    log_success "Caddy reloaded"
}

# =============================================================================
# Init: First-time deployment
# =============================================================================
init_deploy() {
    log_info "=== Initial Production Deployment ==="

    # Build image
    log_info "Building Docker image..."
    docker compose -f "$COMPOSE_FILE" build

    # Update Caddyfile to blue
    update_caddyfile "blue"

    # Start infrastructure + blue + caddy
    log_info "Starting infrastructure services..."
    docker compose -f "$COMPOSE_FILE" up -d postgres redis qdrant
    sleep 5

    log_info "Starting app-blue..."
    docker compose -f "$COMPOSE_FILE" up -d app-blue

    wait_for_healthy "blue"

    log_info "Starting Caddy..."
    docker compose -f "$COMPOSE_FILE" up -d caddy

    # Save state
    echo "blue" > "$STATE_FILE"

    log_success "=== Initial deployment complete! Active: blue ==="
}

# =============================================================================
# Deploy: Blue-Green swap
# =============================================================================
deploy() {
    local active
    local target
    active=$(get_active_color)
    target=$(get_inactive_color)

    log_info "=== Blue-Green Deployment ==="
    log_info "Active: ${active} -> Target: ${target}"

    # Build new image
    log_info "Building Docker image..."
    docker compose -f "$COMPOSE_FILE" build

    # Start the new target
    log_info "Starting app-${target}..."
    docker compose -f "$COMPOSE_FILE" up -d "app-${target}"

    # Wait for health check
    if ! wait_for_healthy "$target"; then
        log_error "Deployment failed! Rolling back..."
        docker compose -f "$COMPOSE_FILE" stop "app-${target}"
        log_error "app-${target} stopped. Active remains: ${active}"
        exit 1
    fi

    # Switch Caddy to new target
    update_caddyfile "$target"
    reload_caddy

    # Wait for existing connections to drain
    log_info "Waiting ${DRAIN_WAIT}s for connections to drain..."
    sleep "$DRAIN_WAIT"

    # Stop old app
    log_info "Stopping app-${active}..."
    docker compose -f "$COMPOSE_FILE" stop "app-${active}"

    # Save new state
    echo "$target" > "$STATE_FILE"

    log_success "=== Deployment complete! Active: ${target} ==="
}

# =============================================================================
# Rollback: Switch back to previous color
# =============================================================================
rollback() {
    local active
    local target
    active=$(get_active_color)
    target=$(get_inactive_color)

    log_warn "=== Rollback: ${active} -> ${target} ==="

    # Start the old (rollback target)
    log_info "Starting app-${target}..."
    docker compose -f "$COMPOSE_FILE" up -d "app-${target}"

    wait_for_healthy "$target"

    # Switch Caddy
    update_caddyfile "$target"
    reload_caddy

    sleep "$DRAIN_WAIT"

    # Stop current
    log_info "Stopping app-${active}..."
    docker compose -f "$COMPOSE_FILE" stop "app-${active}"

    echo "$target" > "$STATE_FILE"

    log_success "=== Rollback complete! Active: ${target} ==="
}

# =============================================================================
# Status
# =============================================================================
show_status() {
    local active
    active=$(get_active_color)
    echo ""
    log_info "=== Deployment Status ==="
    echo "  Active color: ${active}"
    echo ""

    local blue_status green_status
    blue_status=$(docker inspect --format='{{.State.Status}}' logit-app-blue 2>/dev/null || echo "not running")
    green_status=$(docker inspect --format='{{.State.Status}}' logit-app-green 2>/dev/null || echo "not running")

    echo "  app-blue:  ${blue_status}"
    echo "  app-green: ${green_status}"
    echo ""
}

# =============================================================================
# Main
# =============================================================================
case "${1:-deploy}" in
    init)
        init_deploy
        ;;
    deploy)
        deploy
        ;;
    rollback)
        rollback
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {init|deploy|rollback|status}"
        echo ""
        echo "  init      First-time setup (starts blue)"
        echo "  deploy    Blue-green deployment (default)"
        echo "  rollback  Switch back to previous color"
        echo "  status    Show current deployment status"
        exit 1
        ;;
esac
