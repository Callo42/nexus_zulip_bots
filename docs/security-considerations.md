# Security Considerations

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
