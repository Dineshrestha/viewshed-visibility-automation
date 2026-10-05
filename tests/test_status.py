from src.status import RunStatus


def test_run_status_roundtrip(tmp_path):
    path = tmp_path / "run_status.json"
    status = RunStatus(path)
    assert not status.is_complete("A001")

    status.set("A001", "Complete", observer_count=7)
    reloaded = RunStatus(path)

    assert reloaded.is_complete("A001")
    assert reloaded.data["sites"]["A001"]["observer_count"] == 7
