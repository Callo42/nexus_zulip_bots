# Code Quality Makefile
# Usage: make -f build/code-quality.mk [target]
#
# NOTE: Uses conda base environment (see AGENTS.md)

.PHONY: help install format lint check clean

# Use conda base environment
CONDA_RUN := conda run -n base

help:
	@echo "Code Quality Commands"
	@echo "====================="
	@echo ""
	@echo "Setup:"
	@echo "  make -f build/code-quality.mk install    Install pre-commit hooks"
	@echo ""
	@echo "Formatting:"
	@echo "  make -f build/code-quality.mk format     Format code with black + isort"
	@echo ""
	@echo "Linting:"
	@echo "  make -f build/code-quality.mk lint       Run all linters"
	@echo "  make -f build/code-quality.mk flake8     Run flake8 only"
	@echo "  make -f build/code-quality.mk bandit     Run security check"
	@echo "  make -f build/code-quality.mk mypy       Run type check"
	@echo "  make -f build/code-quality.mk check-docs Check docstring consistency"
	@echo ""
	@echo "Pre-commit:"
	@echo "  make -f build/code-quality.mk check      Run pre-commit on all files"
	@echo ""
	@echo "Maintenance:"
	@echo "  make -f build/code-quality.mk clean      Clean cache files"
	@echo ""
	@echo "Documentation: CODE_QUALITY.md"
	@echo "Environment: Conda base"

install:
	@echo "📦 Installing pre-commit hooks (conda base)..."
	@bash build/setup-precommit.sh

format:
	@echo "🎨 Formatting with black..."
	$(CONDA_RUN) black --line-length=100 bots/src/ bots/pc_server/
	@echo "📦 Sorting imports with isort..."
	$(CONDA_RUN) isort --profile=black --line-length=100 bots/src/ bots/pc_server/

lint: flake8 bandit mypy docstrings
	@echo "✅ All lint checks complete"

flake8:
	@echo "🔍 Running flake8..."
	$(CONDA_RUN) flake8 bots/src/ bots/pc_server/ --count --show-source --statistics

bandit:
	@echo "🔒 Running bandit security check..."
	$(CONDA_RUN) bandit -r bots/src/ bots/pc_server/ -ll

mypy:
	@echo "📝 Running mypy type check..."
	$(CONDA_RUN) mypy --ignore-missing-imports bots/src/ bots/pc_server/

docstrings:
	@echo "📚 Checking docstring coverage..."
	$(CONDA_RUN) interrogate --verbose --fail-under=50 bots/src/

check-docs:
	@echo "📋 Checking docstring consistency..."
	$(CONDA_RUN) python build/checks/check_docs.py --all

check:
	@echo "🔎 Running pre-commit on all files..."
	@conda run -n base pre-commit run --all-files

clean:
	@echo "🧹 Cleaning cache files..."
	find bots/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find bots/ -type f -name "*.pyc" -delete 2>/dev/null || true
	find bots/ -type f -name "*.pyo" -delete 2>/dev/null || true
	find bots/ -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find bots/ -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find bots/ -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -f bandit-report.json
	@echo "✅ Clean complete"
