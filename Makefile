# AI Tutor App - Development Makefile

.PHONY: help install dev build test clean docker-build docker-up docker-down logs

# Default target
help:
	@echo "AI Tutor App - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  install     - Install all dependencies"
	@echo "  dev         - Start development servers"
	@echo "  build       - Build all components"
	@echo "  test        - Run all tests"
	@echo "  lint        - Run linters"
	@echo "  clean       - Clean build artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build - Build Docker images"
	@echo "  docker-up   - Start all services with Docker"
	@echo "  docker-down - Stop all Docker services"
	@echo "  logs        - View Docker logs"
	@echo ""
	@echo "Database:"
	@echo "  db-setup    - Initialize databases"
	@echo "  db-reset    - Reset databases"
	@echo ""

# Development commands
install:
	@echo "Installing dependencies..."
	npm install
	cd backend && npm install
	cd frontend && npm install
	cd agent && pip install -r requirements.txt

dev:
	@echo "Starting development servers..."
	npm run dev

build:
	@echo "Building all components..."
	cd frontend && npm run build
	cd backend && npm run build || echo "Backend build not needed"

test:
	@echo "Running tests..."
	cd backend && npm test
	cd frontend && npm test
	cd agent && python -m pytest

lint:
	@echo "Running linters..."
	cd backend && npm run lint
	cd frontend && npm run lint
	cd agent && flake8 src/

clean:
	@echo "Cleaning build artifacts..."
	rm -rf frontend/dist
	rm -rf backend/dist
	rm -rf */node_modules
	rm -rf agent/__pycache__
	rm -rf agent/.pytest_cache

# Docker commands
docker-build:
	@echo "Building Docker images..."
	docker-compose build

docker-up:
	@echo "Starting all services..."
	docker-compose up -d
	@echo "Services started! Frontend: http://localhost:3000, Backend: http://localhost:5000, ML Service: http://localhost:8001"

docker-down:
	@echo "Stopping all services..."
	docker-compose down

logs:
	@echo "Viewing logs..."
	docker-compose logs -f

# Database commands
db-setup:
	@echo "Setting up databases..."
	docker-compose up -d postgres mongodb
	sleep 10
	@echo "Databases ready!"

db-reset:
	@echo "Resetting databases..."
	docker-compose down -v
	docker-compose up -d postgres mongodb
	sleep 10
	@echo "Databases reset!"

# Quick start command
start: docker-up
	@echo ""
	@echo "🚀 AI Tutor App is running!"
	@echo "📱 Frontend: http://localhost:3000"
	@echo "🔧 Backend API: http://localhost:5000"
	@echo "🤖 ML Service: http://localhost:8001"
	@echo "📊 Database: PostgreSQL (5432), MongoDB (27017)"
	@echo ""
	@echo "To stop: make docker-down"

# Development setup
setup: install db-setup
	@echo "✅ Development environment setup complete!"
	@echo "Run 'make dev' to start development servers"