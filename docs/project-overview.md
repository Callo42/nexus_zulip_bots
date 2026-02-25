# Project Overview

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
