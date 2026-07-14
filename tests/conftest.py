import pytest

from app.schemas.product import ProductProfile
from tests.builders import build_demo_product


@pytest.fixture
def demo_product() -> ProductProfile:
    return build_demo_product()
