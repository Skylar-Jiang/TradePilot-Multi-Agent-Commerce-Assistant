import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_railway_runs_uvicorn_on_the_platform_port_with_healthcheck() -> None:
    config = load_json("railway.json")

    assert config["build"] == {
        "builder": "RAILPACK",
        "buildCommand": "python scripts/materialize_lfs_data.py",
    }
    deploy = config["deploy"]
    assert deploy["startCommand"] == (
        "python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    )
    assert deploy["healthcheckPath"] == "/api/v1/health"
    assert deploy["healthcheckTimeout"] == 300
    assert "--reload" not in deploy["startCommand"]


def test_vercel_serves_the_vite_spa_with_security_headers() -> None:
    config = load_json("frontend/vercel.json")

    assert config["rewrites"] == [{"source": "/(.*)", "destination": "/index.html"}]
    header_entries = config["headers"][0]
    assert header_entries["source"] == "/(.*)"
    headers = {item["key"]: item["value"] for item in header_entries["headers"]}
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "style-src 'self' 'unsafe-inline'" in headers["Content-Security-Policy"]
    assert "https://*.up.railway.app" in headers["Content-Security-Policy"]
