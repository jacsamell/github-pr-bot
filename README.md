# GitHub PR Bot

AI-powered pull request analysis, review, and auto-approval using Claude.

> **License Notice:** Modified version of [PR-Agent](https://github.com/Codium-ai/pr-agent) by Codium AI, licensed under AGPL v3. [Source code available here](https://github.com/jacsamell/github-pr-bot).

## Features

- **Auto Description** - Generates PR titles, summaries, and labels
- **Auto Review** - Provides detailed code feedback and security analysis  
- **Code Suggestions** - Offers specific improvements and best practices
- **Auto Approval** - Safely approves PRs that meet quality criteria
- **Smart Triggers** - Runs on PR events or manual `##prbot` trigger

## Quick Setup

### 1. Add Workflow

Create `.github/workflows/pr-bot.yml`:

```yaml
name: GitHub PR Bot

on:
  pull_request:
    types: [opened, reopened, ready_for_review, synchronize]

jobs:
  pr-bot:
    uses: jacsamell/github-pr-bot/.github/workflows/pr-bot-reusable.yml@main
    with:
      auto_review: true
      auto_describe: true
      auto_improve: true
      enable_auto_approval: true
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### 2. Add API Key

Go to Settings → Secrets → Actions and add:
- `ANTHROPIC_API_KEY` - Your Claude API key

### 3. Configuration (Optional)

Create `.pr_bot.toml`:

```toml
[config]
model = "anthropic/claude-sonnet-4-20250514"
enable_auto_approval = true
max_model_tokens = 100000

[github_action_config]
require_aidesc_trigger = true  # Requires ##prbot in PR description
auto_describe = true
auto_review = true
auto_improve = true
```

## Usage

### Automatic Mode
- Runs on all PRs (default)
- Or add `##prbot` to PR description if `require_aidesc_trigger = true`

### Manual Commands
- `/review` - Get code review
- `/describe` - Generate PR description  
- `/improve` - Get code suggestions

## Auto-Approval

Automatically approves safe changes:
- ✅ Documentation updates, tests, minor refactoring
- ❌ Critical business logic, security code, database changes

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ANTHROPIC__KEY="your-api-key"
export GITHUB_TOKEN="your-github-token"

# Run on a specific PR
python -m pr_agent.cli --pr_url=https://github.com/owner/repo/pull/123 review
```


