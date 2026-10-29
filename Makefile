# Juku's one command: `make check` (standard-checks.md, section 1).
#
# It runs before every commit (the pre-commit hook) and again in CI. Each
# step is one tool. A tool that isn't installed locally is skipped with a
# note, and CI, which sets JUKU_REQUIRE_TOOLS=1, fails instead: CI installs
# every tool, so nothing is skipped there.
#
#   make check     lint, types, tests and fitness functions, migrations, secrets, frontend
#   make db-up     start the local test Postgres (loopback only, throwaway)
#   make db-down   stop it and delete its data
#   make fix       format and auto-fix lint
#   make mutation  mutmut on every package (end of each slice; slow, so not in make check)

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := check

UV ?= uv
BUILD := build
TEST_DB_CONTAINER := juku-test-db
TEST_DB_PORT := 55440
WEB_DIR := app/web

WITH_TOOL := scripts/with-tool.sh

.PHONY: check lint types test migrations-lint secrets frontend lighthouse fix mutation db-up db-down

check: lint types test migrations-lint secrets frontend lighthouse
	@echo "make check: all steps passed"

lint:
	$(UV) run --frozen ruff check .
	$(UV) run --frozen ruff format --check .

types:
	$(UV) run --frozen pyright

# --fitness-complete: an active fitness function in guardrails.yaml with no test fails the run.
# --guardrails-complete: so does a rule in guardrails.yaml with no test (G1).
test:
	$(UV) run --frozen pytest -q --fitness-complete --guardrails-complete

# FF4: render every migration as SQL, offline, and lint it for locking or rewriting statements.
# Alembic's own bookkeeping table (alembic_version, a varchar column) isn't ours, so it's cut first.
migrations-lint:
	@mkdir -p $(BUILD)
	$(UV) run --frozen alembic upgrade heads --sql | sed '/^CREATE TABLE alembic_version/,/^);/d' > $(BUILD)/migrations.sql
	$(WITH_TOOL) squawk "FF4: pip install squawk-cli==2.70.0" squawk --config .squawk.toml $(BUILD)/migrations.sql

# Secrets in any commit, then in the files not yet committed.
secrets:
	$(WITH_TOOL) gitleaks "brew install gitleaks" gitleaks git --no-banner --redact --config .gitleaks.toml .
	$(WITH_TOOL) gitleaks "brew install gitleaks" gitleaks dir --no-banner --redact --config .gitleaks.toml .

# The Vue islands: Vitest, the type check and production build, and FE7's size budget.
frontend:
	cd $(WEB_DIR) && npm ci --prefer-offline --no-audit --no-fund --silent && npm run --silent check

# FF12: the frontend budget on Lighthouse's mobile profile, on static copies of the pages
# (the frontend step has just built the islands).
lighthouse:
	$(UV) run --frozen juku render-previews --out $(BUILD)/previews >/dev/null
	cd $(WEB_DIR) && ../../$(WITH_TOOL) lhci "FF12: npm install -g @lhci/cli@0.15.1" lhci autorun --config=lighthouserc.json

# mutmut 3 runs one package at a time (each has its own [tool.mutmut]); survivors are listed.
mutation:
	@for package in packages/*/; do \
		grep -q '^\[tool.mutmut\]' $$package/pyproject.toml || continue; \
		echo "== $$package"; \
		(cd $$package && rm -rf mutants && $(UV) run --frozen mutmut run --max-children 4 >/dev/null; \
			$(UV) run --frozen mutmut results | grep -v ': killed'; rm -rf mutants); \
	done

fix:
	$(UV) run --frozen ruff format .
	$(UV) run --frozen ruff check --fix .

db-up:
	@if docker inspect $(TEST_DB_CONTAINER) >/dev/null 2>&1; then docker start $(TEST_DB_CONTAINER) >/dev/null; else \
		docker run -d --name $(TEST_DB_CONTAINER) -p 127.0.0.1:$(TEST_DB_PORT):5432 \
			-e POSTGRES_HOST_AUTH_METHOD=trust --memory 512m postgres:16 >/dev/null; fi
	@for _ in $$(seq 1 30); do docker exec $(TEST_DB_CONTAINER) pg_isready -q -U postgres && break; sleep 1; done
	@echo "test Postgres on 127.0.0.1:$(TEST_DB_PORT) (container $(TEST_DB_CONTAINER))"

db-down:
	docker rm -f $(TEST_DB_CONTAINER)
