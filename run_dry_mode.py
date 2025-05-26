#!/usr/bin/env python3
"""
Example script to run PR-Agent in dry-run mode.
This will print all comments to console instead of posting to GitHub.

Usage:
    python run_dry_mode.py --pr_url=<PR_URL> <command>
    
Example:
    python run_dry_mode.py --pr_url=https://github.com/owner/repo/pull/123 review
"""

import os
import sys

# Set dry_run mode via environment variable
os.environ["CONFIG.DRY_RUN"] = "true"

# Import and run the CLI
from pr_agent.cli import run

if __name__ == "__main__":
    if len(sys.argv) < 2 or "--pr_url" not in sys.argv[1]:
        print(__doc__)
        sys.exit(1)
    
    print("Running PR-Agent in DRY RUN mode...")
    print("All output will be printed to console only.\n")
    
    run() 