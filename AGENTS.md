# Agent Guidelines for Zulip LLM Bot

## Project Overview

**Zulip LLM Bot** is a sophisticated chatbot system for Zulip that integrates Large Language Models (LLMs) via LiteLLM proxy. The bot operates with a unique dual-container architecture:

- **Bot Container** (`bots/src/`): Main Zulip bot handling messages, policies, and LLM interactions
- **PC Sidecar** (`bots/pc_server/`): Flask-based API providing tool execution, file management, and conversation history persistence

The architecture enables the bot to execute commands, manage files, persist conversation history, and call external tools (GitLab, web search) while maintaining security through API key authentication and policy-based access control.

### Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11 |
| Bot Framework | Zulip Python API (`zulip==0.9.0`) |
| LLM Gateway | LiteLLM (OpenAI-compatible API) |
| PC Sidecar | Flask 2.3.3 + Flask-CORS |
| Configuration | YAML (`PyYAML`) |
| HTTP Client | `requests==2.31.0` |
| Containerization | Docker + Docker Compose |
| Database | PostgreSQL 15 (for LiteLLM persistence) |
| Local LLMs | Ollama |

### Runtime Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                            │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │   postgres   │  │   litellm    │  │      ollama         │   │
│  │   (db)       │  │   (proxy)    │  │   (local LLMs)      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬──────────┘   │
│         │                 │                     │              │
│         └─────────────────┼─────────────────────┘              │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────┐           │
│  │           zulip-bot-<name> (main)                │           │
│  │  ┌──────────────┐  ┌──────────────┐            │           │
│  │  │  ZulipHandler │  │  LLMClient   │            │           │
│  │  │  (messaging)  │  │  (LiteLLM)   │            │           │
│  │  └──────────────┘  └──────────────┘            │           │
│  └────────────────────────┬────────────────────────┘           │
│                           │ HTTP API (internal network)        │
│  ┌────────────────────────┴────────────────────────┐           │
│  │        zulip-bot-<name>-pc (sidecar)             │           │
│  │  ┌──────────────┐  ┌──────────────┐            │           │
│  │  │ PCManager    │  │ ToolRegistry │            │           │
│  │  │ (files/cmds) │  │ (tools)      │            │           │
│  │  └──────────────┘  └──────────────┘            │           │
│  └─────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Commands

### Setup

```bash
# Install Python dependencies
pip install -r bots/requirements.txt
pip install -r bots/pc_server/requirements.txt

# Install pre-commit hooks (one-time)
bash build/setup-precommit.sh
# Or: make -f build/code-quality.mk install
```

### Build & Lint

```bash
# Format all code
make -f build/code-quality.mk format

# Run all linters
make -f build/code-quality.mk lint

# Run specific linter
make -f build/code-quality.mk flake8      # Style and complexity
make -f build/code-quality.mk mypy        # Type checking
make -f build/code-quality.mk bandit      # Security scan
make -f build/code-quality.mk docstrings  # Docstring coverage
make -f build/code-quality.mk check-docs  # Docstring consistency

# Run pre-commit on all files
make -f build/code-quality.mk check

# Clean cache files
make -f build/code-quality.mk clean
```

### Testing

```bash
# Run all tests
PYTHONPATH=/home/ember/zulip-llm-bot/bots python -m pytest bots/pc_server/tests/

# Run single test file
PYTHONPATH=/home/ember/zulip-llm-bot/bots python -m pytest bots/pc_server/tests/test_gitlab_tools.py

# Run single test method
PYTHONPATH=/home/ember/zulip-llm-bot/bots python -m pytest bots/pc_server/tests/test_gitlab_tools.py::TestGitLabTools::test_tool_registration -v
```

### Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f zulip-bot-testbot1

# Restart a service
docker-compose restart zulip-bot-testbot1

# Stop all services
docker-compose down

# Rebuild and restart a service
docker-compose up -d --build zulip-bot-testbot1
```

**Services:**
- `postgres` - PostgreSQL database for LiteLLM persistence
- `litellm` - LiteLLM proxy server (http://localhost:4000)
- `ollama` - Local LLM runner
- `zulip-bot-testbot1` - Main bot instance
- `zulip-bot-testbot1-pc` - PC sidecar for tools/memory

---

## Code Style Guidelines

### Environment

**Critical**: Code quality tools use **Conda base** environment (not Docker)

```bash
export PATH="/home/ember/miniconda3/bin:$PATH"
conda run -n base python --version  # Python 3.11
```

| Tool | Purpose | Config File |
|------|---------|-------------|
| **Black** | Code formatter | `pyproject.toml` |
| **isort** | Import sorting | `pyproject.toml` |
| **Flake8** | Style guide enforcement | `.flake8` |
| **Bandit** | Security vulnerability scanner | CLI args |
| **Mypy** | Static type checking | `pyproject.toml` |
| **Interrogate** | Docstring coverage | `pyproject.toml` |

### Formatting

- **Line length**: 100 characters max (Black + isort), Flake8 allows 120
- **Target Python**: 3.11
- **Formatter**: Black (`pyproject.toml` configured)
- **Import sorter**: isort (profile: black)

### Import Order

```python
# 1. Standard library
import os
from typing import Dict, Any, Optional

# 2. Third-party
import requests
from flask import Blueprint

# 3. Local (absolute imports only)
from pc_server.memory_manager import MemoryManager
from src.commands.base import BaseCommand
```

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Classes | PascalCase | `class PolicyEngine:` |
| Functions | snake_case | `def load_policy():` |
| Variables | snake_case | `stream_name` |
| Constants | UPPER_SNAKE_CASE | `MAX_ITERATIONS = 10` |
| Private | _leading_underscore | `_internal_helper()` |
| TypeVars | PascalCase, _co/_contra suffix | `T_co`, `T_contra` |

### Type Hints

Required for all function signatures:

```python
def process_message(
    content: str,
    user_id: int,
    optional_param: Optional[str] = None
) -> Dict[str, Any]:
    """Process a message.

    Args:
        content: Message content
        user_id: User identifier
        optional_param: Optional parameter

    Returns:
        Dictionary with processing results

    Raises:
        ValueError: When content is empty
    """
    if not content:
        raise ValueError("Content cannot be empty")
    ...
```

### Error Handling

```python
import logging
logger = logging.getLogger(__name__)

try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    return "❌ User-friendly error message"
except Exception as e:
    logger.exception("Unexpected error in operation")
    raise
```

### Docstrings

Use **Google style** with Args/Returns/Raises sections. Minimum 50% coverage enforced.

```python
def function_name(param1: str, param2: int) -> bool:
    """Short description of what the function does.

    Longer description if needed, explaining the purpose,
    behavior, and any important notes.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is empty
        TypeError: When param2 is not an integer
    """
```

---

## Project Structure

```
bots/
├── src/                    # Main bot code
│   ├── main.py             # Entry point - initializes all components
│   ├── zulip_handler.py    # Zulip API interaction, message routing
│   ├── llm_client.py       # LiteLLM integration with tool support
│   ├── pc_client.py        # PC sidecar API client
│   ├── policy_engine.py    # Policy loading and management
│   ├── model_registry.py   # Model configuration management
│   ├── formatters.py       # LLM response formatters
│   ├── admin_commands.py   # Admin command dispatcher
│   ├── commands/           # Modular command implementations
│   │   ├── base.py         # BaseCommand abstract class
│   │   ├── registry.py     # CommandRegistry for dispatch
│   │   ├── channel_commands.py    # /join, /leave
│   │   ├── policy_commands.py     # /policy, /list-policies
│   │   ├── model_commands.py      # /model
│   │   ├── history_commands.py    # /history, /lookback
│   │   ├── pc_commands.py         # /pc (PC control)
│   │   ├── system_commands.py     # /help, /reload, /status
│   │   └── context.py             # CommandContext for execution
│   └── utils/              # Utilities
│       └── security.py     # Security helpers
├── pc_server/              # PC sidecar API
│   ├── api.py              # Flask entry point
│   ├── pc_manager.py       # File/command operations
│   ├── history_manager.py  # Conversation history storage
│   ├── tool_manager.py     # Tool registry wrapper
│   ├── routes/             # API blueprints
│   │   ├── __init__.py     # create_app() factory
│   │   ├── health.py       # Health check endpoint
│   │   ├── tools.py        # Tool listing and execution
│   │   ├── commands.py     # Shell command execution
│   │   ├── files.py        # File management
│   │   ├── history.py      # History storage/retrieval
│   │   ├── keys.py         # API key management
│   │   └── auth.py         # Authentication manager
│   ├── tools/              # Tool implementations
│   │   ├── __init__.py     # Tool registration
│   │   ├── base.py         # Tool dataclass and ToolContext
│   │   ├── registry.py     # ToolRegistry
│   │   ├── file_tools.py   # File operation tools
│   │   ├── command_tools.py # Shell command tools
│   │   ├── system_tools.py # System info tools
│   │   └── web_search_tools.py # Web search integration
│   ├── pc_utils/           # PC utilities
│   │   └── security.py     # Command validation
│   └── tests/              # pytest tests
│       └── test_gitlab_tools.py
├── requirements.txt        # Bot dependencies
├── Dockerfile              # Bot container image
└── Dockerfile.pc           # PC sidecar container image

build/                      # Build scripts & quality tools
├── code-quality.mk         # Make targets for lint/format
└── checks/
    └── check_docs.py       # Docstring consistency checker

config/                     # Bot configurations
├── admins.yml              # Admin users list
├── models.yml              # Global model definitions
├── litellm_config.yml      # LiteLLM proxy config
└── bot1/                   # Bot-specific configs
    ├── policies.yml        # Policy definitions
    └── state.json          # Runtime state (subscriptions, policies)

secrets/                    # Sensitive credentials (NOT in git)
├── zuliprc-*               # Zulip bot credentials
├── litellm.env             # LiteLLM environment (MASTER_KEY)
├── postgres.env            # Database credentials
└── pc.env                  # PC sidecar API key
```

---

## Component Architecture

### Initialization Order

Components in `main.py` initialize in dependency order:

1. **PC Client** (optional) - Provides memory and tool execution
2. **Policy Engine** - Loads policies and model configurations
3. **LLM Client** - Interfaces with LiteLLM, uses PC client for tools
4. **Admin Handler** - Processes DM commands
5. **Zulip Handler** - Main message processing loop

### Policy System

Policies define bot behavior per stream/DM:

```yaml
# config/bot1/policies.yml
policies:
  pc-enabled:
    description: "Assistant with PC capabilities"
    system_prompt: "..."  # Instructions for LLM
    model: "x-ai/grok-4.1-fast"  # LiteLLM model identifier
    temperature: 0.7
    max_tokens: 64000
    triggers:
      mention_required: true  # Only respond to @mentions
      keywords: []  # Optional keyword triggers
    memory:
      enabled: true
      lookback_messages: 100  # History for context
    tools:
      enabled: true
      max_iterations: 50  # Tool call loops
      allowed_tools: [list_files, read_file, ...]
```

### Tool System

Tools are OpenAI-compatible functions the LLM can call:

1. **File Tools**: `list_files`, `read_file`, `write_file`
2. **Command Tools**: `execute_command`, `run_python_script`
3. **System Tools**: `get_system_info`, `check_disk_space`
4. **GitLab Tools**: `itpGitLab_list_directory`, `itpGitLab_read_file`
5. **Web Search**: `web_search` (Tavily integration)

Tool execution flow:
```
1. LLM decides to call tool(s)
2. LLMClient calls PC client API
3. ToolRegistry validates and executes
4. Results returned to LLM for final response
```

### Conversation History

History is stored in PC sidecar with two scopes:

- **Stream/Topic**: Shared history for all users in a Zulip topic
- **Private DM**: Per-user conversation history

Storage locations (in PC container):
- `/pc/history/streams/<stream_id>/<topic>.jsonl`
- `/pc/history/private/<user_email>.jsonl`

---

## Configuration Files

### pyproject.toml

Key configurations:
```toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
warn_return_any = true
ignore_missing_imports = true

[tool.interrogate]
fail-under = 50  # Min 50% docstring coverage

[tool.commitizen]
version = "2.5.3"
changelog_file = "CHANGELOG.md"
```

### .flake8

```ini
[flake8]
max-line-length = 120
extend-ignore = E203, W503, D100, D104
max-complexity = 9
```

### docker-compose.yml

Key services:
- **postgres**: Internal network only (`litellm-internal`)
- **litellm**: Exposed on localhost:4000 only (security critical)
- **ollama**: GPU-enabled local LLM runner
- **bot + pc**: Paired containers per bot instance

---

## Development Workflow

### Pre-Commit Workflow

**MANDATORY**: Run before every commit

```bash
# Full check (recommended)
make -f build/code-quality.mk check

# Or automatically on git commit
git add .
git commit -m "message"
```

**Never** use `git commit --no-verify` to bypass checks.

### Release Process

One-click release with commitizen:

```bash
# 1. Ensure all changes are committed
git status  # should be clean

# 2. One-click release (auto-performs):
#    - Analyze commits to determine version bump
#    - Update version in pyproject.toml
#    - Generate CHANGELOG
#    - Auto-commit
#    - Create git tag
cz bump

# 3. Push to remote
git push origin main --tags
```

**cz bump auto-detects version:**
- `feat:` → minor (2.4.2 → 2.5.0)
- `fix:` → patch (2.4.2 → 2.4.3)
- `BREAKING CHANGE:` → major (2.4.2 → 3.0.0)

**Preview (dry-run):**
```bash
cz bump --dry-run
```

---

## Security Considerations

### API Key Management

- **LiteLLM Master Key**: Stored in `secrets/litellm.env`
- **PC API Key**: Stored in `secrets/pc.env`, rotated via API
- **Zulip Credentials**: Stored in `secrets/zuliprc-*`

### Command Validation

Dangerous commands are blocked in `pc_utils/security.py`:
- `rm -rf`, `mkfs`, `dd`, `> /dev/...`, etc.
- Pattern-based detection before execution

### Network Security

- LiteLLM proxy bound to `127.0.0.1:4000` (localhost only)
- Internal Docker network for service-to-service communication
- API key required for all PC sidecar endpoints (except health)

### Tool Permissions

- Tools have `dangerous` and `allowed_by_default` flags
- Policy defines `allowed_tools` list
- Granular control per stream/DM via policy assignment

---

## Key Principles

1. **No noqa/type:ignore**: Fix issues, don't bypass them
2. **Absolute imports**: Use full module paths (no relative imports)
3. **Fail fast**: Validate inputs early, raise specific exceptions
4. **Log everything**: Use appropriate levels (debug/info/warning/error)
5. **Test coverage**: Write tests for new functionality
6. **No bare except**: Always catch specific exception types

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Conda not found | `export PATH="/home/ember/miniconda3/bin:$PATH"` |
| Import errors in tests | Use `PYTHONPATH=/home/ember/zulip-llm-bot/bots` prefix |
| Black formatting conflicts | Accept Black's output (consistency > preference) |
| pre-commit fails | Run `make -f build/code-quality.mk format` first |
| Docker service fails to start | Check `secrets/` files exist and are valid |
| Bot cannot connect to Zulip | Verify `secrets/zuliprc-*` credentials |
| Import errors after refactor | Check `__init__.py` files exist in packages |

---

## Multi-Bot Deployment Template

To add a second bot instance (e.g., "coder"):

1. **Create config directory**:
   ```bash
   mkdir config/coder
   cp config/bot1/policies.yml config/coder/
   # Edit policies.yml for bot-specific behavior
   ```

2. **Create secrets file**:
   ```bash
   # Create secrets/zuliprc-coder with bot credentials
   ```

3. **Add to docker-compose.yml** (see commented template in file):
   - `zulip-bot-coder` service
   - `zulip-bot-coder-pc` service
   - `zulip-bot-coder-pc-data` volume

4. **Start new bot**:
   ```bash
   docker-compose up -d zulip-bot-coder zulip-bot-coder-pc
   ```
