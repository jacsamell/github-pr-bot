# AI-Powered PR Bot

🤖 Intelligent pull request analysis, review, and auto-approval using Claude AI

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-AI--Powered%20PR%20Bot-blue.svg?colorA=24292e&colorB=0366d6&style=flat&longCache=true&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAM6wAADOsB5dZE0gAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAERSURBVCiRhZG/SsMxFEZPfsVJ61jbxaF0cRQRcRJ9hlYn30IHN/+9iquDCOIsblIrOjqKgy5aKoJQj4n3EX8DY7ECnEMOeQf+c9/hGtlRsuUiEd3yAAYA4Dr4++2q7dMFNE7dmNBKY0BSk5sehqPfekNzKG0+Qi3GG734+O3zwVwpPy2s2HnP+p7Xh8+dSoGg2XrTg/HcNTDajqHoDdDqNLAqFwTjZm56UCEk6dSBRqDGYSUOu66Zg+I2fNZs/M3/f/Grl/XnyF1Gw3VKCez0PN5IUfFLqvgUN4C0qNqYs5YhPL+aVZYDE4IpUk57oSFnJm4FyCqqOE0jhY2SMyLFoo56zyo6becOS5UVDdj7Vih0zp+tcMhwRpBeLyqtIjlJBFdqyoJuAn9MSL9CCVpkTx/9qAAAAABJRU5ErkJggg==)](https://github.com/marketplace/actions/ai-powered-pr-bot)

Transform your pull request workflow with AI-powered automation that provides intelligent code reviews, generates comprehensive descriptions, and safely auto-approves quality changes.

> **License Notice:** Modified version of [PR-Agent](https://github.com/Codium-ai/pr-agent) by Codium AI, licensed under AGPL v3. [Source code available here](https://github.com/jacsamell/github-pr-bot).

## Features

- **Auto Description** - Generates PR titles, summaries, and labels
- **Auto Review** - Provides detailed code feedback and security analysis  
- **Code Suggestions** - Offers specific improvements and best practices
- **Auto Approval** - Safely approves PRs that meet quality criteria
- **Smart Triggers** - Runs on PR events or manual `##prbot` trigger

## 🚀 Quick Setup

### Basic Usage

```yaml
name: AI PR Bot
on:
  pull_request:
    types: [opened, reopened, ready_for_review, synchronize]

jobs:
  ai-pr-bot:
    runs-on: ubuntu-latest
    steps:
      - uses: jacsamell/github-pr-bot@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          auto_review: true
          auto_describe: true
          enable_auto_approval: false
```

### Advanced Configuration

```yaml
name: AI PR Bot
on:
  pull_request:
    types: [opened, reopened, ready_for_review, synchronize]

jobs:
  ai-pr-bot:
    runs-on: ubuntu-latest
    steps:
      - uses: jacsamell/github-pr-bot@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_review: true
          auto_describe: true
          auto_improve: true
          enable_auto_approval: true
          model: 'anthropic/claude-sonnet-4-20250514'
          max_model_tokens: '100000'
          require_trigger: false
```

### Required Secrets

Add these secrets in your repository settings (Settings → Secrets and variables → Actions):

| Secret | Description | Required |
|--------|-------------|----------|
| `ANTHROPIC_API_KEY` | Your Claude API key from Anthropic | ✅ Yes |

## 📋 Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `anthropic_api_key` | Anthropic API key for Claude AI | ✅ Yes | - |
| `github_token` | GitHub token for API access | ❌ No | `${{ github.token }}` |
| `auto_review` | Enable automatic code review | ❌ No | `true` |
| `auto_describe` | Enable automatic PR description generation | ❌ No | `true` |
| `auto_improve` | Enable code improvement suggestions | ❌ No | `true` |
| `enable_auto_approval` | Enable automatic approval of safe changes | ❌ No | `false` |
| `model` | AI model to use | ❌ No | `anthropic/claude-sonnet-4-20250514` |
| `max_model_tokens` | Maximum tokens for AI model | ❌ No | `100000` |
| `require_trigger` | Require ##prbot trigger in PR description | ❌ No | `false` |

## 📤 Outputs

| Output | Description |
|--------|-------------|
| `review_posted` | Whether a review was posted |
| `description_updated` | Whether PR description was updated |
| `improvements_posted` | Whether improvement suggestions were posted |
| `auto_approved` | Whether PR was automatically approved |

### Optional Configuration File

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

## 🔒 Security & Privacy

- **API Keys**: Your Anthropic API key is securely handled through GitHub Secrets
- **Code Privacy**: Code is only sent to Anthropic's Claude API for analysis
- **No Storage**: No code or data is permanently stored by this action
- **Permissions**: Only requires standard GitHub token permissions for PR operations

## 🤝 Contributing

Contributions are welcome! This project is based on [PR-Agent](https://github.com/Codium-ai/pr-agent) and maintains AGPL v3 licensing.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under AGPL v3 - see the [LICENSE](LICENSE) file for details.

Based on [PR-Agent](https://github.com/Codium-ai/pr-agent) by Codium AI.

## 🆘 Support

- 📖 [Documentation](https://github.com/jacsamell/github-pr-bot)
- 🐛 [Report Issues](https://github.com/jacsamell/github-pr-bot/issues)
- 💬 [Discussions](https://github.com/jacsamell/github-pr-bot/discussions)

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


