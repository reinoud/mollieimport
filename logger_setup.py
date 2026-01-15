import logging
from logging.handlers import RotatingFileHandler


def setup_logging(logfile: str = "import.log", level: int = logging.INFO) -> logging.Logger:
    """Configure and return a standard logger.

    The logger writes INFO+ messages to a rotating logfile and prints WARNING+ to stderr.

    Args:
        logfile: path to the logfile.
        level: logging level for the logger.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger("mollie_import")
    logger.setLevel(level)

    if not logger.handlers:
        # Rotating file handler
        fh = RotatingFileHandler(logfile, maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setLevel(level)
        fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console handler for warnings and errors
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger

