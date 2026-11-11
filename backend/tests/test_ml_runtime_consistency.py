"""
The ML artifacts are pickles: they only load reliably on the library versions they were trained with. These
checks keep requirements.txt, the installed runtime, the artifacts' recorded environment and the Docker build
context consistent, so a version bump or an over-eager .dockerignore cannot silently break /prognosis in production.
"""
from __future__ import annotations

import fnmatch
import importlib.metadata as md
import json
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ARTIFACTS = BACKEND / "app" / "ml" / "artifacts"
SURVIVAL_METADATA = [ARTIFACTS / "survival" / "metadata.json", ARTIFACTS / "survival_rfs" / "metadata.json",
                     ARTIFACTS / "molecular_survival" / "os" / "metadata.json",
                     ARTIFACTS / "molecular_survival" / "rfs" / "metadata.json"]


def _pins() -> dict[str, str]:
    pins = {}
    for line in (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)==([\w.]+)", line.strip())
        if m:
            pins[m.group(1).lower()] = m.group(2)
    return pins


@pytest.mark.parametrize("package", ["scikit-learn", "scikit-survival", "numpy", "scipy", "pandas", "joblib"])
def test_installed_runtime_matches_requirements_pins(package):
    assert md.version(package) == _pins()[package]


@pytest.mark.parametrize("path", SURVIVAL_METADATA, ids=lambda p: "/".join(p.parts[-3:-1]))
def test_survival_artifacts_were_trained_on_the_pinned_library_versions(path):
    env = json.loads(path.read_text(encoding="utf-8"))["environment"]
    pins = _pins()
    assert env["scikit-survival"] == pins["scikit-survival"]
    assert env["scikit-learn"] == pins["scikit-learn"]


def test_every_artifact_directory_has_a_model_and_metadata():
    for directory in ("survival", "survival_rfs", "treatment_response"):
        for name in ("model.joblib", "metadata.json", "metrics.json"):
            assert (ARTIFACTS / directory / name).is_file(), f"{directory}/{name}"
    assert (ARTIFACTS / "model.joblib").is_file() and (ARTIFACTS / "metrics.json").is_file()  # WDBC classifier


def test_docker_context_ships_the_artifacts_and_the_survival_runtime():
    patterns = [l.strip() for l in (BACKEND / ".dockerignore").read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith(("#", "!"))]
    shipped = ["app/ml/artifacts/model.joblib", "app/ml/artifacts/survival/model.joblib",
               "app/ml/artifacts/survival_rfs/model.joblib", "app/ml/artifacts/survival/metadata.json",
               "app/ml/prognosis.py", "app/ml/survival/predict.py"]
    for path in shipped:
        for pattern in patterns:
            p = pattern.rstrip("/")
            assert not (fnmatch.fnmatch(path, p) or fnmatch.fnmatch(Path(path).name, p) or path.startswith(p + "/")), (
                f"{path} is excluded from the image by .dockerignore pattern {pattern!r}")
    assert re.search(r"^COPY app \./app\s*$", (BACKEND / "Dockerfile").read_text(encoding="utf-8"), re.M)
    assert "scikit-survival" in _pins()
