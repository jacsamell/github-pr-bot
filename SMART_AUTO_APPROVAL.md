# 🤖 Smart Auto-Approval for PR-Agent

This enhanced version of PR-Agent includes intelligent auto-approval functionality based on AI-generated confidence, complexity, and security scores.

## ✨ Features

### **Custom AI Scoring**
- **Confidence Score (1-100)**: How certain the AI is about its analysis
- **Complexity Score (1-10)**: How complex the code changes are
- **Security Score (1-10)**: How secure the changes are (10 = very secure)
- **Auto-Approval Recommendation**: AI's recommendation for auto-approval

### **Smart Decision Logic**
The system automatically approves PRs that meet ALL criteria:
- ✅ High AI confidence (≥85%)
- ✅ Low complexity (≤5/10)
- ✅ High security (≥8/10)
- ✅ Low review effort (≤3/5)
- ✅ Small change size (≤200 lines, ≤5 files)
- ✅ Few issues found (≤3)
- ✅ No critical security concerns

## 🚀 Quick Start

### 1. Setup API Keys
Add to your repository secrets:
```bash
ANTHROPIC_API_KEY=your_anthropic_key_here
GITHUB_TOKEN=automatic  # Provided by GitHub
```

### 2. Configure Auto-Approval
Edit `.pr_agent.toml`:
```toml
[config]
enable_auto_approval = true

# Adjust thresholds to your preferences
auto_approve_confidence_threshold = 85    # AI confidence (1-100)
auto_approve_complexity_threshold = 5     # Max complexity (1-10)
auto_approve_security_threshold = 8       # Min security score (1-10)
auto_approve_effort_threshold = 3         # Max effort score (1-5)
auto_approve_max_files = 5               # Max files changed
auto_approve_max_lines = 200             # Max total lines changed
auto_approve_max_issues = 3              # Max issues found
```

### 3. Add GitHub Workflow
Copy `.github/workflows/smart-pr-agent.yml` to your repository.

### 4. Test It!
Create a small PR and watch the magic happen! 🎉

## 📊 How It Works

### **Analysis Phase**
1. AI analyzes the PR diff and generates custom scores
2. System extracts PR metrics (files, lines, author, etc.)
3. Decision engine evaluates all criteria

### **Decision Phase**
```
Auto-Approval Criteria (ALL must pass):
├─ 🧠 Confidence ≥ 85/100
├─ 🔧 Complexity ≤ 5/10
├─ 🔒 Security ≥ 8/10
├─ ⏱️ Effort ≤ 3/5
├─ 📁 Files ≤ 5
├─ 📝 Lines ≤ 200
├─ ⚠️ Issues ≤ 3
└─ 🚫 No critical issues
```

### **Action Phase**
- ✅ **Auto-Approve**: Meets all criteria → PR approved automatically
- 🔍 **Manual Review**: Fails criteria → Comment with detailed reasoning

## ⚙️ Configuration Options

### **Confidence Threshold** (1-100)
```toml
auto_approve_confidence_threshold = 85
```
- `90+`: Very strict - only approve when AI is extremely confident
- `85`: Recommended default - good balance
- `70-`: Lenient - may approve with lower AI confidence

### **Complexity Threshold** (1-10)
```toml
auto_approve_complexity_threshold = 5
```
- `3`: Very strict - only simple changes
- `5`: Recommended default - moderate complexity allowed
- `7+`: Lenient - allows more complex changes

### **Security Threshold** (1-10)
```toml
auto_approve_security_threshold = 8
```
- `9+`: Very strict - highest security requirements
- `8`: Recommended default - good security standard
- `6-`: Lenient - may approve with security concerns

### **Size Limits**
```toml
auto_approve_max_files = 5     # Max files changed
auto_approve_max_lines = 200   # Max total lines changed
```

## 🎯 Example Scenarios

### ✅ **Auto-Approved**: Documentation Update
```yaml
review:
  confidence_score_[1-100]: 95
  complexity_score_[1-10]: 2
  security_score_[1-10]: 10
  auto_approve_recommendation: true
  key_issues_to_review: []
```
**Result**: Auto-approved (documentation-only, very safe)

### ✅ **Auto-Approved**: Simple Bug Fix
```yaml
review:
  confidence_score_[1-100]: 88
  complexity_score_[1-10]: 4
  security_score_[1-10]: 9
  auto_approve_recommendation: true
  key_issues_to_review: [{"issue_header": "Minor Style"}]
```
**Result**: Auto-approved (small, confident fix)

### ❌ **Manual Review**: Complex Feature
```yaml
review:
  confidence_score_[1-100]: 75
  complexity_score_[1-10]: 8
  security_score_[1-10]: 7
  auto_approve_recommendation: false
  key_issues_to_review: [
    {"issue_header": "Possible Bug"},
    {"issue_header": "Performance Concern"}
  ]
```
**Result**: Manual review required (too complex, low confidence)

## 🔧 CLI Usage

### **Auto-Approval Mode**
```bash
python -m pr_agent.cli --pr_url="https://github.com/user/repo/pull/123" review auto_approve
```

### **Review Only** (No Auto-Approval)
```bash
python -m pr_agent.cli --pr_url="https://github.com/user/repo/pull/123" review
```

### **Configuration Override**
```bash
export config.auto_approve_confidence_threshold=90
export config.auto_approve_max_lines=100
python -m pr_agent.cli --pr_url="..." review auto_approve
```

## 🛡️ Safety Features

### **Multiple Safety Layers**
1. **AI Analysis**: Detailed code review with scoring
2. **Size Limits**: Prevents approval of large changes
3. **Critical Issue Detection**: Blocks PRs with security/error issues
4. **Configurable Thresholds**: Adjust strictness to your needs
5. **Fallback Mode**: Falls back to review-only if auto-approval fails

### **Critical Issue Detection**
Automatically blocks auto-approval for issues containing:
- `critical`, `error`, `bug`, `security`, `fail`

### **Security Scanning**
- Analyzes for SQL injection, XSS, CSRF vulnerabilities
- Checks for exposed secrets/API keys
- Evaluates authentication and authorization logic

## 🔍 Troubleshooting

### **Auto-Approval Not Working?**
1. Check `enable_auto_approval = true` in config
2. Verify API keys are set correctly
3. Review threshold settings (may be too strict)
4. Check workflow file is properly configured

### **Too Many False Positives?**
Adjust thresholds to be more lenient:
```toml
auto_approve_confidence_threshold = 80    # Lower from 85
auto_approve_complexity_threshold = 6     # Higher from 5
auto_approve_max_lines = 300             # Higher from 200
```

### **Too Many False Negatives?**
Adjust thresholds to be stricter:
```toml
auto_approve_confidence_threshold = 90    # Higher from 85
auto_approve_complexity_threshold = 4     # Lower from 5
auto_approve_max_issues = 1              # Lower from 3
```

## 🤝 Contributing

Want to improve the auto-approval logic? 

1. **Fork the repository**
2. **Modify the scoring logic** in `pr_agent/tools/pr_reviewer.py`
3. **Update thresholds** in `pr_agent/settings/configuration.toml`
4. **Test thoroughly** with various PR types
5. **Submit a pull request**

## 📈 Monitoring & Analytics

### **Success Metrics to Track**
- Auto-approval rate (target: 20-40% for most repos)
- False positive rate (auto-approved but shouldn't be)
- False negative rate (should auto-approve but didn't)
- Time saved on reviews
- Developer satisfaction

### **Logging**
Enable debug logging to see decision details:
```toml
[config]
log_level = "DEBUG"
verbosity_level = 2
```

---

## 🎉 **You're All Set!**

Your PR-Agent now has intelligent auto-approval capabilities! Start with conservative thresholds and adjust based on your team's needs and experience.

**Happy reviewing!** 🚀 