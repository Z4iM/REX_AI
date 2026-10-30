"""One explicit runtime mode keeps TA fixtures away from academy storage."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def is_demo():
    mode = os.getenv("REX_APP_MODE", "academy").strip().lower()
    if mode not in ("academy", "demo"):
        raise RuntimeError("REX_APP_MODE must be academy or demo")
    return mode == "demo"


def origin():
    return "synthetic_demo" if is_demo() else "academy"


def catalog_dir():
    if is_demo():
        directory = Path(os.getenv("REX_DEMO_DATA_DIR") or ROOT / "data/demo").resolve() / "catalog"
        academy = Path(os.getenv("REX_CATALOG_DATA_DIR") or ROOT / "data/catalog").resolve()
        if directory == academy:
            raise RuntimeError("TA demo and academy catalog directories must be different")
        return directory
    return Path(os.getenv("REX_CATALOG_DATA_DIR") or ROOT / "data/catalog").resolve()


def rfp_dir():
    if is_demo():
        return catalog_dir().parent / "rfp"
    return Path(os.getenv("RFP_DATA_DIR") or ROOT / "data/rfp").resolve()
