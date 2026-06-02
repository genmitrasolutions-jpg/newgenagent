"""
utils/logger.py — Colored console logger + JSON event file logger
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

try:
    import colorama
    colorama.init(autoreset=True)
    R  = colorama.Fore.RED
    G  = colorama.Fore.GREEN
    Y  = colorama.Fore.YELLOW
    B  = colorama.Fore.BLUE
    C  = colorama.Fore.CYAN
    M  = colorama.Fore.MAGENTA
    W  = colorama.Fore.WHITE
    DIM= colorama.Style.DIM
    RST= colorama.Style.RESET_ALL
except ImportError:
    R=G=Y=B=C=M=W=DIM=RST=""

LEVEL_COLORS = {
    "DEBUG":    DIM,
    "INFO":     G,
    "WARNING":  Y,
    "ERROR":    R,
    "CRITICAL": M,
}


class ColorFormatter(logging.Formatter):
    def format(self, record):
        ts    = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        col   = LEVEL_COLORS.get(record.levelname, "")
        name  = f"{record.name:<10}"
        msg   = record.getMessage()
        return f"{DIM}{ts}{RST} {col}{record.levelname:<8}{RST} {C}{name}{RST} {msg}"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(ColorFormatter())
    logger.addHandler(h)
    logger.propagate = False
    return logger


def log_run_event(event_type: str, data: dict):
    """Append a structured JSON event to the run_events.jsonl log file."""
    try:
        from utils.config import Config
        Config.ensure_dirs()
        events_file = Config.LOGS_DIR / "run_events.jsonl"
        record = {
            "timestamp":  datetime.now().isoformat(),
            "event_type": event_type,
            **data,
        }
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
