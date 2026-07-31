.PHONY: help sync run test lint typecheck

# Default: show help
.DEFAULT_GOAL := help

help: ## Show this help
	@echo "ai-engine — Academio AI engine (Python)"
	@echo ""
	@grep -E '^[a-zA-Z_%-]+:.*?## ' $(MAKEFILE_LIST) | awk -F'## ' '{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Project ─────────────────────────────────────────────────────────────────

sync: ## Sync dependencies
	uv sync

run: ## Run the dev server
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# ── Quality ─────────────────────────────────────────────────────────────────

test: ## Run tests
	uv run pytest

lint: ## Lint with ruff
	uv run ruff check .

typecheck: ## Type check
	uv run pyright
