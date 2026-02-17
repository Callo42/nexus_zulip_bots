#!/bin/bash
# Setup pre-commit hooks for the project
# Run from project root directory
#
# NOTE: Uses conda base environment for all Python tools
# (see AGENTS.md for environment details)
#
# IMPORTANT: Code quality tools run on LOCAL HOST, not Docker!
# Docker is for bot runtime only.

set -e

echo "========================================"
echo "Setting up pre-commit hooks"
echo "========================================"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Error: Conda is not installed or not in PATH"
    echo "Please install miniconda or anaconda first"
    exit 1
fi

CONDA_BASE=$(conda info --base)
echo "📍 Using conda from: $CONDA_BASE"
echo "📍 Python version: $(conda run -n base python --version)"

# Install tools into conda base environment
echo "📥 Installing pre-commit and tools into conda base environment..."
conda run -n base pip install --upgrade pip
conda run -n base pip install pre-commit black isort flake8 flake8-bugbear flake8-docstrings bandit mypy interrogate commitizen

# Install pre-commit hooks
echo "🔗 Installing pre-commit hooks..."
conda run -n base pre-commit install

echo ""
echo "========================================"
echo "✅ Pre-commit setup complete!"
echo "========================================"
echo ""
echo "Usage:"
echo "  - Hooks will run automatically on 'git commit'"
echo "  - Run manually: make -f build/code-quality.mk check"
echo "  - Run on specific file: conda run -n base pre-commit run --files bots/src/llm_client.py"
echo "  - Skip hooks (not recommended): git commit --no-verify"
echo ""
echo "Quick commands:"
echo "  make -f build/code-quality.mk format     Format code"
echo "  make -f build/code-quality.mk lint       Run all linters"
echo "  make -f build/code-quality.mk flake8     Run flake8 only"
echo ""
echo "Environment: Conda base ($(conda run -n base python --version))"
echo ""
