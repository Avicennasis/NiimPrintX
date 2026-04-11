import os
import sys
import platformdirs
from loguru import logger


def _get_log_path():
    log_dir = platformdirs.user_log_dir('NiimPrintX')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "nimmy.log")


def setup_logger():
    logger.remove()
    default_level = "INFO"
    logger.add(sys.stderr, colorize=True, format="<blue>{time}</blue> | <level>{level}</level> | {message}",
               level=default_level)
    try:
        logger.add(_get_log_path(), rotation="100 MB", compression="zip", level=default_level)
    except (PermissionError, OSError):
        pass


# | Level name | Severity value | Logger method     |
# ---------------------------------------------------
# | TRACE      | 5              | logger.trace()    |
# | DEBUG      | 10             | logger.debug()    |
# | INFO       | 20             | logger.info()     |
# | SUCCESS    | 25             | logger.success()  |
# | WARNING    | 30             | logger.warning()  |
# | ERROR      | 40             | logger.error()    |
# | CRITICAL   | 50             | logger.critical() |
# ---------------------------------------------------
def logger_enable(verbose: int):
    # At verbose=0, keep the handlers setup_logger() already configured
    if verbose == 0:
        return

    # Mapping verbosity level to Loguru levels
    levels = {1: "INFO", 2: "DEBUG", 3: "TRACE"}
    new_level = levels.get(min(verbose, 3), "TRACE")

    # Remove existing handlers and re-add with new level
    logger.remove()  # public API — removes all handlers atomically

    logger.add(sys.stderr, colorize=True, format="<blue>{time}</blue> | <level>{level}</level> | {message}",
               level=new_level)
    try:
        logger.add(_get_log_path(), rotation="100 MB", compression="zip", level=new_level)
    except (PermissionError, OSError):
        pass


def get_logger():
    return logger
