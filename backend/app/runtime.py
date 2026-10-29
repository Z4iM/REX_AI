"""One explicit runtime mode keeps synthetic fixtures away from academy storage."""
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


def _demo_directory(name):
    root = Path(os.getenv("REX_DEMO_DATA_DIR") or ROOT / "data/demo").resolve()
    # Reject parent/child overlap too: backups and cleanup must stay isolated.
    for variable, default in (("REX_CATALOG_DATA_DIR", "catalog"),
                              ("RFP_DATA_DIR", "rfp"),
                              ("REX_CURRICULUM_DIR", "curriculum")):
        academy = Path(os.getenv(variable) or ROOT / "data" / default).resolve()
        if root == academy or root in academy.parents or academy in root.parents:
            raise RuntimeError("demo and academy storage directories must be different and must not overlap")
    if configured_url := os.getenv("RFP_DATABASE_URL"):
        from sqlalchemy.engine import make_url
        url = make_url(configured_url)
        if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
            if Path(url.database).resolve().is_relative_to(root):
                raise RuntimeError("demo storage must not contain the configured academy RFP database")
    return root / name


def catalog_dir():
    if is_demo():
        return _demo_directory("catalog")
    return Path(os.getenv("REX_CATALOG_DATA_DIR") or ROOT / "data/catalog").resolve()


def rfp_dir():
    if is_demo():
        return _demo_directory("rfp")
    return Path(os.getenv("RFP_DATA_DIR") or ROOT / "data/rfp").resolve()


def curriculum_dir():
    academy = Path(os.getenv("REX_CURRICULUM_DIR") or ROOT / "data/curriculum").resolve()
    if is_demo():
        return _demo_directory("curriculum")
    return academy
