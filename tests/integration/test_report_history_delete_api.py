from pathlib import Path

from tests.integration.test_report_support_api import _client, _report_id


def _edit_report(client, report_id: str, replacement: str) -> dict[str, object]:  # type: ignore[no-untyped-def]
    response = client.post(
        f"/api/v1/reports/{report_id}/support",
        json={
            "action": "edit",
            "section_id": "next-actions",
            "message": "Clarify the next action.",
            "replacement": [replacement],
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_deleting_a_middle_version_keeps_the_remaining_version_numbers(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path) as client:
        first_report_id = _report_id(client)
        second = _edit_report(client, first_report_id, "先补齐证据后再发布。")
        third = _edit_report(client, str(second["report_id"]), "发布前完成最终审校。")
        second_report = client.get(f"/api/v1/reports/{second['report_id']}").json()["data"]
        second_paths = [Path(second_report["json_path"]), Path(second_report["markdown_path"])]
        assert all(path.is_file() for path in second_paths)

        deleted = client.delete(f"/api/v1/reports/{second['report_id']}")
        versions = client.get(f"/api/v1/reports/{third['report_id']}/versions")
        history = client.get("/api/v1/reports")
        missing = client.get(f"/api/v1/reports/{second['report_id']}")

    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_report_id"] == second["report_id"]
    assert deleted.json()["data"]["deleted_file_count"] == 2
    assert [item["version"] for item in versions.json()["data"]["versions"]] == [1, 3]
    assert history.json()["data"]["reports"][0]["version"] == 3
    assert history.json()["data"]["reports"][0]["version_count"] == 2
    assert missing.status_code == 404
    assert not any(path.exists() for path in second_paths)


def test_clearing_history_removes_all_report_families(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path) as client:
        first_report_id = _report_id(client, "Clear history A")
        second_report_id = _report_id(client, "Clear history B")

        cleared = client.delete("/api/v1/reports")
        history = client.get("/api/v1/reports")
        first_missing = client.get(f"/api/v1/reports/{first_report_id}")
        second_missing = client.get(f"/api/v1/reports/{second_report_id}")

    assert cleared.status_code == 200
    assert cleared.json()["data"]["deleted_report_count"] == 2
    assert cleared.json()["data"]["deleted_file_count"] == 4
    assert history.json()["data"] == {"total": 0, "reports": []}
    assert first_missing.status_code == 404
    assert second_missing.status_code == 404
