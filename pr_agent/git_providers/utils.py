import copy
import os
import tempfile
from pathlib import Path

from dynaconf import Dynaconf
from starlette_context import context

from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider_with_context
from pr_agent.log import get_logger
from pr_agent.algo.cursor_claude_rules import CursorRulesHandler


def apply_repo_settings(pr_url):
    os.environ["AUTO_CAST_FOR_DYNACONF"] = "false"
    git_provider = get_git_provider_with_context(pr_url)
    
    # First, try to load local .pr_agent.toml file if it exists
    local_pr_agent_toml = Path(__file__).parent.parent.parent / ".pr_agent.toml"
    if local_pr_agent_toml.exists():
        try:
            get_settings().load_file(str(local_pr_agent_toml))
            get_logger().info(f"Loaded local .pr_agent.toml from {local_pr_agent_toml}")
        except Exception as e:
            get_logger().warning(f"Failed to load local .pr_agent.toml: {e}")
    
    if get_settings().config.use_repo_settings_file:
        repo_settings_file = None
        try:
            try:
                repo_settings = context.get("repo_settings", None)
            except Exception:
                repo_settings = None
                pass
            if repo_settings is None:  # None is different from "", which is a valid value
                repo_settings = git_provider.get_repo_settings()
                try:
                    context["repo_settings"] = repo_settings
                except Exception:
                    pass

            error_local = None
            if repo_settings:
                repo_settings_file = None
                category = 'local'
                try:
                    fd, repo_settings_file = tempfile.mkstemp(suffix='.toml')
                    os.write(fd, repo_settings)
                    new_settings = Dynaconf(settings_files=[repo_settings_file])
                    for section, contents in new_settings.as_dict().items():
                        section_dict = copy.deepcopy(get_settings().as_dict().get(section, {}))
                        for key, value in contents.items():
                            section_dict[key] = value
                        get_settings().unset(section)
                        get_settings().set(section, section_dict, merge=False)
                    get_logger().info(f"Applying repo settings:\n{new_settings.as_dict()}")
                except Exception as e:
                    get_logger().warning(f"Failed to apply repo {category} settings, error: {str(e)}")
                    error_local = {'error': str(e), 'settings': repo_settings, 'category': category}

                if error_local:
                    handle_configurations_errors([error_local], git_provider)
        except Exception as e:
            get_logger().exception("Failed to apply repo settings", e)
        finally:
            if repo_settings_file:
                try:
                    os.remove(repo_settings_file)
                except Exception as e:
                    get_logger().error(f"Failed to remove temporary settings file {repo_settings_file}", e)

    # enable switching models with a short definition
    if get_settings().config.model.lower() == 'claude-3-5-sonnet':
        set_claude_model()
    
    # Load Cursor rules from repository if enabled
    if get_settings().config.get('use_cursor_rules', True):
        try:
            rules_handler = CursorRulesHandler(git_provider)
            if rules_handler.load_rules_from_repo():
                # Store rules in context for use in prompts
                try:
                    context["cursor_rules"] = rules_handler
                    get_logger().info("Loaded Cursor repository rules")
                except Exception:
                    # If context is not available, store in settings
                    get_settings().set('cursor_rules', rules_handler)
                    get_logger().info("Loaded Cursor repository rules into settings")
        except Exception as e:
            get_logger().debug(f"No Cursor rules found or failed to load: {e}")
    else:
        get_logger().debug("Cursor rules loading is disabled in configuration")


def handle_configurations_errors(config_errors, git_provider):
    try:
        if not any(config_errors):
            return

        for err in config_errors:
            if err:
                configuration_file_content = err['settings'].decode()
                err_message = err['error']
                config_type = err['category']
                header = f"❌ **PR-Agent failed to apply '{config_type}' repo settings**"
                body = f"{header}\n\nThe configuration file needs to be a valid [TOML](https://qodo-merge-docs.qodo.ai/usage-guide/configuration_options/), please fix it.\n\n"
                body += f"___\n\n**Error message:**\n`{err_message}`\n\n"
                if git_provider.is_supported("gfm_markdown"):
                    body += f"\n\n<details><summary>Configuration content:</summary>\n\n```toml\n{configuration_file_content}\n```\n\n</details>"
                else:
                    body += f"\n\n**Configuration content:**\n\n```toml\n{configuration_file_content}\n```\n\n"
                get_logger().warning(f"Sending a 'configuration error' comment to the PR", artifact={'body': body})
                # git_provider.publish_comment(body)
                if hasattr(git_provider, 'publish_persistent_comment'):
                    git_provider.publish_persistent_comment(body,
                                                            initial_header=header,
                                                            update_header=False,
                                                            final_update_message=False)
                else:
                    git_provider.publish_comment(body)
    except Exception as e:
        get_logger().exception(f"Failed to handle configurations errors", e)


def set_claude_model():
    """
    set the claude-sonnet-3.5 model easily (even by users), just by stating: --config.model='claude-3-5-sonnet'
    """
    model_claude = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0"
    get_settings().set('config.model', model_claude)
    get_settings().set('config.model_weak', model_claude)
    get_settings().set('config.fallback_models', [model_claude])


def get_cursor_rules():
    """
    Get the Cursor rules handler from context or settings.
    Returns None if no rules are available.
    """
    try:
        # Try to get from context first
        rules_handler = context.get("cursor_rules", None)
        if rules_handler:
            return rules_handler
    except Exception:
        pass
    
    # Try to get from settings
    try:
        rules_handler = get_settings().get('cursor_rules', None)
        if rules_handler:
            return rules_handler
    except Exception:
        pass
    
    return None


def get_repository_rules_for_prompt():
    """
    Get repository-specific Cursor rules formatted for AI prompts.
    Returns empty string if no rules are available or feature is disabled.
    """
    if not get_settings().config.get('use_cursor_rules', True):
        get_logger().debug("🚫 Cursor rules are disabled in configuration")
        return ""
    
    rules_handler = get_cursor_rules()
    if rules_handler and rules_handler.has_rules():
        rules_content = rules_handler.get_rules_for_prompt()

        # Optionally clip rules to a max token budget to avoid exceeding context
        try:
            from pr_agent.algo.token_handler import TokenHandler
            from pr_agent.algo.utils import get_max_tokens
            model = get_settings().config.model
            token_handler = TokenHandler()
            rules_tokens = token_handler.count_tokens(rules_content)

            max_rules_tokens = int(get_settings().config.get('max_cursor_rules_tokens', 20000))
            hard_cap_ratio = float(get_settings().config.get('cursor_rules_context_ratio', 0.25))
            model_ctx = get_max_tokens(model)
            hard_cap_tokens = max(2000, int(model_ctx * hard_cap_ratio))
            allowed_tokens = min(max_rules_tokens, hard_cap_tokens)

            if rules_tokens > allowed_tokens:
                from pr_agent.algo.utils import clip_tokens
                clipped = clip_tokens(rules_content, allowed_tokens, add_three_dots=True)
                get_logger().warning(
                    f"Cursor rules too large ({rules_tokens} tokens). Clipped to {allowed_tokens} tokens for prompting."
                )
                rules_content = clipped
        except Exception as e:
            get_logger().debug(f"Failed to apply cursor rules token budget: {e}")

        # Count rules size for logging
        rules_size = len(rules_content)
        get_logger().info(f"📋 Including repository Cursor rules in AI prompt ({rules_size:,} characters)")
        return rules_content
    else:
        get_logger().debug("📋 No Cursor rules available for this repository")
        return ""


def add_repository_rules_to_prompt(system_prompt: str) -> str:
    """
    Add repository-specific Cursor rules to a system prompt.
    
    Args:
        system_prompt: The original system prompt
        
    Returns:
        The system prompt with repository rules appended (if any)
    """
    repo_rules = get_repository_rules_for_prompt()
    if repo_rules:
        rules_explanation = """

## Repository Coding Standards

The following are repository-specific coding standards and guidelines that you MUST follow when reviewing this pull request. These rules represent the team's preferred coding practices and standards for this project:

"""
        return system_prompt + rules_explanation + repo_rules + """

When reviewing the PR, ensure that:
1. The code adheres to these repository-specific standards
2. Any violations are flagged in your review
3. Suggestions align with these coding guidelines
4. Auto-approval decisions consider compliance with these rules

"""
    return system_prompt
