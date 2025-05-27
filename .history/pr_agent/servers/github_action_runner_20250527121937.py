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
from pr_agent.log import get_logger
from pr_agent.tools.pr_code_suggestions import PRCodeSuggestions
from pr_agent.tools.pr_description import PRDescription
from pr_agent.tools.pr_reviewer import PRReviewer


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
    auto_improve = get_setting_or_env("GITHUB_ACTION_CONFIG.AUTO_IMPROVE", True)

    # Configure for auto mode
    get_settings().config.is_auto_command = True
    get_settings().pr_description.final_update_message = False

    get_logger().info(f"Running GitHub PR Bot: describe={auto_describe}, review={auto_review}, improve={auto_improve}")

    # Run enabled tools
    try:
        if is_true(auto_describe):
            await PRDescription(pr_url).run()
        if is_true(auto_review):
            await PRReviewer(pr_url).run()
        if is_true(auto_improve):
            await PRCodeSuggestions(pr_url).run()
    except Exception as e:
        get_logger().error(f"Error running GitHub PR Bot tools: {e}")
        raise


async def run_action():
    """Main entry point for GitHub PR Bot runner."""
    # Validate required environment variables
    required_env_vars = {
        'GITHUB_EVENT_NAME': os.environ.get('GITHUB_EVENT_NAME'),
        'GITHUB_EVENT_PATH': os.environ.get('GITHUB_EVENT_PATH'),
        'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN')
    }
    
    for var_name, var_value in required_env_vars.items():
        if not var_value:
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
    except (json.JSONDecodeError, FileNotFoundError) as e:
        get_logger().error(f"Failed to load event payload: {e}")
        return

    # Apply repository-specific settings
    try:
        pr_url = event_payload.get("pull_request", {}).get("html_url")
        if pr_url:
            apply_repo_settings(pr_url)
            get_logger().info("Repository settings applied successfully")
    except Exception as e:
        get_logger().warning(f"Failed to apply repo settings: {e}")

    # Handle pull request events only
    event_name = required_env_vars['GITHUB_EVENT_NAME']
    
    try:
        if event_name in ["pull_request", "pull_request_target"]:
            await handle_pull_request_event(event_payload)
        else:
            get_logger().info(f"Unsupported event type: {event_name}")
    except Exception as e:
        get_logger().error(f"Error processing {event_name} event: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(run_action())
