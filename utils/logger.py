import logging
import sys
import time
from pathlib import Path
from datetime import datetime

# ANSI colors
COLORS = {
    "RESET": "\033[0m",
    "RED": "\033[31m",
    "YELLOW": "\033[33m",
    "GREEN": "\033[32m",
    "BLUE": "\033[34m",
    "WHITE": "\033[37m",
    "BOLDRED": "\033[1;31m",
}

LEVEL_COLORS = {
    logging.DEBUG: COLORS["BLUE"],
    logging.INFO: COLORS["YELLOW"],
    logging.WARNING: COLORS["GREEN"],
    logging.ERROR: COLORS["RED"],
    logging.CRITICAL: COLORS["BOLDRED"],
}


class ColorFormatter(logging.Formatter):
    def format(self, record):
        level_color = LEVEL_COLORS.get(record.levelno, COLORS["WHITE"])
        record.levelname = f"{level_color}{record.levelname}{COLORS['RESET']}"
        record.name = f"{COLORS['BLUE']}{record.name}{COLORS['RESET']}"
        record.msg = f"{COLORS['WHITE']}{record.getMessage()}{COLORS['RESET']}"
        return super().format(record)


class StreamingHandler(logging.StreamHandler):
    """Custom console handler that prints text letter by letter"""

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            for char in msg + self.terminator:
                stream.write(char)
                stream.flush()
                # time.sleep(0.005)  # delay per character
        except Exception:
            self.handleError(record)


def setup_logger(name: str = __name__, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_formatter = ColorFormatter("%(levelname)s - %(name)s - %(message)s")

    log_filename = logs_dir / f"job_scraper_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Use custom streaming handler
    console_handler = StreamingHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
