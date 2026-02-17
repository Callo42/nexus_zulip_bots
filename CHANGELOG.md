# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2.5.3 (2026-02-15)

### Refactor

- use docker named volumes for postgres and ollama data

## 2.5.2 (2026-02-15)

## 2.5.1 (2026-02-13)

### Fix

- correct parameter name in history storage calls

## 2.5.0 (2026-02-13)

### Feat

- integrate cz bump for automated releases

## v2.4.2 (2026-02-13)

### Feat

- integrate commitizen for conventional commit validation
- add auto-generated CHANGELOG in pre-commit

## [2.4.1] - 2026-02-13

### Changed

- update CHANGELOG for v2.4.0 and v2.4.1 releases
- reduce function complexity to comply with flake8 C901 (max 9)
- consolidate memory system into conversation history

### Fixed

- resolve audit-logs 500 error and lint configuration

## [2.4.0] - 2026-02-12

### Changed

- add comprehensive docstrings and migrate check script
- fix CHANGELOG version mismatch - add missing v2.3.0 section
- update CHANGELOG with recent changes since v2.2.0

## [2.3.0] - 2026-02-12

### Added

- improve user identification, fix duplicate storage, and add code quality tools

### Changed

- simplify AGENTS.md to quick reference format
- eliminate all flake8 and mypy bypasses
- fix code quality issues across codebase
- rename pc/utils to pc_utils and add TypeGuard for mypy compliance
- fix flake8 errors and remove unused imports

## [2.2.0] - 2026-02-11

### Changed

- Archive refactor-todo.md to archive/
- Complete 5-Phase Modularization
- migrate doc consistency checker to .agents/skills/

### Fixed

- resolve import errors after 5-phase modularization refactor

## [2.1.0] - 2026-02-11

### Added

- add Tavily web search tool and refactor secrets configuration

### Changed

- update CHANGELOG for v2.1.0 release
- 添加 Project Todo List 章节并更新待办事项

### Fixed

- add missing litellm.env to bot service env_file

## [2.0.9] - 2026-02-11

### Added

- add x-ai/grok-4.1-fast model and set as default
- add DM lookback support and fix model storage command
- add observability commands and hierarchical help system
- Add timestamps to historical messages in LLM context
- add dynamic lookback configuration and decouple storage from response
- add memory clearing commands and update bot identity
- enhance search with multi-type document support and LLM-driven query processing
- add Zulip platform context to system prompt
- enhance GitLab tools with recursive README indexing and multi-layer security
- hide reasoning content from user responses while preserving API capability

### Changed

- Fix /pc clear command and clean up help system
- refactor AGENTS.md and add comprehensive docstrings
- simplify memory configuration - remove storage limits
- streamline system prompt for pc-enabled policy
- switch pc-enabled policy to gemini-3-pro-preview-thinking and update model configs

### Fixed

- add TZ environment variable for Asia/Shanghai timezone

## [2.0-deepseek开发最终版] - 2026-02-09

### Added

- add GitLab tools for ITP groupmeeting repository access
- add PC tool support for LLM responses in channels
- enhance PC sidecar security with 5-layer protection and audit logging
- Add PC sidecar system for persistent storage and command execution

### Changed

- improve tool error handling and security limits
- Update model configuration to use openrouter/deepseek/deepseek-v3.2
- add todo.txt to version control
- improve bot interaction with @mentions and context management
- add high-priority reminder to update AGENTS.md after code changes
- Update pc-enabled policy system prompt for tool calling architecture
- Migrate from XML tag tools to PC-centered agentic architecture
- Add admin DM conversation support with policy switching
- update docker-compose commands to docker compose

### Fixed

- run bot as module for package imports

### Security

- remove hardcoded credentials, rotate all secrets, and update environment configuration
- simplify pc-enabled policy system prompt, remove security model details and strengthen non-disclosure
- prevent system prompt leaks and simplify PC tool handling
