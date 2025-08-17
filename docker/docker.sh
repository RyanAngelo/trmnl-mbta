#!/bin/bash
# Convenience script for Docker operations in the docker/ directory

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

COMMAND=${1:-help}

case $COMMAND in
    "build")
        echo -e "${GREEN}🐳 Building Docker image...${NC}"
        docker build -f Dockerfile -t trmnl-mbta:latest ..
        ;;
    "dev"|"development")
        echo -e "${BLUE}🔧 Starting development environment...${NC}"
        docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
        ;;
    "prod"|"production")
        echo -e "${BLUE}🏭 Starting production environment...${NC}"
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
        ;;
    "stop")
        echo -e "${YELLOW}🛑 Stopping services...${NC}"
        docker-compose down
        ;;
    "logs")
        echo -e "${BLUE}📋 Showing logs...${NC}"
        docker-compose logs -f trmnl-mbta
        ;;
    "shell")
        echo -e "${BLUE}🐚 Accessing container shell...${NC}"
        docker-compose exec trmnl-mbta /bin/bash
        ;;
    "status")
        echo -e "${BLUE}📊 Container status:${NC}"
        docker-compose ps
        ;;
    "restart")
        echo -e "${YELLOW}🔄 Restarting services...${NC}"
        docker-compose restart
        ;;
    "clean")
        echo -e "${YELLOW}🧹 Cleaning up...${NC}"
        docker-compose down -v --remove-orphans
        docker system prune -f
        ;;
    "help"|*)
        echo -e "${GREEN}🐳 TRMNL MBTA Docker Commands${NC}"
        echo ""
        echo "Usage: ./docker.sh <command>"
        echo ""
        echo "Commands:"
        echo "  build       - Build Docker image"
        echo "  dev         - Start development environment"
        echo "  prod        - Start production environment"
        echo "  stop        - Stop all services"
        echo "  logs        - Show container logs"
        echo "  shell       - Access container shell"
        echo "  status      - Show container status"
        echo "  restart     - Restart services"
        echo "  clean       - Clean up containers and images"
        echo "  help        - Show this help"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  ./docker.sh build"
        echo "  ./docker.sh dev"
        echo "  ./docker.sh logs"
        ;;
esac
