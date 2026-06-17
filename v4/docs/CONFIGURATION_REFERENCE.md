# Aviation Girl V4 Discord Bot - Configuration Reference

## Overview

This document provides a comprehensive reference for all configuration options available in the Aviation Girl V4 Discord Bot.

## Table of Contents

1. [Environment Variables](#environment-variables)
2. [Configuration Files](#configuration-files)
3. [Security Configuration](#security-configuration)
4. [Performance Tuning](#performance-tuning)
5. [Monitoring Configuration](#monitoring-configuration)
6. [Deployment Configurations](#deployment-configurations)

## Environment Variables

### Discord Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | - | Discord bot token from Discord Developer Portal |
| `DISCORD_COMMAND_PREFIX` | No | `!` | Command prefix for bot commands |
| `DISCORD_MAX_MESSAGE_LENGTH` | No | `2000` | Maximum message length for responses |

### AI Model Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AI_MODEL_NAME` | Yes | `qwen2.5-7b-instruct` | Name of the AI model to use |
| `AI_MODEL_PATH` | No | `/models/` | Path to AI model files |
| `AI_MAX_TOKENS` | No | `2000` | Maximum tokens for AI responses |
| `AI_TEMPERATURE` | No | `0.7` | Temperature setting for AI generation |
| `AI_TIMEOUT` | No | `30` | Timeout for AI requests in seconds |

### Data Storage Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATA_STORAGE_PATH` | No | `./data` | Base path for data storage |
| `KNOWLEDGE_BASE_PATH` | No | `./data/knowledge` | Path for knowledge base files |
| `USER_PROFILES_PATH` | No | `./data/profiles` | Path for user profile storage |
| `LOGS_PATH` | No | `./logs` | Path for log files |

### Aviation API Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEATHER_API_KEY` | No | - | API key for weather data service |
| `WEATHER_API_URL` | No | - | Base URL for weather API |
| `FLIGHT_API_KEY` | No | - | API key for flight tracking service |
| `FLIGHT_API_URL` | No | - | Base URL for flight tracking API |
| `NOTAM_API_KEY` | No | - | API key for NOTAM service |
| `NOTAM_API_URL` | No | - | Base URL for NOTAM API |

### Security Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENCRYPTION_KEY` | Yes | - | 32-character encryption key for sensitive data |
| `SECURE_STORAGE_PATH` | No | `./keys` | Path for secure credential storage |
| `LOG_SENSITIVE_DATA` | No | `false` | Whether to log sensitive information |

### Performance Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAX_CONCURRENT_REQUESTS` | No | `50` | Maximum concurrent request processing |
| `REQUEST_TIMEOUT` | No | `30` | Request timeout in seconds |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | No | `100` | Rate limit for requests per minute |
| `RATE_LIMIT_BURST_LIMIT` | No | `20` | Burst limit for rate limiting |

### Monitoring Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_METRICS` | No | `true` | Enable metrics collection |
| `METRICS_PORT` | No | `8080` | Port for metrics endpoint |
| `HEALTH_CHECK_PORT` | No | `8081` | Port for health check endpoint |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Environment Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | Environment type (development, staging, production) |
| `DEBUG` | No | `false` | Enable debug mode |

## Configuration Files

### Main Configuration File

The main configuration file is located at `v4/config/{environment}.json` where `{environment}` is the value of the `ENVIRONMENT` variable.

#### Example: `v4/config/production.json`

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
    },
    "rate_limiting": {
      "enabled": true,
      "requests_per_second": 5,
      "burst_limit": 10
    }
  },
  "ai": {
    "model_name": "${AI_MODEL_NAME}",
    "model_path": "${AI_MODEL_PATH}",
    "max_tokens": 2000,
    "temperature": 0.7,
    "timeout": 30,
    "fallback_responses": {
      "enabled": true,
      "timeout_message": "I'm taking longer than usual to respond. Please try again.",
      "error_message": "I'm experiencing technical difficulties. Please try again later."
    }
  },
  "data": {
    "storage_path": "${DATA_STORAGE_PATH}",
    "knowledge_base_path": "${KNOWLEDGE_BASE_PATH}",
    "user_profiles_path": "${USER_PROFILES_PATH}",
    "backup_enabled": true,
    "backup_interval_hours": 24,
    "data_retention": {
      "conversation_days": 90,
      "user_profile_days": 365,
      "log_days": 30
    }
  },
  "aviation_apis": {
    "weather": {
      "api_key": "${WEATHER_API_KEY}",
      "base_url": "${WEATHER_API_URL}",
      "timeout": 10,
      "cache_duration_minutes": 15,
      "retry_attempts": 3
    },
    "flight_tracking": {
      "api_key": "${FLIGHT_API_KEY}",
      "base_url": "${FLIGHT_API_URL}",
      "timeout": 10,
      "cache_duration_minutes": 5,
      "retry_attempts": 2
    },
    "notam": {
      "api_key": "${NOTAM_API_KEY}",
      "base_url": "${NOTAM_API_URL}",
      "timeout": 15,
      "cache_duration_minutes": 30,
      "retry_attempts": 2
    }
  },
  "security": {
    "encryption_key": "${ENCRYPTION_KEY}",
    "secure_storage_path": "${SECURE_STORAGE_PATH}",
    "log_sensitive_data": false,
    "password_policy": {
      "min_length": 12,
      "require_special_chars": true,
      "require_numbers": true
    },
    "session_management": {
      "timeout_minutes": 60,
      "max_concurrent_sessions": 5
    }
  },
  "performance": {
    "max_concurrent_requests": 50,
    "request_timeout": 30,
    "memory_limit_mb": 2048,
    "cpu_limit_percent": 80,
    "rate_limit": {
      "requests_per_minute": 100,
      "burst_limit": 20,
      "cooldown_seconds": 60
    },
    "caching": {
      "enabled": true,
      "ttl_seconds": 300,
      "max_size_mb": 100
    }
  },
  "monitoring": {
    "enable_metrics": true,
    "metrics_port": 8080,
    "health_check_port": 8081,
    "log_level": "INFO",
    "alerts": {
      "enabled": true,
      "email_notifications": false,
      "webhook_notifications": false,
      "thresholds": {
        "memory_percent": 85,
        "cpu_percent": 80,
        "disk_percent": 90,
        "response_time_ms": 5000,
        "error_rate_percent": 10
      }
    }
  },
  "features": {
    "interactive_experiences": {
      "enabled": true,
      "quiz_timeout_minutes": 30,
      "max_concurrent_quizzes": 10
    },
    "file_processing": {
      "enabled": true,
      "max_file_size_mb": 10,
      "allowed_extensions": [".txt", ".pdf", ".jpg", ".png", ".kml", ".gpx"]
    },
    "thread_management": {
      "enabled": true,
      "auto_archive_hours": 24,
      "max_thread_participants": 50
    }
  }
}
```

### Development Configuration

#### Example: `v4/config/development.json`

```json
{
  "discord": {
    "token": "${DISCORD_TOKEN}",
    "command_prefix": "!dev",
    "max_message_length": 2000,
    "intents": {
      "message_content": true,
      "reactions": true,
      "guilds": true,
      "members": true
    }
  },
  "ai": {
    "model_name": "test-model",
    "max_tokens": 1000,
    "temperature": 0.8,
    "timeout": 60
  },
  "data": {
    "storage_path": "./dev_data",
    "backup_enabled": false
  },
  "monitoring": {
    "log_level": "DEBUG",
    "enable_metrics": false
  },
  "security": {
    "log_sensitive_data": true
  }
}
```

## Security Configuration

### Encryption Settings

```json
{
  "security": {
    "encryption": {
      "algorithm": "AES-256-GCM",
      "key_derivation": "PBKDF2",
      "iterations": 100000,
      "salt_length": 32
    },
    "data_protection": {
      "encrypt_user_profiles": true,
      "encrypt_conversation_history": true,
      "encrypt_api_keys": true,
      "hash_user_ids": false
    }
  }
}
```

### Access Control

```json
{
  "security": {
    "access_control": {
      "admin_users": ["user_id_1", "user_id_2"],
      "moderator_users": ["user_id_3", "user_id_4"],
      "banned_users": [],
      "guild_whitelist": [],
      "guild_blacklist": []
    },
    "permissions": {
      "admin_commands": ["restart", "shutdown", "backup", "config"],
      "moderator_commands": ["ban", "unban", "clear_data"],
      "user_commands": ["help", "weather", "aircraft", "quiz"]
    }
  }
}
```

## Performance Tuning

### Memory Management

```json
{
  "performance": {
    "memory": {
      "max_heap_size_mb": 2048,
      "gc_threshold_mb": 1024,
      "conversation_cache_size": 1000,
      "knowledge_cache_size": 5000,
      "cleanup_interval_minutes": 30
    }
  }
}
```

### Concurrency Settings

```json
{
  "performance": {
    "concurrency": {
      "max_worker_threads": 10,
      "max_io_threads": 20,
      "queue_size": 1000,
      "timeout_seconds": 30,
      "retry_attempts": 3,
      "backoff_multiplier": 2
    }
  }
}
```

### Database Optimization

```json
{
  "performance": {
    "database": {
      "connection_pool_size": 10,
      "connection_timeout": 30,
      "query_timeout": 15,
      "batch_size": 100,
      "vacuum_interval_hours": 24,
      "index_optimization": true
    }
  }
}
```

## Monitoring Configuration

### Metrics Collection

```json
{
  "monitoring": {
    "metrics": {
      "collection_interval_seconds": 30,
      "retention_days": 7,
      "custom_metrics": {
        "message_processing_time": true,
        "ai_response_quality": true,
        "user_satisfaction": true,
        "knowledge_base_hits": true
      }
    }
  }
}
```

### Alerting Rules

```json
{
  "monitoring": {
    "alerts": {
      "rules": [
        {
          "name": "high_memory_usage",
          "condition": "memory_percent > 85",
          "duration_minutes": 5,
          "severity": "warning",
          "actions": ["email", "webhook"]
        },
        {
          "name": "high_error_rate",
          "condition": "error_rate_percent > 10",
          "duration_minutes": 2,
          "severity": "critical",
          "actions": ["email", "webhook", "restart"]
        },
        {
          "name": "slow_response_time",
          "condition": "avg_response_time_ms > 5000",
          "duration_minutes": 3,
          "severity": "warning",
          "actions": ["webhook"]
        }
      ]
    }
  }
}
```

## Deployment Configurations

### Docker Configuration

#### Dockerfile Environment Variables

```dockerfile
ENV DISCORD_TOKEN=""
ENV AI_MODEL_NAME="qwen2.5-7b-instruct"
ENV DATA_STORAGE_PATH="/app/data"
ENV LOGS_PATH="/app/logs"
ENV ENVIRONMENT="production"
ENV LOG_LEVEL="INFO"
```

### Kubernetes Configuration

#### ConfigMap Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aviationgirl-config
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  METRICS_PORT: "8080"
  HEALTH_CHECK_PORT: "8081"
  MAX_CONCURRENT_REQUESTS: "50"
  REQUEST_TIMEOUT: "30"
```

#### Secret Example

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aviationgirl-secrets
type: Opaque
data:
  DISCORD_TOKEN: <base64-encoded-token>
  ENCRYPTION_KEY: <base64-encoded-key>
  WEATHER_API_KEY: <base64-encoded-key>
```

### Systemd Service Configuration

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
Environment=ENVIRONMENT=production
Environment=LOG_LEVEL=INFO
EnvironmentFile=/opt/aviationgirl/v4/.env
ExecStart=/opt/aviationgirl/v4/venv/bin/python -m src.bot.discord_client
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Configuration Validation

### Validation Rules

The bot includes built-in configuration validation that checks:

1. **Required Fields**: All required configuration fields are present
2. **Data Types**: Configuration values match expected data types
3. **Value Ranges**: Numeric values are within acceptable ranges
4. **File Paths**: Specified paths exist and are accessible
5. **API Connectivity**: External API endpoints are reachable
6. **Security**: Encryption keys meet minimum requirements

### Validation Command

```bash
# Validate configuration
python -m src.bot.config_validator

# Validate specific environment
python -m src.bot.config_validator --env production

# Validate and show detailed report
python -m src.bot.config_validator --verbose
```

## Configuration Best Practices

### Security Best Practices

1. **Never commit secrets**: Use environment variables or secure secret management
2. **Rotate keys regularly**: Change encryption keys and API keys periodically
3. **Limit permissions**: Use principle of least privilege for file permissions
4. **Encrypt sensitive data**: Enable encryption for user data and API keys
5. **Monitor access**: Log and monitor configuration access

### Performance Best Practices

1. **Tune for your environment**: Adjust memory and CPU limits based on available resources
2. **Monitor metrics**: Use performance metrics to identify bottlenecks
3. **Cache appropriately**: Configure caching based on data access patterns
4. **Scale gradually**: Increase limits gradually while monitoring performance
5. **Regular maintenance**: Perform regular cleanup and optimization

### Operational Best Practices

1. **Environment separation**: Use different configurations for dev/staging/production
2. **Version control**: Track configuration changes in version control
3. **Backup configurations**: Include configurations in backup procedures
4. **Document changes**: Document configuration changes and their impact
5. **Test configurations**: Validate configurations in staging before production

## Troubleshooting Configuration Issues

### Common Issues

1. **Invalid JSON**: Check for syntax errors in configuration files
2. **Missing environment variables**: Ensure all required variables are set
3. **File permissions**: Check that the bot can read configuration files
4. **Network connectivity**: Verify external API endpoints are accessible
5. **Resource limits**: Ensure system has sufficient resources for configured limits

### Debugging Commands

```bash
# Check configuration syntax
python -c "import json; json.load(open('config/production.json'))"

# Test environment variables
env | grep -E "(DISCORD|AI|DATA)_"

# Validate file permissions
ls -la config/
ls -la .env

# Test API connectivity
curl -I https://discord.com/api/v10/gateway
```

## Configuration Migration

### Upgrading Configurations

When upgrading the bot, configuration files may need updates:

1. **Backup current configuration**: Always backup before upgrading
2. **Review changelog**: Check for configuration changes in release notes
3. **Use migration tools**: Use provided migration scripts when available
4. **Validate after upgrade**: Run configuration validation after upgrading
5. **Test thoroughly**: Test all functionality after configuration changes

### Migration Script Example

```bash
#!/bin/bash
# Migrate configuration from v3 to v4

# Backup current configuration
cp config/production.json config/production.json.backup

# Apply migration transformations
python scripts/migrate_config.py --from v3 --to v4 --config config/production.json

# Validate migrated configuration
python -m src.bot.config_validator --config config/production.json
```

This configuration reference provides comprehensive documentation for all aspects of configuring the Aviation Girl V4 Discord Bot. Use this as a reference when setting up, maintaining, or troubleshooting your bot deployment.