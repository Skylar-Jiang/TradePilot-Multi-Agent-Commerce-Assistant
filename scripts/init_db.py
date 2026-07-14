import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.migrations import upgrade_database  # noqa: E402


def main() -> None:
    settings = get_settings()
    for path in (settings.upload_dir, settings.report_dir, settings.chroma_dir):
        path.mkdir(parents=True, exist_ok=True)
    upgrade_database(settings.database_url)
    print(f"TradePilot scaffold database initialized: {settings.database_url}")


if __name__ == "__main__":
    main()
