# Docker Deployment Guide

This document provides detailed information about using Docker with the TRMNL MBTA project.

## Directory Structure

```
docker/
├── Dockerfile                    # Main application container
├── docker-compose.yml           # Base compose configuration
├── docker-compose.override.yml  # Development overrides
├── docker-compose.prod.yml      # Production configuration
├── docker.env.example           # Environment template
├── Makefile.docker              # Docker-specific make targets
└── docker.sh                    # Convenience script
```

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp docker/docker.env.example docker/docker.env

# Edit with your configuration
vim docker/docker.env
```

### 2. Development Deployment

```bash
# Using the convenience script
cd docker && ./docker.sh dev

# Or using docker-compose directly
cd docker && docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

### 3. Production Deployment

```bash
# Using the convenience script
cd docker && ./docker.sh prod

# Or using docker-compose directly
cd docker && docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Environment Variables

| Variable            | Description                       | Required | Default |
| ------------------- | --------------------------------- | -------- | ------- |
| `MBTA_API_KEY`      | MBTA API key from api-v3.mbta.com | Yes      | -       |
| `TRMNL_WEBHOOK_URL` | TRMNL webhook URL from dashboard  | Yes      | -       |

| `DEBUG_MODE`        | Enable debug mode                 | No       | `false`                 |
| `DEBUG_OUTPUT_FILE` | Debug output file path            | No       | -                       |

## Docker Commands

### Using the Convenience Script

```bash
cd docker

# Build image
./docker.sh build

# Start development
./docker.sh dev

# Start production
./docker.sh prod

# View logs
./docker.sh logs

# Access shell
./docker.sh shell

# Check status
./docker.sh status

# Stop services
./docker.sh stop

# Clean up
./docker.sh clean
```

### Using Docker Compose Directly

```bash
cd docker

# Build and start development
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# Build and start production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f trmnl-mbta

# Stop services
docker-compose down

# Access container shell
docker-compose exec trmnl-mbta /bin/bash
```

## Development vs Production

### Development Mode Features

- **Live reload**: Code changes trigger automatic restarts
- **Debug mode**: Enabled by default
- **Volume mounts**: Source code mounted for live editing
- **Extended logging**: More verbose output
- **Development tools**: Additional debugging utilities

### Production Mode Features

- **Resource limits**: CPU and memory constraints
- **Health checks**: Automatic restart on failure
- **Log rotation**: Prevents log files from growing too large
- **Security hardening**: Non-root user, minimal attack surface
- **Persistent volumes**: Data survives container restarts

## Troubleshooting

### Common Issues

1. **Container won't start**
   ```bash
   # Check container logs
   docker-compose logs trmnl-mbta
   
   # Stop conflicting services
   docker-compose down
   ```

2. **Permission denied**
   ```bash
   # Fix script permissions
   chmod +x docker/docker.sh
   ```

3. **Environment variables not loaded**
   ```bash
   # Verify .env file exists and has correct format
   cat docker/docker.env
   ```

4. **Container won't start**
   ```bash
   # Check logs for errors
   cd docker && docker-compose logs trmnl-mbta
   ```

### Debugging

```bash
# Access container shell for debugging
cd docker && ./docker.sh shell

# Check container status
cd docker && ./docker.sh status

# View real-time logs
cd docker && ./docker.sh logs

# Rebuild from scratch
cd docker && ./docker.sh clean && ./docker.sh build && ./docker.sh dev
```

## Best Practices

1. **Always use the convenience script** for consistency
2. **Keep environment files secure** - never commit them
3. **Use development mode** for local development
4. **Use production mode** for deployments
5. **Monitor logs regularly** for issues
6. **Clean up resources** periodically to save disk space

## Security Considerations

- Environment files contain sensitive information
- Container runs as non-root user
- Only necessary ports are exposed
- Resource limits prevent resource exhaustion
- Health checks ensure service availability
