.PHONY: help dev dev-backend dev-frontend test test-backend test-frontend lint build clean docker-up docker-down migrate

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start both backend and frontend dev servers
	@echo "Starting backend and frontend..."
	@trap 'kill 0' EXIT; \
	(cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

dev-backend: ## Start backend dev server
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd backend && python -m pytest tests/ -v --tb=short

test-frontend: ## Run frontend tests
	cd frontend && npm run test -- --run

lint: ## Run linters for both backend and frontend
	@echo "Linting backend..."
	cd backend && python -m pylint app/ --disable=C0111,R0903 || true
	@echo "Linting frontend..."
	cd frontend && npm run lint

build: ## Build frontend for production
	cd frontend && npm run build

clean: ## Clean build artifacts and cache files
	@echo "Cleaning build artifacts..."
	rm -rf frontend/dist
	rm -rf frontend/.vite
	rm -rf backend/__pycache__
	rm -rf backend/**/__pycache__
	rm -rf backend/.pytest_cache
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Clean complete"

docker-up: ## Start Docker services (PostgreSQL, Redis, Qdrant)
	docker compose up -d

docker-down: ## Stop Docker services
	docker compose down

docker-logs: ## Show Docker service logs
	docker compose logs -f

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="migration message")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

migrate-rollback: ## Rollback last migration
	cd backend && alembic downgrade -1

install: ## Install all dependencies
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

setup: install docker-up migrate ## Complete setup: install dependencies, start services, run migrations
	@echo "Setup complete! Run 'make dev' to start development servers"
