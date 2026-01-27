"""Application package initialization.

Loads environment variables early so they're available to all modules,
including BAML-generated code which checks for env vars at import time.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables BEFORE any other imports
# This ensures BAML and other libraries can read env vars at import time
env = os.getenv("ENVIRONMENT", "development")
env_file = Path(__file__).parent.parent / f".env.{env}"

if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    # Fallback to .env if environment-specific file doesn't exist
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
