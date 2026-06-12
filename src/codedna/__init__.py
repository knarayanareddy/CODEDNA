"""
CodeDNA - Local-first, privacy-preserving developer identity and code intelligence tool.
"""

__version__ = "0.3.0"
__author__ = "CodeDNA Contributors"
__license__ = "MIT"

from codedna.db.models import Base
from codedna.db.session import get_session, init_database
from codedna.db.schema import CURRENT_SCHEMA_VERSION

__all__ = ["__version__", "Base", "get_session", "init_database", "CURRENT_SCHEMA_VERSION"]
