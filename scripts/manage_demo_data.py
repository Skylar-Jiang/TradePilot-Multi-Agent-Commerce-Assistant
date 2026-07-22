import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.maintenance.demo_data import DemoDataManager  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up or reset TradePilot shared demo data safely.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("plan", help="Show the reset plan without changing data.")
    subcommands.add_parser("export", help="Back up SQLite plus upload and report files.")
    reset = subcommands.add_parser("reset", help="Dry-run by default; reset only with exact confirmation.")
    reset.add_argument("--confirm")
    args = parser.parse_args()

    manager = DemoDataManager(get_settings())
    if args.command == "plan":
        result = manager.plan()
    elif args.command == "export":
        result = {"backup_dir": str(manager.export())}
    else:
        result = manager.reset(confirm=args.confirm)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
