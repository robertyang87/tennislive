import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import benchmark_reel_models as benchmark


def test_missing_reference_images_fails_before_any_model_request(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "benchmark", lambda: {
        "cover": {"portrait": {"image": "cover.jpg"}}})
    def unexpected_model():
        raise AssertionError("A model must not be called with missing source images")
    monkeypatch.setattr(benchmark, "Chat", unexpected_model)
    with pytest.raises(FileNotFoundError, match="contact sheets missing"):
        benchmark.run(tmp_path / "report")
