# Development Workflow

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
