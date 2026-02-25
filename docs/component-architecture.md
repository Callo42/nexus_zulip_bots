# Component Architecture

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
