# Aviation Girl V4 Discord Bot - Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the Aviation Girl V4 Discord Bot in various environments including development, staging, and production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Configuration](#configuration)
4. [Deployment Methods](#deployment-methods)
5. [Health Checks](#health-checks)
6. [Monitoring](#monitoring)
7. [Maintenance](#maintenance)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python**: 3.9 or higher
- **Memory**: Minimum 2GB RAM (4GB recommended for production)
- **Storage**: Minimum 5GB free space
- **Network**: Stable internet connection for Discord API and aviation data sources

### Required Services

- **Discord Bot Token**: Create a bot application at [Discord Developer Portal](https://discord.com/developers/applications)
- **Aviation Data APIs**: 
  - Weather API access (METAR/TAF data)
  - Flight tracking API (optional)
  - NOTAM data access (optional)

### Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Additional system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y python3-dev build-essential libssl-dev libffi-dev

# Additional system dependencies (CentOS/RHEL)
sudo yum install -y python3-devel gcc openssl-devel libffi-devel
```

## Environment Setup

### Development Environment

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd aviation-girl-v4
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup Environment Variables**
   ```bash
   cp v4/.env.example v4/.env
   # Edit v4/.env with your configuration
   ```

### Production Environment

1. **System User Setup**
   ```bash
   # Create dedicated user for the bot
   sudo useradd -r -s /bin/false aviationgirl
   sudo mkdir -p /opt/aviationgirl
   sudo chown aviationgirl:aviationgirl /opt/aviationgirl
   ```

2. **Application Setup**
   ```bash
   # Deploy application files
   sudo cp -r v4/ /opt/aviationgirl/
   sudo chown -R aviationgirl:aviationgirl /opt/aviationgirl
   
   # Create data directories
   sudo mkdir -p /var/lib/aviationgirl/{data,logs,keys}
   sudo chown -R aviationgirl:aviationgirl /var/lib/aviationgirl
   ```

3. **Python Environment**
   ```bash
   # Install Python dependencies in production environment
   cd /opt/aviationgirl
   sudo -u aviationgirl python -m venv venv
   sudo -u aviationgirl venv/bin/pip install -r requirements.txt
   ```

## Configuration

### Environment Variables

Create a `.env` file in the v4 directory with the following variables:

```bash
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_COMMAND_PREFIX=!
DISCORD_MAX_MESSAGE_LENGTH=2000

# AI Model Configuration
AI_MODEL_NAME=qwen2.5-7b-instruct
AI_MAX_TOKENS=2000
AI_TEMPERATURE=0.7
AI_MODEL_PATH=/path/to/model

# Data Storage Configuration
DATA_STORAGE_PATH=/var/lib/aviationgirl/data
KNOWLEDGE_BASE_PATH=/var/lib/aviationgirl/data/knowledge
USER_PROFILES_PATH=/var/lib/aviationgirl/data/profiles
LOGS_PATH=/var/lib/aviationgirl/logs

# Aviation APIs
WEATHER_API_KEY=your_weather_api_key
WEATHER_API_URL=https://api.weather.service/
FLIGHT_API_KEY=your_flight_api_key
FLIGHT_API_URL=https://api.flight.service/

# Security Configuration
ENCRYPTION_KEY=your_32_character_encryption_key_here
SECURE_STORAGE_PATH=/var/lib/aviationgirl/keys

# Performance Configuration
MAX_CONCURRENT_REQUESTS=50
REQUEST_TIMEOUT=30
RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Monitoring Configuration
ENABLE_METRICS=true
METRICS_PORT=8080
HEALTH_CHECK_PORT=8081
LOG_LEVEL=INFO

# Environment
ENVIRONMENT=production  # development, staging, production
DEBUG=false
```

### Configuration Files

#### Bot Configuration (v4/config/production.json)

```json
{
  "discord": {
    "token": "${DISCORD_TOKEN}",
    "command_prefix": "${DISCORD_COMMAND_PREFIX}",
    "max_message_length": 2000,
    "intents": {
      "message_content": true,
      "reactions": true,
      "guilds": true,
      "members": false
    }
  },
  "ai": {
    "model_name": "${AI_MODEL_NAME}",
    "model_path": "${AI_MODEL_PATH}",
    "max_tokens": 2000,
    "temperature": 0.7,
    "timeout": 30
  },
  "data": {
    "storage_path": "${DATA_STORAGE_PATH}",
    "knowledge_base_path": "${KNOWLEDGE_BASE_PATH}",
    "user_profiles_path": "${USER_PROFILES_PATH}",
    "backup_enabled": true,
    "backup_interval_hours": 24
  },
  "aviation_apis": {
    "weather": {
      "api_key": "${WEATHER_API_KEY}",
      "base_url": "${WEATHER_API_URL}",
      "timeout": 10,
      "cache_duration_minutes": 15
    },
    "flight_tracking": {
      "api_key": "${FLIGHT_API_KEY}",
      "base_url": "${FLIGHT_API_URL}",
      "timeout": 10,
      "cache_duration_minutes": 5
    }
  },
  "security": {
    "encryption_key": "${ENCRYPTION_KEY}",
    "secure_storage_path": "${SECURE_STORAGE_PATH}",
    "log_sensitive_data": false
  },
  "performance": {
    "max_concurrent_requests": 50,
    "request_timeout": 30,
    "rate_limit": {
      "requests_per_minute": 100,
      "burst_limit": 20
    }
  },
  "monitoring": {
    "enable_metrics": true,
    "metrics_port": 8080,
    "health_check_port": 8081,
    "log_level": "INFO"
  }
}
```

## Deployment Methods

### Method 1: Direct Python Deployment

1. **Start the Bot**
   ```bash
   cd /opt/aviationgirl/v4
   sudo -u aviationgirl venv/bin/python -m src.bot.discord_client
   ```

2. **Using Systemd Service**
   
   Create `/etc/systemd/system/aviationgirl.service`:
   ```ini
   [Unit]
   Description=Aviation Girl V4 Discord Bot
   After=network.target
   Wants=network.target
   
   [Service]
   Type=simple
   User=aviationgirl
   Group=aviationgirl
   WorkingDirectory=/opt/aviationgirl/v4
   Environment=PATH=/opt/aviationgirl/v4/venv/bin
   ExecStart=/opt/aviationgirl/v4/venv/bin/python -m src.bot.discord_client
   ExecReload=/bin/kill -HUP $MAINPID
   Restart=always
   RestartSec=10
   StandardOutput=journal
   StandardError=journal
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable aviationgirl
   sudo systemctl start aviationgirl
   ```

### Method 2: Docker Deployment

1. **Build Docker Image**
   ```bash
   cd v4
   docker build -t aviationgirl-v4:latest .
   ```

2. **Run Container**
   ```bash
   docker run -d \
     --name aviationgirl-v4 \
     --env-file .env \
     -v /var/lib/aviationgirl:/app/data \
     -p 8080:8080 \
     -p 8081:8081 \
     --restart unless-stopped \
     aviationgirl-v4:latest
   ```

3. **Using Docker Compose**
   
   Create `docker-compose.yml`:
   ```yaml
   version: '3.8'
   
   services:
     aviationgirl:
       build: .
       container_name: aviationgirl-v4
       env_file: .env
       volumes:
         - /var/lib/aviationgirl:/app/data
         - ./logs:/app/logs
       ports:
         - "8080:8080"  # Metrics
         - "8081:8081"  # Health checks
       restart: unless-stopped
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
         interval: 30s
         timeout: 10s
         retries: 3
         start_period: 40s
   ```
   
   Deploy:
   ```bash
   docker-compose up -d
   ```

### Method 3: Kubernetes Deployment

1. **Create Namespace**
   ```bash
   kubectl apply -f k8s/namespace.yaml
   ```

2. **Deploy Configuration**
   ```bash
   kubectl apply -f k8s/configmap.yaml
   kubectl apply -f k8s/pvc.yaml
   ```

3. **Deploy Application**
   ```bash
   kubectl apply -f k8s/deployment.yaml
   kubectl apply -f k8s/service.yaml
   ```

## Health Checks

### Health Check Endpoints

The bot provides several health check endpoints:

- **Basic Health**: `GET /health`
- **Detailed Health**: `GET /health/detailed`
- **Readiness**: `GET /ready`
- **Liveness**: `GET /alive`

### Health Check Script

Create `/opt/aviationgirl/scripts/health_check.sh`:

```bash
#!/bin/bash

HEALTH_URL="http://localhost:8081/health"
TIMEOUT=10

# Check if health endpoint responds
if curl -f -s --max-time $TIMEOUT "$HEALTH_URL" > /dev/null; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed"
    exit 1
fi
```

Make it executable:
```bash
chmod +x /opt/aviationgirl/scripts/health_check.sh
```

### Monitoring Health

Add to crontab for regular health monitoring:
```bash
# Check health every 5 minutes
*/5 * * * * /opt/aviationgirl/scripts/health_check.sh || /usr/bin/systemctl restart aviationgirl
```

## Monitoring

### Metrics Collection

The bot exposes metrics on port 8080 (configurable):

- **System Metrics**: CPU, memory, disk usage
- **Application Metrics**: Message processing rates, response times, error rates
- **Discord Metrics**: Guild count, user interactions, API rate limits
- **AI Metrics**: Model response times, token usage, error rates

### Log Management

#### Log Configuration

Logs are written to `/var/lib/aviationgirl/logs/` with rotation:

```bash
# Setup log rotation
sudo tee /etc/logrotate.d/aviationgirl << EOF
/var/lib/aviationgirl/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 aviationgirl aviationgirl
    postrotate
        systemctl reload aviationgirl
    endscript
}
EOF
```

#### Log Monitoring

Monitor logs in real-time:
```bash
# Follow all logs
tail -f /var/lib/aviationgirl/logs/*.log

# Follow error logs only
tail -f /var/lib/aviationgirl/logs/error.log

# Search for specific patterns
grep -i "error\|warning\|exception" /var/lib/aviationgirl/logs/*.log
```

## Maintenance

### Regular Maintenance Tasks

1. **Update Dependencies**
   ```bash
   cd /opt/aviationgirl/v4
   sudo -u aviationgirl venv/bin/pip install --upgrade -r requirements.txt
   ```

2. **Database Cleanup**
   ```bash
   # Clean old conversation data (older than 90 days)
   sudo -u aviationgirl python scripts/cleanup_old_data.py --days 90
   ```

3. **Log Cleanup**
   ```bash
   # Manual log cleanup if needed
   find /var/lib/aviationgirl/logs -name "*.log" -mtime +30 -delete
   ```

4. **Backup Data**
   ```bash
   # Create backup
   sudo -u aviationgirl tar -czf /backup/aviationgirl-$(date +%Y%m%d).tar.gz \
     /var/lib/aviationgirl/data
   ```

### Update Procedure

1. **Backup Current Installation**
   ```bash
   sudo systemctl stop aviationgirl
   sudo cp -r /opt/aviationgirl /opt/aviationgirl.backup.$(date +%Y%m%d)
   ```

2. **Deploy New Version**
   ```bash
   # Update code
   sudo cp -r new-version/* /opt/aviationgirl/
   sudo chown -R aviationgirl:aviationgirl /opt/aviationgirl
   
   # Update dependencies
   cd /opt/aviationgirl/v4
   sudo -u aviationgirl venv/bin/pip install -r requirements.txt
   ```

3. **Test Configuration**
   ```bash
   sudo -u aviationgirl venv/bin/python -m src.bot.config_validator
   ```

4. **Restart Service**
   ```bash
   sudo systemctl start aviationgirl
   sudo systemctl status aviationgirl
   ```

5. **Verify Deployment**
   ```bash
   # Check health
   curl http://localhost:8081/health
   
   # Check logs
   sudo journalctl -u aviationgirl -f
   ```

## Troubleshooting

### Common Issues

#### Bot Won't Start

1. **Check Configuration**
   ```bash
   sudo -u aviationgirl python -m src.bot.config_validator
   ```

2. **Check Permissions**
   ```bash
   ls -la /opt/aviationgirl
   ls -la /var/lib/aviationgirl
   ```

3. **Check Dependencies**
   ```bash
   sudo -u aviationgirl venv/bin/pip check
   ```

#### High Memory Usage

1. **Check Memory Usage**
   ```bash
   ps aux | grep python
   free -h
   ```

2. **Restart Service**
   ```bash
   sudo systemctl restart aviationgirl
   ```

3. **Check for Memory Leaks**
   ```bash
   # Monitor memory over time
   while true; do
     ps -p $(pgrep -f aviationgirl) -o pid,vsz,rss,pcpu,pmem,time,comm
     sleep 60
   done
   ```

#### Discord API Issues

1. **Check API Status**
   ```bash
   curl -I https://discord.com/api/v10/gateway
   ```

2. **Check Rate Limits**
   ```bash
   grep -i "rate limit" /var/lib/aviationgirl/logs/*.log
   ```

3. **Verify Bot Token**
   ```bash
   # Test token (replace with actual token)
   curl -H "Authorization: Bot YOUR_TOKEN" \
     https://discord.com/api/v10/users/@me
   ```

### Log Analysis

#### Error Pattern Analysis

```bash
# Most common errors
grep -i error /var/lib/aviationgirl/logs/*.log | \
  awk '{print $NF}' | sort | uniq -c | sort -nr | head -10

# Response time analysis
grep "response_time" /var/lib/aviationgirl/logs/*.log | \
  awk '{print $NF}' | sort -n | tail -20
```

#### Performance Analysis

```bash
# Message processing rates
grep "message_processed" /var/lib/aviationgirl/logs/*.log | \
  awk '{print $1, $2}' | uniq -c

# AI model performance
grep "ai_response_time" /var/lib/aviationgirl/logs/*.log | \
  awk '{sum+=$NF; count++} END {print "Average:", sum/count "ms"}'
```

### Emergency Procedures

#### Service Recovery

```bash
# Emergency restart
sudo systemctl stop aviationgirl
sleep 5
sudo systemctl start aviationgirl

# Force kill if needed
sudo pkill -f aviationgirl
sudo systemctl start aviationgirl
```

#### Rollback Procedure

```bash
# Stop current service
sudo systemctl stop aviationgirl

# Restore backup
sudo rm -rf /opt/aviationgirl
sudo mv /opt/aviationgirl.backup.YYYYMMDD /opt/aviationgirl

# Restart service
sudo systemctl start aviationgirl
```

## Security Considerations

### File Permissions

```bash
# Secure configuration files
sudo chmod 600 /opt/aviationgirl/v4/.env
sudo chmod 600 /opt/aviationgirl/v4/config/*.json

# Secure data directories
sudo chmod 700 /var/lib/aviationgirl/keys
sudo chmod 755 /var/lib/aviationgirl/data
sudo chmod 755 /var/lib/aviationgirl/logs
```

### Network Security

- Use firewall to restrict access to monitoring ports
- Consider using reverse proxy for health check endpoints
- Implement proper SSL/TLS for external API connections

### Data Protection

- Encrypt sensitive data at rest
- Implement proper backup encryption
- Regular security audits of stored data

## Support

For deployment issues:

1. Check the troubleshooting section above
2. Review application logs
3. Verify configuration settings
4. Test network connectivity to required services
5. Contact support with detailed error information

## Appendix

### Required Ports

- **8080**: Metrics endpoint (internal)
- **8081**: Health check endpoint (internal)
- **443**: HTTPS outbound (Discord API, Aviation APIs)
- **80**: HTTP outbound (fallback connections)

### Resource Requirements

| Environment | CPU | Memory | Storage |
|-------------|-----|--------|---------|
| Development | 1 core | 2GB | 5GB |
| Staging | 2 cores | 4GB | 10GB |
| Production | 4 cores | 8GB | 20GB |

### Environment Variables Reference

See the [Configuration](#configuration) section for complete environment variable documentation.