"""TradePilot classroom launcher: start the backend and open Swagger."""

import argparse
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path

import httpx
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent
LAUNCHER_PATH = PROJECT_ROOT / "start_demo.py"
DEFAULT_PRODUCT = {
    "name": "Cordless 3L Stainless Steel Cat Water Fountain",
    "category": "pet water fountain",
    "description": (
        "Unlisted complete cordless drinking fountain for cats with a stainless steel basin, rechargeable "
        "circulation system, removable reservoir, and visible water level."
    ),
    "attributes": {"Target Species": "Cat", "Product Type": "Pet Water Fountain", "Capacity": "3L"},
    "features": [
        "cordless rechargeable circulation",
        "stainless steel drinking basin",
        "removable reservoir",
        "visible water level",
    ],
    "use_scenarios": ["indoor cat hydration without a nearby power outlet"],
    "target_market": "United States",
    "target_audience": ["indoor cat owners"],
    "target_price": 39.99,
    "target_currency": "USD",
    "known_risks": ["pump noise validation", "battery endurance validation"],
    "data_mode": "real",
}


def _data(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(str(payload.get("error") or payload))
    return dict(payload["data"])


def project_python_command(arguments: list[str]) -> list[str] | None:
    """Re-run with the project virtual environment when launched by another Python."""
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if "--inside-venv" in arguments or not venv_python.is_file():
        return None
    if Path(sys.executable).resolve() == venv_python.resolve():
        return None
    return [str(venv_python), str(LAUNCHER_PATH), "--inside-venv", *arguments]


def run_real_workflow(
    client: httpx.Client,
    *,
    base_url: str,
    timeout_seconds: int,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, str]:
    """Create the classroom candidate, wait for a real run, and return its report URL."""
    product = _data(client.post("/api/v1/products", json=DEFAULT_PRODUCT))
    run = _data(
        client.post(
            "/api/v1/analysis-runs",
            json={
                "product_id": product["product_id"],
                "data_mode": "real",
                "target_market": "United States",
                "jurisdiction": "US",
                "platform": "Amazon",
                "background_context_types": ["tariff_rate"],
                "background_provider": "us-tariff-provider",
                "user_constraints": {
                    "new_product_has_own_reviews": False,
                    "new_product_has_own_sales": False,
                    "new_product_has_own_rating": False,
                },
            },
        )
    )
    run_id = str(run["run_id"])
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = _data(client.get(f"/api/v1/analysis-runs/{run_id}/status"))
        state = str(status["status"])
        if state == "succeeded":
            report_id = str(status.get("report_id") or "")
            if not report_id:
                report_id = str(_data(client.get(f"/api/v1/analysis-runs/{run_id}"))["report_id"])
            return {
                "run_id": run_id,
                "report_id": report_id,
                "report_url": f"{base_url}/api/v1/reports/{report_id}/markdown",
            }
        if state in {"manual_review", "failed"}:
            raise RuntimeError(f"真实分析以 {state} 结束，请查看 /analysis-runs/{run_id}/audit。")
        sleep(1)
    raise TimeoutError(f"真实分析超过 {timeout_seconds} 秒仍未完成：{run_id}")


def _wait_for_health(base_url: str, timeout_seconds: int = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    with httpx.Client(base_url=base_url, timeout=2, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                if _data(client.get("/api/v1/health")).get("status") == "ok":
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
    raise TimeoutError("后端在 30 秒内未启动，请检查终端日志。")


def _run_automated_demo(port: int, timeout_seconds: int, no_browser: bool) -> int:
    base_url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=PROJECT_ROOT,
    )
    try:
        _wait_for_health(base_url)
        print("后端已启动，正在执行真实同行分析与营销报告生成，请耐心等待…", flush=True)
        with httpx.Client(base_url=base_url, timeout=180, trust_env=False) as client:
            result = run_real_workflow(
                client,
                base_url=base_url,
                timeout_seconds=timeout_seconds,
            )
        print(f"\n分析完成。Markdown 报告：{result['report_url']}", flush=True)
        print(f"Swagger：{base_url}/docs", flush=True)
        print(f"运行 ID：{result['run_id']}；报告 ID：{result['report_id']}", flush=True)
        if not no_browser:
            webbrowser.open(result["report_url"])
        server.wait()
        return 0
    except KeyboardInterrupt:
        print("\n正在停止 TradePilot 后端…", flush=True)
        return 0
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=15)


def main(argv: list[str] | None = None) -> int:
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    command = project_python_command(raw_arguments)
    if command is not None:
        return subprocess.call(command, cwd=PROJECT_ROOT)

    parser = argparse.ArgumentParser(description="Start TradePilot backend for a classroom demonstration.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--server-only", action="store_true", help="只启动 Swagger，不自动生成真实报告")
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--inside-venv", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(raw_arguments)
    if args.server_only:
        if not args.no_browser:
            webbrowser.open(f"http://127.0.0.1:{args.port}/docs")
        uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)
        return 0
    return _run_automated_demo(args.port, args.timeout_seconds, args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
