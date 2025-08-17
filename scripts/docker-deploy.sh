#!/bin/bash
# Deploy TRMNL MBTA using Docker Compose

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default environment
ENVIRONMENT=${1:-development}

echo -e "${GREEN}🚀 Deploying TRMNL MBTA in ${ENVIRONMENT} mode...${NC}"

# Check if docker.env exists
if [ ! -f "docker/docker.env" ]; then
    echo -e "${YELLOW}⚠️  docker/docker.env not found. Creating from example...${NC}"
    if [ -f "docker/docker.env.example" ]; then
        cp docker/docker.env.example docker/docker.env
        echo -e "${RED}❗ Please edit docker/docker.env with your actual configuration before continuing${NC}"
        exit 1
    else
        echo -e "${RED}❌ docker/docker.env.example not found${NC}"
        exit 1
    fi
fi

# Source environment variables
export $(grep -v '^#' docker/docker.env | xargs)

case $ENVIRONMENT in
    "development"|"dev")
        echo -e "${BLUE}🔧 Starting development environment...${NC}"
        cd docker && docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
        ;;
    "production"|"prod")
        echo -e "${BLUE}🏭 Starting production environment...${NC}"
        cd docker && docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
        ;;
    *)
        echo -e "${RED}❌ Unknown environment: $ENVIRONMENT${NC}"
        echo -e "${YELLOW}Available environments: development, production${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}✅ Deployment completed!${NC}"
echo ""
echo -e "${YELLOW}📊 Container status:${NC}"
cd docker && docker-compose ps

echo ""
echo -e "${YELLOW}📋 Useful commands:${NC}"
echo "  View logs:     cd docker && docker-compose logs -f trmnl-mbta"
echo "  Stop service:  cd docker && docker-compose down"
echo "  Restart:       cd docker && docker-compose restart trmnl-mbta"
echo "  Shell access:  cd docker && docker-compose exec trmnl-mbta /bin/bash"
echo ""
echo -e "${YELLOW}📋 CLI application is running in the container${NC}"
