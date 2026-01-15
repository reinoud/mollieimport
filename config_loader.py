import configparser
from typing import Dict


def load_config(path: str = "config.ini") -> Dict[str, str]:
    """Load Mollie configuration from an ini file.

    Expects a [mollie] section with APIkey and optional ProfileID.

    Args:
        path: path to the config.ini file.

    Returns:
        A dict with keys 'APIkey' and optionally 'ProfileID'.

    Raises:
        FileNotFoundError: if the file does not exist.
        KeyError: if required keys are missing.
    """
    parser = configparser.ConfigParser()
    read = parser.read(path)
    if not read:
        raise FileNotFoundError(f"Config file not found: {path}")

    if "mollie" not in parser:
        raise KeyError("Missing [mollie] section in config file")

    cfg = parser["mollie"]
    if "APIkey" not in cfg:
        raise KeyError("Missing APIkey in [mollie] section")

    return {"APIkey": cfg["APIkey"], "ProfileID": cfg.get("ProfileID", "")}

