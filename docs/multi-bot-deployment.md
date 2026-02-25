# Multi-Bot Deployment Template

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
