from utils.pattern import Singleton
import logging
from datetime import datetime
import os

class ScreenFormatter(logging.Formatter):
    GREY = "\x1b[38;20m"
    BLUE = "\x1b[34;20m"
    YELLOW = "\x1b[33;20m"
    GREEN = "\x1b[32;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    format = f"{GREEN}%(asctime)s{RESET} - ""{0}%(levelname)s"\
        f"{RESET} [%(pathname)s:%(lineno)d - %(funcName)s()] -> "\
        "{0}%(message)s"f"{RESET}"

    FORMATS = {
        logging.DEBUG: format.format(GREY),
        logging.INFO: format.format(BLUE),
        logging.WARNING: format.format(YELLOW),
        logging.ERROR: format.format(RED),
        logging.CRITICAL: format.format(BOLD_RED)
    }

    def format(self, record: logging.LogRecord):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

class FileFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        FORMAT = "[%(asctime)s (%(pathname)s:%(lineno)d - %(funcName)s())] %(levelname)s -> %(message)s"
        return logging.Formatter(FORMAT).format(record)

class Logger(logging.Logger, metaclass=Singleton):
    """
    Create logger object for the first time to use
    """
        
    def __init__(self, level: str = 'info', to_screen: bool = True,
                 to_file: bool = False, log_dir: str = 'Logs') -> None:
        """
        level: debug, info, warn, error, fatal
        log_dir: directory to store log files, default is 'Logs'
        """
        super().__init__("")
        lvl_text = ["debug", "info", "warn", "error", "fatal"]
        lvl_int = [logging.DEBUG, logging.INFO, logging.WARN, logging.ERROR, logging.FATAL]
        lvl_val = lvl_int[lvl_text.index(level)]

        # Log to console
        if to_screen:
            h = logging.StreamHandler()
            h.setLevel(lvl_val)
            h.setFormatter(ScreenFormatter())
            self.addHandler(h)

        # Log to file
        if to_file:
            # Ensure the Logs directory exists
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # Generate log file name based on the current date
            log_filename = os.path.join(log_dir, f"log_{datetime.now().strftime('%Y-%m-%d')}.log")

            # Set up file handler
            h = logging.FileHandler(log_filename)
            h.setLevel(lvl_val)
            h.setFormatter(FileFormatter())
            self.addHandler(h)



# logger = Logger(level='error', to_screen=True, to_file=False)
# logger.error("This is an info message.")
