#!/bin/bash
# Development environment setup script

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🛠️  Setting up TRMNL MBTA development environment...${NC}"

# Check if we're in a devcontainer
if [ -n "$REMOTE_CONTAINERS" ] || [ -n "$CODESPACES" ]; then
    echo -e "${GREEN}✅ Running in development container${NC}"
else
    echo -e "${YELLOW}⚠️  Not in a development container. Consider using VS Code Dev Containers.${NC}"
fi

# Install Python dependencies
echo -e "${GREEN}📦 Installing Python dependencies...${NC}"
pip install -e ".[dev]"

# Set up pre-commit hooks
echo -e "${GREEN}🪝 Setting up pre-commit hooks...${NC}"
pre-commit install

# Create necessary directories
echo -e "${GREEN}📁 Creating directories...${NC}"
mkdir -p logs
mkdir -p data

# Set up environment files
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}📝 Creating .env from example...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}❗ Please edit .env with your configuration${NC}"
    fi
fi

if [ ! -f "config.json" ]; then
    echo -e "${YELLOW}📝 Creating default config.json...${NC}"
    echo '{"route_id": "Orange"}' > config.json
fi

# Run tests to verify setup
echo -e "${GREEN}🧪 Running tests to verify setup...${NC}"
python -m pytest tests/ -v --tb=short

echo -e "${GREEN}✅ Development environment setup complete!${NC}"
echo ""
echo -e "${YELLOW}🚀 Quick start commands:${NC}"
echo "  Run CLI:        python cli.py"
echo "  Run tests:      python -m pytest"
echo "  Format code:    black src/ tests/"
echo "  Lint code:      flake8 src/ tests/"
echo "  Docker build:   ./scripts/docker-build.sh"
echo ""
echo -e "${YELLOW}📚 VS Code features:${NC}"
echo "  - Press F5 to debug the application"
echo "  - Use Ctrl+Shift+P -> 'Tasks: Run Task' for common tasks"
echo "  - Python tests are auto-discovered in the Test Explorer"
