import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = ROOT / "start_demo.py"


def _launcher_module():
    assert LAUNCHER_PATH.is_file(), "课堂启动器应位于仓库根目录的 start_demo.py"
    spec = importlib.util.spec_from_file_location("tradepilot_demo_launcher", LAUNCHER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_reexecutes_with_project_venv_python(monkeypatch) -> None:
    launcher = _launcher_module()
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    monkeypatch.setattr(launcher, "PROJECT_ROOT", ROOT)
    monkeypatch.setattr(launcher.sys, "executable", r"C:\Python312\python.exe")

    command = launcher.project_python_command(["--no-browser"])

    assert command == [str(venv_python), str(LAUNCHER_PATH), "--inside-venv", "--no-browser"]


def test_launcher_server_only_mode_starts_uvicorn_and_opens_swagger(monkeypatch) -> None:
    launcher = _launcher_module()
    observed: dict[str, object] = {}
    monkeypatch.setattr(launcher, "project_python_command", lambda arguments: None)
    monkeypatch.setattr(
        launcher.uvicorn,
        "run",
        lambda app, **kwargs: observed.update({"app": app, **kwargs}),
    )
    monkeypatch.setattr(
        launcher.webbrowser,
        "open",
        lambda url: observed.setdefault("docs_url", url),
    )

    launcher.main(["--inside-venv", "--server-only", "--port", "8765"])

    assert observed == {
        "app": "app.main:app",
        "host": "127.0.0.1",
        "port": 8765,
        "docs_url": "http://127.0.0.1:8765/docs",
    }


class _Response:
    def __init__(self, data: dict[str, object]) -> None:
        self.data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"success": True, "data": self.data}


class _WorkflowClient:
    def __init__(self, status: str = "succeeded") -> None:
        self.status = status
        self.posts: list[tuple[str, dict[str, object]]] = []
        self.status_requests = 0

    def post(self, path: str, json: dict[str, object]) -> _Response:
        self.posts.append((path, json))
        if path == "/api/v1/products":
            return _Response({"product_id": "product-1", "data_origin": "user"})
        return _Response({"run_id": "run-1"})

    def get(self, path: str) -> _Response:
        if path.endswith("/status"):
            self.status_requests += 1
            return _Response({"status": self.status, "report_id": "report-1"})
        if path == "/api/v1/analysis-runs/run-1":
            return _Response({"report_id": "report-1"})
        raise AssertionError(path)


def test_launcher_submits_real_workflow_and_returns_report_url() -> None:
    launcher = _launcher_module()
    client = _WorkflowClient()

    result = launcher.run_real_workflow(
        client,
        base_url="http://127.0.0.1:8765",
        timeout_seconds=1,
        sleep=lambda _: None,
    )

    assert result == {
        "run_id": "run-1",
        "report_id": "report-1",
        "report_url": "http://127.0.0.1:8765/api/v1/reports/report-1/markdown",
    }
    assert [path for path, _ in client.posts] == ["/api/v1/products", "/api/v1/analysis-runs"]
    assert client.posts[0][1]["data_mode"] == "real"
    assert client.posts[1][1]["background_provider"] == "us-tariff-provider"


def test_launcher_stops_when_real_workflow_requires_manual_review() -> None:
    launcher = _launcher_module()

    with pytest.raises(RuntimeError, match="manual_review"):
        launcher.run_real_workflow(
            _WorkflowClient(status="manual_review"),
            base_url="http://127.0.0.1:8765",
            timeout_seconds=1,
            sleep=lambda _: None,
        )
