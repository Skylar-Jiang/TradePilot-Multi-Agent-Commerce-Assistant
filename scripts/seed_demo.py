import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.adapters.profiles import load_domain_adapter, load_domain_profile  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.migrations import upgrade_database  # noqa: E402
from app.db.repositories.sqlalchemy import SqlAlchemyProductRepository  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.rag.factory import create_knowledge_store  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a configured TradePilot Demo domain profile.")
    parser.add_argument("--profile", default="generic_cross_border_demo")
    parser.add_argument("--profiles-dir", type=Path, default=ROOT / "config" / "domain_profiles")
    args = parser.parse_args()

    profile = load_domain_profile(args.profile, profiles_dir=args.profiles_dir)
    adapter = load_domain_adapter(profile)
    upgrade_database(get_settings().database_url)
    with SessionLocal() as session:
        product = adapter.seed(
            session,
            SqlAlchemyProductRepository(session),
            create_knowledge_store(),
        )
    print(f"DEMO fixture seeded: product_id={product.product_id}")


if __name__ == "__main__":
    main()
