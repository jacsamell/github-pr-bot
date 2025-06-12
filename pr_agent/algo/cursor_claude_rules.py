from typing import Dict, Optional
from pr_agent.log import get_logger


class CursorRulesHandler:
    """Handles reading official Cursor rules from repositories."""
    
    # Official Cursor rules files
    CURSOR_RULES_DIR = ".cursor/rules"
    LEGACY_CURSOR_RULES_FILE = ".cursorrules"
    
    def __init__(self, git_provider):
        self.git_provider = git_provider
        self.rules_content = ""
    
    def load_rules_from_repo(self, branch: str = None) -> bool:
        """Load official Cursor rules from the repository."""
        if not branch:
            try:
                # Use branch name first, fallback to SHA if needed, then 'main'
                if hasattr(self.git_provider, 'pr') and self.git_provider.pr:
                    branch = getattr(self.git_provider.pr.head, 'ref', None) or self.git_provider.pr.head.sha
                else:
                    branch = 'main'
            except (AttributeError, Exception):
                branch = 'main'
        
        content_parts = []
        loaded_files = []
        
        # Try to load .cursor/rules/*.mdc files
        mdc_content, mdc_files = self._load_mdc_files(branch)
        if mdc_content:
            content_parts.append(mdc_content)
            loaded_files.extend(mdc_files)
        
        # Try to load legacy .cursorrules file
        legacy_content = self._load_legacy_file(branch)
        if legacy_content:
            content_parts.append(legacy_content)
            loaded_files.append(self.LEGACY_CURSOR_RULES_FILE)
        
        self.rules_content = "\n\n".join(content_parts)
        
        # Log summary of what was loaded
        if loaded_files:
            get_logger().info(f"📋 Loaded Cursor rules from {len(loaded_files)} file(s): {', '.join([f.split('/')[-1] for f in loaded_files])}")
        else:
            get_logger().info("📋 No Cursor rules files found in repository")
        
        return bool(self.rules_content)
    
    def _load_mdc_files(self, branch: str) -> tuple[Optional[str], list[str]]:
        """Load .mdc files from .cursor/rules/ directory."""
        if not hasattr(self.git_provider, 'get_pr_file_content'):
            return None, []
        
        content_parts = []
        loaded_files = []
        
        # First try to list all .mdc files in the .cursor/rules/ directory
        try:
            # Check if git provider supports directory listing (currently GitHub only)
            if hasattr(self.git_provider, '_get_repo'):
                # NOTE: Using private method _get_repo() for GitHub-specific directory listing
                # This is the only way to access repository contents beyond individual files
                # We fallback gracefully for other providers that don't support this
                repo = self.git_provider._get_repo()
                directory_contents = repo.get_contents(self.CURSOR_RULES_DIR, ref=branch)
                
                # Filter for .mdc files
                mdc_files = []
                if isinstance(directory_contents, list):
                    # Multiple files in directory
                    mdc_files = [f for f in directory_contents if f.name.endswith('.mdc')]
                else:
                    # Single file
                    if directory_contents.name.endswith('.mdc'):
                        mdc_files = [directory_contents]
                
                get_logger().info(f"🔍 Found {len(mdc_files)} .mdc file(s) in {self.CURSOR_RULES_DIR}")
                
                # Load each .mdc file
                for file_obj in mdc_files:
                    try:
                        content = self.git_provider.get_pr_file_content(file_obj.path, branch)
                        if content and content.strip():
                            get_logger().info(f"✅ Loaded Cursor rules from: {file_obj.path}")
                            content_parts.append(content.strip())
                            loaded_files.append(file_obj.path)
                        else:
                            get_logger().debug(f"Empty content in {file_obj.path}")
                    except Exception as e:
                        get_logger().debug(f"Failed to load {file_obj.path}: {e}")
                        continue
            else:
                # Provider doesn't support directory listing, skip to fallback
                raise NotImplementedError("Directory listing not supported by this git provider")
                    
        except Exception as e:
            get_logger().debug(f"Failed to list {self.CURSOR_RULES_DIR} directory: {e}")
            get_logger().info(f"📋 Directory listing not supported by git provider - skipping .mdc files")

        return "\n\n".join(content_parts) if content_parts else None, loaded_files
    
    def _load_legacy_file(self, branch: str) -> Optional[str]:
        """Load legacy .cursorrules file."""
        if not hasattr(self.git_provider, 'get_pr_file_content'):
            return None
        
        try:
            content = self.git_provider.get_pr_file_content(self.LEGACY_CURSOR_RULES_FILE, branch)
            if content and content.strip():
                get_logger().info(f"✅ Loaded legacy Cursor rules from: {self.LEGACY_CURSOR_RULES_FILE}")
                return content.strip()
        except (FileNotFoundError, Exception):
            return None
    
    def has_rules(self) -> bool:
        """Check if any rules were loaded."""
        return bool(self.rules_content)
    
    def get_rules_for_prompt(self) -> str:
        """Get Cursor rules formatted for inclusion in AI prompts."""
        if not self.rules_content:
            return ""
        
        return f"\n\n## Repository Cursor Rules\n{self.rules_content}\n" 