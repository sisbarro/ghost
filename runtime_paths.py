"""Runtime paths shared by source and packaged GhostMail builds."""

import os
import sys


APP_NAME = "GhostMail"


def get_data_dir() -> str:
    """Return a user-writable directory for persistent application data."""
    configured_dir = os.getenv("GHOSTMAIL_DATA_DIR")
    if configured_dir:
        data_dir = os.path.abspath(os.path.expandvars(configured_dir))
    elif getattr(sys, "frozen", False) and os.name == "nt":
        root = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(root, APP_NAME)
    elif getattr(sys, "frozen", False):
        data_dir = os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")
    else:
        data_dir = os.path.abspath(os.path.dirname(__file__))
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


DATA_DIR = get_data_dir()