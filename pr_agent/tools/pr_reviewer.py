import copy
import datetime
import traceback
from collections import OrderedDict
from functools import partial
from typing import List, Tuple

from jinja2 import Environment, StrictUndefined

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.algo.pr_processing import (add_ai_metadata_to_diff_files,
                                         get_pr_diff,
                                         retry_with_fallback_models)
from pr_agent.algo.token_handler import TokenHandler
from pr_agent.algo.utils import (ModelType, PRReviewHeader,
                                 convert_to_markdown_v2, github_action_output,
                                 load_yaml, show_relevant_configurations)
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import (get_git_provider,
                                    get_git_provider_with_context)
from pr_agent.git_providers.git_provider import (IncrementalPR,
                                                 get_main_pr_language)
from pr_agent.log import get_logger
from pr_agent.servers.help import HelpMessage
from pr_agent.tools.ticket_pr_compliance_check import (
    extract_and_cache_pr_tickets, extract_tickets)


class PRReviewer:
    """
    The PRReviewer class is responsible for reviewing a pull request and generating feedback using an AI model.
    """

    def __init__(self, pr_url: str, is_answer: bool = False, is_auto: bool = False, args: list = None,
                 ai_handler: partial[BaseAiHandler,] = LiteLLMAIHandler):
        """
        Initialize the PRReviewer object with the necessary attributes and objects to review a pull request.

        Args:
            pr_url (str): The URL of the pull request to be reviewed.
            is_answer (bool, optional): Indicates whether the review is being done in answer mode. Defaults to False.
            is_auto (bool, optional): Indicates whether the review is being done in automatic mode. Defaults to False.
            ai_handler (BaseAiHandler): The AI handler to be used for the review. Defaults to None.
            args (list, optional): List of arguments passed to the PRReviewer class. Defaults to None.
        """
        self.git_provider = get_git_provider_with_context(pr_url)
        self.args = args
        self.incremental = self.parse_incremental(args)  # -i command
        if self.incremental and self.incremental.is_incremental:
            self.git_provider.get_incremental_commits(self.incremental)

        self.main_language = get_main_pr_language(
            self.git_provider.get_languages(), self.git_provider.get_files()
        )
        self.pr_url = pr_url
        self.is_answer = is_answer
        self.is_auto = is_auto

        if self.is_answer and not self.git_provider.is_supported("get_issue_comments"):
            raise Exception(f"Answer mode is not supported for {get_settings().config.git_provider} for now")
        self.ai_handler = ai_handler()
        self.ai_handler.main_pr_language = self.main_language
        self.patches_diff = None
        self.prediction = None
        answer_str, question_str = self._get_user_answers()
        self.pr_description, self.pr_description_files = (
            self.git_provider.get_pr_description(split_changes_walkthrough=True))
        if (self.pr_description_files and get_settings().get("config.is_auto_command", False) and
                get_settings().get("config.enable_ai_metadata", False)):
            add_ai_metadata_to_diff_files(self.git_provider, self.pr_description_files)
            get_logger().debug(f"AI metadata added to the this command")
        else:
            get_settings().set("config.enable_ai_metadata", False)
            get_logger().debug(f"AI metadata is disabled for this command")

        self.vars = {
            "title": self.git_provider.pr.title,
            "branch": self.git_provider.get_pr_branch(),
            "description": self.pr_description,
            "language": self.main_language,
            "diff": "",  # empty diff for initial calculation
            "num_pr_files": self.git_provider.get_num_of_files(),
            "num_max_findings": get_settings().pr_reviewer.num_max_findings,
            "require_score": get_settings().pr_reviewer.require_score_review,
            "require_tests": get_settings().pr_reviewer.require_tests_review,
            "require_estimate_effort_to_review": get_settings().pr_reviewer.require_estimate_effort_to_review,
            'require_can_be_split_review': get_settings().pr_reviewer.require_can_be_split_review,
            'require_security_review': get_settings().pr_reviewer.require_security_review,
            'question_str': question_str,
            'answer_str': answer_str,
            "extra_instructions": get_settings().pr_reviewer.extra_instructions,
            "commit_messages_str": self.git_provider.get_commit_messages(),
            "custom_labels": "",
            "enable_custom_labels": get_settings().config.enable_custom_labels,
            "is_ai_metadata":  get_settings().get("config.enable_ai_metadata", False),
            "related_tickets": get_settings().get('related_tickets', []),
            'duplicate_prompt_examples': get_settings().config.get('duplicate_prompt_examples', False),
            "date": datetime.datetime.now().strftime('%Y-%m-%d'),
        }

        self.token_handler = TokenHandler(
            self.git_provider.pr,
            self.vars,
            get_settings().pr_review_prompt.system,
            get_settings().pr_review_prompt.user
        )

    def parse_incremental(self, args: List[str]):
        is_incremental = False
        if args and len(args) >= 1:
            arg = args[0]
            if arg == "-i":
                is_incremental = True
        incremental = IncrementalPR(is_incremental)
        return incremental

    async def run(self) -> None:
        try:
            if not self.git_provider.get_files():
                get_logger().info(f"PR has no files: {self.pr_url}, skipping review")
                return None

            if self.incremental.is_incremental and not self._can_run_incremental_review():
                return None

            if isinstance(self.args, list) and self.args and self.args[0] == 'auto_approve':
                get_logger().info(f'Auto approve flow PR: {self.pr_url} ...')
                await self.auto_approve_logic()
                return None

            get_logger().info(f'Reviewing PR: {self.pr_url} ...')
            relevant_configs = {'pr_reviewer': dict(get_settings().pr_reviewer),
                                'config': dict(get_settings().config)}
            get_logger().debug("Relevant configs", artifacts=relevant_configs)

            # ticket extraction if exists
            await extract_and_cache_pr_tickets(self.git_provider, self.vars)

            if self.incremental.is_incremental and hasattr(self.git_provider, "unreviewed_files_set") and not self.git_provider.unreviewed_files_set:
                get_logger().info(f"Incremental review is enabled for {self.pr_url} but there are no new files")
                previous_review_url = ""
                if hasattr(self.git_provider, "previous_review"):
                    previous_review_url = self.git_provider.previous_review.html_url
                if get_settings().config.publish_output:
                    self.git_provider.publish_comment(f"Incremental Review Skipped\n"
                                    f"No files were changed since the [previous PR Review]({previous_review_url})")
                return None

            if get_settings().config.publish_output and not get_settings().config.get('is_auto_command', False):
                self.git_provider.publish_comment("Preparing review...", is_temporary=True)

            await retry_with_fallback_models(self._prepare_prediction, model_type=ModelType.REGULAR)
            if not self.prediction:
                self.git_provider.remove_initial_comment()
                return None

            pr_review = self._prepare_pr_review()
            get_logger().debug(f"PR output", artifact=pr_review)

            if get_settings().config.publish_output:
                # publish the review
                if get_settings().pr_reviewer.persistent_comment and not self.incremental.is_incremental:
                    final_update_message = get_settings().pr_reviewer.final_update_message
                    self.git_provider.publish_persistent_comment(pr_review,
                                                                 initial_header=f"{PRReviewHeader.REGULAR.value} 🔍",
                                                                 update_header=True,
                                                                 final_update_message=final_update_message, )
                else:
                    self.git_provider.publish_comment(pr_review)

                self.git_provider.remove_initial_comment()
            else:
                get_logger().info("Review output is not published")
                get_settings().data = {"artifact": pr_review}
                return
        except Exception as e:
            get_logger().error(f"Failed to review PR: {e}")

    async def _prepare_prediction(self, model: str) -> None:
        self.patches_diff = get_pr_diff(self.git_provider,
                                        self.token_handler,
                                        model,
                                        add_line_numbers_to_hunks=True,
                                        disable_extra_lines=False,)

        if self.patches_diff:
            get_logger().debug(f"PR diff", diff=self.patches_diff)
            self.prediction = await self._get_prediction(model)
        else:
            get_logger().warning(f"Empty diff for PR: {self.pr_url}")
            self.prediction = None

    async def _get_prediction(self, model: str) -> str:
        """
        Generate an AI prediction for the pull request review.

        Args:
            model: A string representing the AI model to be used for the prediction.

        Returns:
            A string representing the AI prediction for the pull request review.
        """
        variables = copy.deepcopy(self.vars)
        variables["diff"] = self.patches_diff  # update diff

        environment = Environment(undefined=StrictUndefined)
        system_prompt = environment.from_string(get_settings().pr_review_prompt.system).render(variables)
        user_prompt = environment.from_string(get_settings().pr_review_prompt.user).render(variables)

        response, finish_reason = await self.ai_handler.chat_completion(
            model=model,
            temperature=get_settings().config.temperature,
            system=system_prompt,
            user=user_prompt
        )

        return response

    def _prepare_pr_review(self) -> str:
        """
        Prepare the PR review by processing the AI prediction and generating a markdown-formatted text that summarizes
        the feedback.
        """
        first_key = 'review'
        last_key = 'security_concerns'
        data = load_yaml(self.prediction.strip(),
                         keys_fix_yaml=["ticket_compliance_check", "estimated_effort_to_review_[1-5]:", "security_concerns:", "key_issues_to_review:",
                                        "confidence_score_[1-100]:", "complexity_score_[1-10]:", "security_score_[1-10]:", "auto_approve_recommendation:",
                                        "relevant_file:", "relevant_line:", "suggestion:"],
                         first_key=first_key, last_key=last_key)
        github_action_output(data, 'review')

        if 'review' not in data:
            get_logger().exception("Failed to parse review data", artifact={"data": data})
            return ""

        # move data['review'] 'key_issues_to_review' key to the end of the dictionary
        if 'key_issues_to_review' in data['review']:
            key_issues_to_review = data['review'].pop('key_issues_to_review')
            data['review']['key_issues_to_review'] = key_issues_to_review

        incremental_review_markdown_text = None
        # Add incremental review section
        if self.incremental.is_incremental:
            last_commit_url = f"{self.git_provider.get_pr_url()}/commits/" \
                              f"{self.git_provider.incremental.first_new_commit_sha}"
            incremental_review_markdown_text = f"Starting from commit {last_commit_url}"

        markdown_text = convert_to_markdown_v2(data, self.git_provider.is_supported("gfm_markdown"),
                                            incremental_review_markdown_text,
                                               git_provider=self.git_provider,
                                               files=self.git_provider.get_diff_files())

        # Add help text if gfm_markdown is supported
        if self.git_provider.is_supported("gfm_markdown") and get_settings().pr_reviewer.enable_help_text:
            markdown_text += "<hr>\n\n<details> <summary><strong>💡 Tool usage guide:</strong></summary><hr> \n\n"
            markdown_text += HelpMessage.get_review_usage_guide()
            markdown_text += "\n</details>\n"

        # Output the relevant configurations if enabled
        if get_settings().get('config', {}).get('output_relevant_configurations', False):
            markdown_text += show_relevant_configurations(relevant_section='pr_reviewer')

        # Add custom labels from the review prediction (effort, security)
        self.set_review_labels(data)

        if markdown_text == None or len(markdown_text) == 0:
            markdown_text = ""

        return markdown_text

    def _get_user_answers(self) -> Tuple[str, str]:
        """
        Retrieves the question and answer strings from the discussion messages related to a pull request.

        Returns:
            A tuple containing the question and answer strings.
        """
        question_str = ""
        answer_str = ""

        if self.is_answer:
            discussion_messages = self.git_provider.get_issue_comments()

            for message in discussion_messages.reversed:
                if "Questions to better understand the PR:" in message.body:
                    question_str = message.body
                elif '/answer' in message.body:
                    answer_str = message.body

                if answer_str and question_str:
                    break

        return question_str, answer_str

    def _get_previous_review_comment(self):
        """
        Get the previous review comment if it exists.
        """
        try:
            if hasattr(self.git_provider, "get_previous_review"):
                return self.git_provider.get_previous_review(
                    full=not self.incremental.is_incremental,
                    incremental=self.incremental.is_incremental,
                )
        except Exception as e:
            get_logger().exception(f"Failed to get previous review comment, error: {e}")

    def _remove_previous_review_comment(self, comment):
        """
        Remove the previous review comment if it exists.
        """
        try:
            if comment:
                self.git_provider.remove_comment(comment)
        except Exception as e:
            get_logger().exception(f"Failed to remove previous review comment, error: {e}")

    def _can_run_incremental_review(self) -> bool:
        """
        Checks if we can run incremental review according the various configurations and previous review.
        """
        # checking if running is auto mode but there are no new commits
        if self.is_auto and not self.incremental.first_new_commit_sha:
            get_logger().info(f"Incremental review is enabled for {self.pr_url} but there are no new commits")
            return False

        if not hasattr(self.git_provider, "get_incremental_commits"):
            get_logger().info(f"Incremental review is not supported for {get_settings().config.git_provider}")
            return False
        # checking if there are enough commits to start the review
        num_new_commits = len(self.incremental.commits_range)
        num_commits_threshold = get_settings().pr_reviewer.minimal_commits_for_incremental_review
        not_enough_commits = num_new_commits < num_commits_threshold
        # checking if the commits are not too recent to start the review
        recent_commits_threshold = datetime.datetime.now() - datetime.timedelta(
            minutes=get_settings().pr_reviewer.minimal_minutes_for_incremental_review
        )
        last_seen_commit_date = (
            self.incremental.last_seen_commit.commit.author.date if self.incremental.last_seen_commit else None
        )
        all_commits_too_recent = (
            last_seen_commit_date > recent_commits_threshold if self.incremental.last_seen_commit else False
        )
        # check all the thresholds or just one to start the review
        condition = any if get_settings().pr_reviewer.require_all_thresholds_for_incremental_review else all
        if condition((not_enough_commits, all_commits_too_recent)):
            get_logger().info(
                f"Incremental review is enabled for {self.pr_url} but didn't pass the threshold check to run:"
                f"\n* Number of new commits = {num_new_commits} (threshold is {num_commits_threshold})"
                f"\n* Last seen commit date = {last_seen_commit_date} (threshold is {recent_commits_threshold})"
            )
            return False
        return True

    def set_review_labels(self, data):
        if not get_settings().config.publish_output:
            return

        if not get_settings().pr_reviewer.require_estimate_effort_to_review:
            get_settings().pr_reviewer.enable_review_labels_effort = False # we did not generate this output
        if not get_settings().pr_reviewer.require_security_review:
            get_settings().pr_reviewer.enable_review_labels_security = False # we did not generate this output

        if (get_settings().pr_reviewer.enable_review_labels_security or
                get_settings().pr_reviewer.enable_review_labels_effort):
            try:
                review_labels = []
                if get_settings().pr_reviewer.enable_review_labels_effort:
                    estimated_effort = data['review']['estimated_effort_to_review_[1-5]']
                    estimated_effort_number = 0
                    if isinstance(estimated_effort, str):
                        try:
                            estimated_effort_number = int(estimated_effort.split(',')[0])
                        except ValueError:
                            get_logger().warning(f"Invalid estimated_effort value: {estimated_effort}")
                    elif isinstance(estimated_effort, int):
                        estimated_effort_number = estimated_effort
                    else:
                        get_logger().warning(f"Unexpected type for estimated_effort: {type(estimated_effort)}")
                    if 1 <= estimated_effort_number <= 5:  # 1, because ...
                        review_labels.append(f'Review effort {estimated_effort_number}/5')
                if get_settings().pr_reviewer.enable_review_labels_security and get_settings().pr_reviewer.require_security_review:
                    security_concerns = data['review']['security_concerns']  # yes, because ...
                    security_concerns_bool = 'yes' in security_concerns.lower() or 'true' in security_concerns.lower()
                    if security_concerns_bool:
                        review_labels.append('Possible security concern')

                current_labels = self.git_provider.get_pr_labels(update=True)
                if not current_labels:
                    current_labels = []
                get_logger().debug(f"Current labels:\n{current_labels}")
                if current_labels:
                    current_labels_filtered = [label for label in current_labels if
                                               not label.lower().startswith('review effort') and not label.lower().startswith(
                                                   'possible security concern')]
                else:
                    current_labels_filtered = []
                new_labels = review_labels + current_labels_filtered
                if (current_labels or review_labels) and sorted(new_labels) != sorted(current_labels):
                    get_logger().info(f"Setting review labels:\n{review_labels + current_labels_filtered}")
                    self.git_provider.publish_labels(new_labels)
                else:
                    get_logger().info(f"Review labels are already set:\n{review_labels + current_labels_filtered}")
            except Exception as e:
                get_logger().error(f"Failed to set review labels, error: {e}")

    async def auto_approve_logic(self):
        """
        Smart auto-approve a pull request based on AI analysis and custom scoring.
        """
        if not get_settings().config.enable_auto_approval:
            get_logger().info("Auto-approval option is disabled")
            self.git_provider.publish_comment("Auto-approval option for PR-Agent is disabled. "
                                              "You can enable it via a [configuration file](https://github.com/Codium-ai/pr-agent/blob/main/docs/REVIEW.md#auto-approval-1)")
            return

        try:
            # First, run the AI review to get our custom scoring
            await retry_with_fallback_models(self._prepare_prediction, model_type=ModelType.REGULAR)
            if not self.prediction:
                get_logger().info("No AI prediction available for auto-approval")
                return

            # Parse the review data to get our custom scores
            review_data = self._parse_review_data()
            if not review_data:
                get_logger().info("Failed to parse review data for auto-approval")
                return

            # Make the auto-approval decision
            should_approve, reason, details = self._evaluate_auto_approval(review_data)

            if should_approve:
                is_auto_approved = self.git_provider.auto_approve()
                if is_auto_approved:
                    get_logger().info(f"Auto-approved PR: {reason}")
                    self.git_provider.publish_comment(f"🤖 **Auto-approved PR**\n\n**Reason**: {reason}\n\n**Analysis Details**:\n{details}\n\n_This PR meets all auto-approval criteria._")
                else:
                    get_logger().warning("Failed to auto-approve PR via git provider")
                    self.git_provider.publish_comment(f"⚠️ **Auto-approval recommended but failed**\n\n**Reason**: {reason}\n\n**Analysis Details**:\n{details}")
            else:
                get_logger().info(f"Auto-approval declined: {reason}")
                self.git_provider.publish_comment(f"🔍 **Manual review required**\n\n**Reason**: {reason}\n\n**Analysis Details**:\n{details}")

        except Exception as e:
            get_logger().error(f"Error in auto-approval logic: {e}")
            self.git_provider.publish_comment("❌ **Auto-approval failed due to an error**. Manual review required.")

    def _parse_review_data(self):
        """Parse the AI prediction to extract review data"""
        try:
            first_key = 'review'
            last_key = 'security_concerns'
            data = load_yaml(self.prediction.strip(),
                             keys_fix_yaml=["ticket_compliance_check", "estimated_effort_to_review_[1-5]:", "security_concerns:", "key_issues_to_review:",
                                            "confidence_score_[1-100]:", "complexity_score_[1-10]:", "security_score_[1-10]:", "auto_approve_recommendation:",
                                            "relevant_file:", "relevant_line:", "suggestion:"],
                             first_key=first_key, last_key=last_key)
            
            if 'review' not in data:
                get_logger().error("No review data found in AI prediction")
                return None
                
            return data['review']
        except Exception as e:
            get_logger().error(f"Failed to parse review data: {e}")
            return None

    def _evaluate_auto_approval(self, review_data):
        """
        Smart auto-approval logic based on AI analysis and PR metrics
        Returns: (should_approve: bool, reason: str, details: str)
        """
        # Get configurable thresholds
        config = get_settings().config
        confidence_threshold = getattr(config, 'auto_approve_confidence_threshold', 85)
        complexity_threshold = getattr(config, 'auto_approve_complexity_threshold', 5)
        security_threshold = getattr(config, 'auto_approve_security_threshold', 8)
        effort_threshold = getattr(config, 'auto_approve_effort_threshold', 3)
        max_files = getattr(config, 'auto_approve_max_files', 5)
        max_lines = getattr(config, 'auto_approve_max_lines', 200)
        max_issues = getattr(config, 'auto_approve_max_issues', 3)

        # Extract AI scores (with safe defaults)
        confidence = self._safe_extract_score(review_data.get('confidence_score_[1-100]'), 1, 100, 0)
        complexity = self._safe_extract_score(review_data.get('complexity_score_[1-10]'), 1, 10, 10)
        security = self._safe_extract_score(review_data.get('security_score_[1-10]'), 1, 10, 0)
        effort = self._safe_extract_score(review_data.get('estimated_effort_to_review_[1-5]'), 1, 5, 5)
        ai_recommends = review_data.get('auto_approve_recommendation', False)
        
        # Convert string boolean if needed
        if isinstance(ai_recommends, str):
            ai_recommends = ai_recommends.lower() in ['true', 'yes', '1']

        # Extract other data
        issues = review_data.get('key_issues_to_review', [])
        security_concerns = review_data.get('security_concerns', '')
        has_security_issues = security_concerns.lower() not in ['no', 'none', '']

        # Get PR metrics
        pr_files = self.git_provider.get_num_of_files()
        pr_additions = getattr(self.git_provider.pr, 'additions', 0)
        pr_deletions = getattr(self.git_provider.pr, 'deletions', 0)
        total_lines = pr_additions + pr_deletions
        author = getattr(self.git_provider.pr, 'user', {}).get('login', 'unknown')
        
        # Build details string
        details = f"""
- **Confidence Score**: {confidence}/100 (threshold: ≥{confidence_threshold})
- **Complexity Score**: {complexity}/10 (threshold: ≤{complexity_threshold})
- **Security Score**: {security}/10 (threshold: ≥{security_threshold})
- **Effort Score**: {effort}/5 (threshold: ≤{effort_threshold})
- **Files Changed**: {pr_files} (threshold: ≤{max_files})
- **Lines Changed**: +{pr_additions}/-{pr_deletions} (total: {total_lines}, threshold: ≤{max_lines})
- **Issues Found**: {len(issues)} (threshold: ≤{max_issues})
- **AI Recommendation**: {ai_recommends}
- **Author**: {author}
"""

        # AUTO-APPROVAL DECISION LOGIC
        
        # Check for immediate disqualifiers
        if has_security_issues and security < security_threshold:
            return False, f"Security concerns detected (score: {security}/{security_threshold})", details
            
        if len(issues) > max_issues:
            return False, f"Too many issues found ({len(issues)}/{max_issues})", details
            
        if total_lines > max_lines:
            return False, f"Large change size ({total_lines}/{max_lines} lines)", details
            
        if pr_files > max_files:
            return False, f"Too many files changed ({pr_files}/{max_files})", details
            
        if effort > effort_threshold:
            return False, f"High review effort required ({effort}/{effort_threshold})", details

        # Check for critical issues
        critical_issues = [issue for issue in issues if 
                          any(word in issue.get('issue_header', '').lower() 
                              for word in ['critical', 'error', 'bug', 'security', 'fail'])]
        
        if critical_issues:
            return False, f"Critical issues detected: {', '.join([i.get('issue_header', '') for i in critical_issues])}", details

        # Auto-approval criteria (must meet ALL)
        criteria_checks = []
        
        # High confidence requirement
        if confidence >= confidence_threshold:
            criteria_checks.append("✅ High confidence")
        else:
            return False, f"Low confidence score ({confidence}/{confidence_threshold})", details
            
        # Low complexity requirement  
        if complexity <= complexity_threshold:
            criteria_checks.append("✅ Low complexity")
        else:
            return False, f"High complexity score ({complexity}/{complexity_threshold})", details
            
        # High security requirement
        if security >= security_threshold:
            criteria_checks.append("✅ High security")
        else:
            return False, f"Low security score ({security}/{security_threshold})", details
            
        # Low effort requirement
        if effort <= effort_threshold:
            criteria_checks.append("✅ Low effort")
        else:
            return False, f"High effort score ({effort}/{effort_threshold})", details
            
        # Size requirements
        if total_lines <= max_lines:
            criteria_checks.append("✅ Small change")
        else:
            return False, f"Large change ({total_lines}/{max_lines} lines)", details
            
        if pr_files <= max_files:
            criteria_checks.append("✅ Few files")
        else:
            return False, f"Many files ({pr_files}/{max_files})", details
            
        # AI recommendation bonus (not required but helpful)
        if ai_recommends:
            criteria_checks.append("✅ AI recommends approval")
            
        # All criteria met!
        criteria_summary = "\n".join(criteria_checks)
        reason = f"All auto-approval criteria met ({len(criteria_checks)} checks passed)"
        
        return True, reason, details + f"\n\n**Criteria Met**:\n{criteria_summary}"

    def _safe_extract_score(self, value, min_val, max_val, default):
        """Safely extract and validate a numeric score"""
        try:
            if isinstance(value, (int, float)):
                score = int(value)
            elif isinstance(value, str):
                # Try to extract number from string
                import re
                match = re.search(r'\d+', value)
                if match:
                    score = int(match.group())
                else:
                    return default
            else:
                return default
                
            # Clamp to valid range
            return max(min_val, min(max_val, score))
        except (ValueError, TypeError):
            return default
