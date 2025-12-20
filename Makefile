.PHONY: dev up down logs clean test test-up test-down help

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

help:
	@echo "Makefile commands:"
	@echo "  dev    - Start development environment with hot-reloading"
	@echo "  up     - Start services in detached mode"
	@echo "  down   - Stop services"
	@echo "  logs   - Follow logs of services"
	@echo "  clean  - Remove all containers, networks, and volumes"

test-up:
	docker compose -f docker-compose.test.yml up --build \
		--abort-on-container-exit \
		--exit-code-from backend-test

test-down:
	docker compose -f docker-compose.test.yml down -v

test: test-up test-down

clean:
	docker compose down -v --remove-orphans
