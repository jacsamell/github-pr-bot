#!/usr/bin/env python3

"""
Test script for Cursor rules functionality
"""

import sys
import os
from pathlib import Path

# Add the pr_agent module to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_cursor_rules_import():
    """Test that we can import the CursorRulesHandler"""
    try:
        from pr_agent.algo.cursor_claude_rules import CursorRulesHandler
        print("✅ Successfully imported CursorRulesHandler")
        return True
    except ImportError as e:
        print(f"❌ Failed to import CursorRulesHandler: {e}")
        return False

def test_cursor_rules_files_exist():
    """Test that our Cursor rules files exist"""
    mdc_file = Path(".cursor/rules/python.mdc")
    
    if mdc_file.exists():
        print(f"✅ Found Cursor rules file: {mdc_file}")
        with open(mdc_file, 'r') as f:
            content = f.read()
            if "Python Coding Rules" in content and "description:" in content:
                print("✅ Cursor rules file has expected content and metadata")
                return True
            else:
                print("❌ Cursor rules file missing expected content")
                return False
    else:
        print(f"❌ Cursor rules file not found: {mdc_file}")
        return False

class MockGitProvider:
    """Mock git provider for testing"""
    
    def __init__(self):
        self.pr = None
    
    def get_pr_file_content(self, file_path: str, branch: str) -> str:
        """Mock implementation that reads from actual files"""
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            raise Exception(f"File not found: {file_path}")

def test_cursor_rules_loading():
    """Test that CursorRulesHandler can load rules"""
    try:
        from pr_agent.algo.cursor_claude_rules import CursorRulesHandler
        
        mock_provider = MockGitProvider()
        handler = CursorRulesHandler(mock_provider)
        
        # Test loading rules
        rules_loaded = handler.load_rules_from_repo("main")
        
        if rules_loaded:
            print("✅ Successfully loaded rules from repository")
            
            # Test rules formatting for prompts
            prompt_rules = handler.get_rules_for_prompt()
            if prompt_rules and "Python Coding Rules" in prompt_rules:
                print("✅ Successfully formatted rules for AI prompts")
                print(f"   Prompt length: {len(prompt_rules)} characters")
                return True
            else:
                print("❌ Failed to format rules for prompts")
                return False
        else:
            print("❌ No rules were loaded")
            return False
            
    except Exception as e:
        print(f"❌ Error testing rules loading: {e}")
        return False

def test_git_provider_utils():
    """Test the git provider utils integration"""
    try:
        from pr_agent.git_providers.utils import get_repository_rules_for_prompt
        
        # This should return empty string since we don't have a real context
        rules = get_repository_rules_for_prompt()
        print("✅ Successfully called get_repository_rules_for_prompt()")
        print(f"   Returned: {'<empty>' if not rules else f'{len(rules)} characters'}")
        return True
        
    except Exception as e:
        print(f"❌ Error testing git provider utils: {e}")
        return False

def test_dynamic_mdc_discovery():
    """Test that we discover more .mdc files than just the original hardcoded ones"""
    print("\n" + "="*50)
    print("🔍 TESTING DYNAMIC .MDC FILE DISCOVERY")
    print("="*50)
    
    # Import the CursorRulesHandler to check the fallback list
    from pr_agent.algo.cursor_claude_rules import CursorRulesHandler
    
    # Mock git provider to test the fallback logic
    class MockGitProvider:
        def __init__(self):
            self.call_count = 0
            self.attempted_files = []
            
        def get_pr_file_content(self, file_path, branch):
            self.call_count += 1
            self.attempted_files.append(file_path)
            # Simulate file not found for all files
            raise Exception("File not found")
    
    mock_provider = MockGitProvider()
    handler = CursorRulesHandler(mock_provider)
    
    # This will trigger the fallback logic which tries multiple files
    try:
        handler._load_mdc_files('main')
    except:
        pass
    
    print(f"📊 Attempted to load {mock_provider.call_count} .mdc files")
    print("📋 Files checked:")
    for file_path in mock_provider.attempted_files:
        filename = file_path.split('/')[-1]
        print(f"  - {filename}")
    
    # Check that we're trying more than the original 3 files
    original_count = 3  # python.mdc, general.mdc, style.mdc
    if mock_provider.call_count > original_count:
        print(f"✅ SUCCESS: Now checking {mock_provider.call_count} files (was {original_count})")
        print("✅ Dynamic discovery improvement implemented!")
        
        # Show the additional files we now check
        additional_files = [f for f in mock_provider.attempted_files if f.split('/')[-1] not in ['python.mdc', 'general.mdc', 'style.mdc']]
        if additional_files:
            print("🆕 Additional files now discovered:")
            for file_path in additional_files:
                filename = file_path.split('/')[-1] 
                print(f"  - {filename}")
    else:
        print(f"❌ FAILURE: Still only checking {mock_provider.call_count} files")
        
    return mock_provider.call_count > original_count

def test_pr_review_logging():
    """Test the complete logging flow during a simulated PR review"""
    print("\n" + "="*50)
    print("🔄 TESTING PR REVIEW LOGGING FLOW")
    print("="*50)
    
    # Create a more complete mock git provider that simulates PR review environment
    class PRReviewMockGitProvider:
        def __init__(self):
            self.pr = type('MockPR', (), {'head': type('MockHead', (), {'sha': 'abc123'})})()
            
        def get_pr_file_content(self, file_path, branch):
            if file_path == ".cursor/rules/python.mdc":
                return """# Python Coding Rules for PR Agent

## Code Style
- Follow Python PEP 8 style guidelines
- Use 4 spaces for indentation (never tabs)
- Line length should not exceed 120 characters
"""
            elif file_path == ".cursor/rules/testing.mdc":
                return """# Testing Guidelines

## Unit Testing
- Write tests for all new functions
- Use descriptive test method names
- Follow AAA pattern: Arrange, Act, Assert
"""
            elif file_path == ".cursorrules":
                return """# Legacy Cursor Rules
- Be concise and clear
- Follow best practices
"""
            else:
                raise Exception("File not found")
    
    print("🎬 Simulating PR review with Cursor rules...")
    
    # Import the handler and create instance
    from pr_agent.algo.cursor_claude_rules import CursorRulesHandler
    mock_provider = PRReviewMockGitProvider()
    handler = CursorRulesHandler(mock_provider)
    
    print("\n📋 Step 1: Loading repository rules...")
    success = handler.load_rules_from_repo()
    
    print(f"\n📋 Step 2: Rules available: {success}")
    if success:
        print(f"📊 Rules content length: {len(handler.rules_content):,} characters")
    
    print("\n📋 Step 3: Including rules in AI prompt...")
    from pr_agent.git_providers.utils import get_repository_rules_for_prompt
    
    # Store the handler to simulate it being available
    from starlette_context import context
    try:
        context["cursor_rules"] = handler
        rules_for_prompt = get_repository_rules_for_prompt()
        print(f"📊 Prompt rules length: {len(rules_for_prompt):,} characters")
    except Exception as e:
        # Context not available in test environment
        print("📋 Context not available in test - simulating prompt inclusion...")
        rules_for_prompt = handler.get_rules_for_prompt()
        print(f"📊 Would include {len(rules_for_prompt):,} characters in AI prompt")
    
    print("\n🎯 Example of what would appear in PR review logs:")
    print("   ✅ Loaded Cursor rules from: .cursor/rules/python.mdc")
    print("   ✅ Loaded Cursor rules from: .cursor/rules/testing.mdc") 
    print("   ✅ Loaded legacy Cursor rules from: .cursorrules")
    print("   📋 Loaded Cursor rules from 3 file(s): python.mdc, testing.mdc, .cursorrules")
    print("   📋 Including repository Cursor rules in AI prompt (2,104 characters)")
    
    return success

def main():
    """Run all tests"""
    print("🧪 Testing Cursor Rules Implementation\n")
    
    tests = [
        ("Import Test", test_cursor_rules_import),
        ("Files Exist Test", test_cursor_rules_files_exist),
        ("Rules Loading Test", test_cursor_rules_loading),
        ("Git Provider Utils Test", test_git_provider_utils),
        ("Dynamic MDC Discovery Test", test_dynamic_mdc_discovery),
        ("PR Review Logging Test", test_pr_review_logging),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        if test_func():
            passed += 1
        
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Cursor rules implementation is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 