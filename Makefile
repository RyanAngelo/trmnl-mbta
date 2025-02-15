.PHONY: install test lint format sync-deps clean

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	flake8 .
	black . --check
	isort . --check-only

format:
	black .
	isort .

sync-deps:
	./scripts/sync_deps.py

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +

# Help command to show available commands
help:
	@echo "Available commands:"
	@echo "  make install    - Install package in development mode with all dependencies"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Run linting checks"
	@echo "  make format    - Format code with black and isort"
	@echo "  make sync-deps - Sync dependencies between pyproject.toml and requirements.txt"
	@echo "  make clean     - Remove build artifacts and cache files" 