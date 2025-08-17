#!/bin/bash
# Build Docker image for TRMNL MBTA

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Building TRMNL MBTA Docker image...${NC}"

# Check if Dockerfile exists
if [ ! -f "docker/Dockerfile" ]; then
    echo -e "${RED}❌ Dockerfile not found in docker/ directory${NC}"
    exit 1
fi

# Build the image
docker build -f docker/Dockerfile -t trmnl-mbta:latest .

# Tag with version if provided
if [ ! -z "$1" ]; then
    echo -e "${GREEN}🏷️  Tagging image as trmnl-mbta:$1${NC}"
    docker tag trmnl-mbta:latest trmnl-mbta:$1
fi

echo -e "${GREEN}✅ Build completed successfully!${NC}"
echo -e "${YELLOW}📋 Available images:${NC}"
docker images | grep trmnl-mbta

echo -e "${YELLOW}🚀 To run the container:${NC}"
echo "  cd docker && docker-compose up -d"
echo ""
echo -e "${YELLOW}🔧 To run in development mode:${NC}"
echo "  cd docker && docker-compose -f docker-compose.yml -f docker-compose.override.yml up"
