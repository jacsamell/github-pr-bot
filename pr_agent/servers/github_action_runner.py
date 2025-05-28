#!/usr/bin/env python3
"""
GitHub PR Bot - GitHub Action Runner

This is a modified version of PR-Agent by Codium AI (https://github.com/Codium-ai/pr-agent)
Modified on 2025-01-27 for company use as "GitHub PR Bot"
Licensed under GNU Affero General Public License v3.0 (AGPL-3.0)
Source code: https://github.com/jacsamell/github-pr-bot
"""

import asyncio
import json
import os
from typing import Union

from pr_agent.config_loader import get_settings
from pr_agent.git_providers.utils import apply_repo_settings
from pr_agent.log import LoggingFormat, get_logger, setup_logger
from pr_agent.tools.pr_code_suggestions import PRCodeSuggestions
from pr_agent.tools.pr_description import PRDescription
from pr_agent.tools.pr_reviewer import PRReviewer

# Set up logging format based on environment variable
pretty_logs = os.getenv('GITHUB_ACTION_CONFIG.PRETTY_LOGS', 'true').lower() == 'true'
log_format = LoggingFormat.CONSOLE if pretty_logs else LoggingFormat.JSON
setup_logger(fmt=log_format, level=get_settings().get("CONFIG.LOG_LEVEL", "INFO"))


def is_true(value: Union[str, bool]) -> bool:
    """Convert string or boolean to boolean value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == 'true'
    return False


def get_setting_or_env(key: str, default: Union[str, bool] = None) -> Union[str, bool]:
    """Get setting from config or environment variable with fallback."""
    try:
        return get_settings().get(key, default)
    except AttributeError:
        return (os.getenv(key) or 
                os.getenv(key.upper()) or 
                os.getenv(key.lower()) or 
                default)


async def handle_pull_request_event(event_payload: dict) -> None:
    """Handle pull request events (opened, reopened, synchronize, etc.)."""
    action = event_payload.get("action")
    pr_actions = get_settings().get("GITHUB_ACTION_CONFIG.PR_ACTIONS", 
                                   ["opened", "reopened", "ready_for_review", "synchronize"])

    if action not in pr_actions:
        get_logger().info(f"Skipping action: {action}")
        return

    pr_url = event_payload.get("pull_request", {}).get("url")
    if not pr_url:
        get_logger().error("No PR URL found in event payload")
        return

    # Check if PR is draft and if we should process draft PRs
    pull_request = event_payload.get("pull_request", {})
    is_draft = pull_request.get("draft", False)
    feedback_on_draft_pr = get_setting_or_env("CONFIG.FEEDBACK_ON_DRAFT_PR", False)
    if is_draft and not is_true(feedback_on_draft_pr):
        if pretty_logs:
            get_logger().info(f"⏭️ Ignoring draft PR (set feedback_on_draft_pr=true to process draft PRs)")
        else:
            get_logger().info(f"Ignoring draft PR (set feedback_on_draft_pr=true to process draft PRs)")
        return

    # Check for ##prbot trigger if required
    require_trigger = get_setting_or_env("GITHUB_ACTION_CONFIG.REQUIRE_AIDESC_TRIGGER", False)
    if is_true(require_trigger):
        pr_body = event_payload.get("pull_request", {}).get("body", "") or ""
        if "##prbot" not in pr_body.lower():
            get_logger().info("Skipping: ##prbot trigger not found in PR description")
            return
        get_logger().info("##prbot trigger found, proceeding with GitHub PR Bot actions")

    # Get auto-action settings
    auto_describe = get_setting_or_env("GITHUB_ACTION_CONFIG.AUTO_DESCRIBE", True)
    auto_review = get_setting_or_env("GITHUB_ACTION_CONFIG.AUTO_REVIEW", True)
    auto_improve = get_setting_or_env("GITHUB_ACTION_CONFIG.AUTO_IMPROVE", False)  # Default to False to avoid unwanted runs
    
    # Debug logging to see what values we're getting
    if pretty_logs:
        get_logger().info(f"🔧 Configuration: auto_describe={auto_describe}, auto_review={auto_review}, auto_improve={auto_improve}")
    else:
        get_logger().info(f"Configuration: auto_describe={auto_describe}, auto_review={auto_review}, auto_improve={auto_improve}")

    # Configure for auto mode
    get_settings().config.is_auto_command = True
    get_settings().pr_description.final_update_message = False

    # Use emojis only if pretty logs are enabled
    if pretty_logs:
        get_logger().info(f"🤖 Running GitHub PR Bot: describe={auto_describe}, review={auto_review}, improve={auto_improve}")
    else:
        get_logger().info(f"Running GitHub PR Bot: describe={auto_describe}, review={auto_review}, improve={auto_improve}")

    # Run enabled tools
    try:
        if is_true(auto_describe):
            if pretty_logs:
                get_logger().info("📝 Generating PR description...")
            else:
                get_logger().info("Generating PR description...")
            await PRDescription(pr_url).run()
            if pretty_logs:
                get_logger().info("✅ PR description completed")
            else:
                get_logger().info("PR description completed")
            
        if is_true(auto_review):
            # Check if auto-approval is enabled
            enable_auto_approval = get_setting_or_env("CONFIG.ENABLE_AUTO_APPROVAL", False)
            
            if is_true(enable_auto_approval):
                if pretty_logs:
                    get_logger().info("🔍 Reviewing PR with auto-approval...")
                else:
                    get_logger().info("Reviewing PR with auto-approval...")
                await PRReviewer(pr_url, args=['auto_approve']).run()
            else:
                if pretty_logs:
                    get_logger().info("🔍 Reviewing PR...")
                else:
                    get_logger().info("Reviewing PR...")
                await PRReviewer(pr_url).run()
                
            if pretty_logs:
                get_logger().info("✅ PR review completed")
            else:
                get_logger().info("PR review completed")
            
        if is_true(auto_improve):
            if pretty_logs:
                get_logger().info("💡 Generating code suggestions...")
            else:
                get_logger().info("Generating code suggestions...")
            try:
                await PRCodeSuggestions(pr_url).run()
                if pretty_logs:
                    get_logger().info("✅ Code suggestions completed")
                else:
                    get_logger().info("Code suggestions completed")
            except Exception as e:
                if pretty_logs:
                    get_logger().error(f"❌ Code suggestions failed: {e}")
                else:
                    get_logger().error(f"Code suggestions failed: {e}")
                # Don't re-raise the exception to avoid stopping other tools
        else:
            if pretty_logs:
                get_logger().info("⏭️ Code suggestions disabled, skipping...")
            else:
                get_logger().info("Code suggestions disabled, skipping...")
            
        if pretty_logs:
            get_logger().info("🎉 GitHub PR Bot analysis complete!")
        else:
            get_logger().info("GitHub PR Bot analysis complete!")
    except Exception as e:
        if pretty_logs:
            get_logger().error(f"❌ Error running GitHub PR Bot tools: {e}")
        else:
            get_logger().error(f"Error running GitHub PR Bot tools: {e}")
        raise


async def run_action():
    """Main entry point for GitHub PR Bot runner."""
    if pretty_logs:
        get_logger().info("🚀 Starting GitHub PR Bot...")
    else:
        get_logger().info("Starting GitHub PR Bot...")
    
    # Validate required environment variables
    required_env_vars = {
        'GITHUB_EVENT_NAME': os.environ.get('GITHUB_EVENT_NAME'),
        'GITHUB_EVENT_PATH': os.environ.get('GITHUB_EVENT_PATH'),
        'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN')
    }
    
    for var_name, var_value in required_env_vars.items():
        if not var_value:
            if pretty_logs:
                get_logger().error(f"❌ Required environment variable {var_name} not set")
            else:
                get_logger().error(f"Required environment variable {var_name} not set")
            return

    # Set up API keys if provided
    openai_key = os.environ.get('OPENAI_KEY') or os.environ.get('OPENAI.KEY')
    openai_org = os.environ.get('OPENAI_ORG') or os.environ.get('OPENAI.ORG')
    
    if openai_key:
        get_settings().set("OPENAI.KEY", openai_key)
    if openai_org:
        get_settings().set("OPENAI.ORG", openai_org)

    # Configure GitHub deployment
    get_settings().set("GITHUB.DEPLOYMENT_TYPE", "user")
    enable_output = get_setting_or_env("GITHUB_ACTION_CONFIG.ENABLE_OUTPUT", True)
    get_settings().set("GITHUB_ACTION_CONFIG.ENABLE_OUTPUT", enable_output)

    # Load and parse event payload
    try:
        with open(required_env_vars['GITHUB_EVENT_PATH'], 'r') as f:
            event_payload = json.load(f)
        if pretty_logs:
            get_logger().info("📄 Event payload loaded successfully")
        else:
            get_logger().info("Event payload loaded successfully")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        if pretty_logs:
            get_logger().error(f"❌ Failed to load event payload: {e}")
        else:
            get_logger().error(f"Failed to load event payload: {e}")
        return

    # Apply repository-specific settings
    try:
        pr_url = event_payload.get("pull_request", {}).get("html_url")
        if pr_url:
            if pretty_logs:
                get_logger().info(f"🔧 Applying repository settings for: {pr_url}")
            else:
                get_logger().info(f"Applying repository settings for: {pr_url}")
            apply_repo_settings(pr_url)
            if pretty_logs:
                get_logger().info("✅ Repository settings applied successfully")
            else:
                get_logger().info("Repository settings applied successfully")
    except Exception as e:
        if pretty_logs:
            get_logger().warning(f"⚠️ Failed to apply repo settings: {e}")
        else:
            get_logger().warning(f"Failed to apply repo settings: {e}")

    # Handle pull request events only
    event_name = required_env_vars['GITHUB_EVENT_NAME']
    
    try:
        if event_name in ["pull_request", "pull_request_target"]:
            if pretty_logs:
                get_logger().info(f"🎯 Processing {event_name} event...")
            else:
                get_logger().info(f"Processing {event_name} event...")
            await handle_pull_request_event(event_payload)
        else:
            if pretty_logs:
                get_logger().info(f"ℹ️ Unsupported event type: {event_name}")
            else:
                get_logger().info(f"Unsupported event type: {event_name}")
    except Exception as e:
        if pretty_logs:
            get_logger().error(f"❌ Error processing {event_name} event: {e}")
        else:
            get_logger().error(f"Error processing {event_name} event: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(run_action())
