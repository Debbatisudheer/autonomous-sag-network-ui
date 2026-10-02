from pathlib import Path

from sag_network.release import build_release_manifest

ROOT = Path(__file__).resolve().parents[1]

PHASE54_FINGERPRINT = (
    "089bddd7512758b24f2a4c0798a5f3833cd8a9035493dda571d136816dbeabc4"
)


def test_release_manifest_excludes_development_artifacts() -> None:
    manifest = build_release_manifest(
        ROOT,
        version="1.0.0",
        phase54_benchmark_fingerprint=PHASE54_FINGERPRINT,
        evidence_class="software/research testbed",
        network_mutation=False,
        excluded_artifacts=(
            ".venv",
            "__pycache__",
            "*.pyc",
        ),
        runtime={
            "python_version": "3.11.0",
            "platform": "test",
        },
    )

    assert manifest.source_file_count >= 190
    assert manifest.test_file_count >= 56
    assert manifest.deterministic is True
    assert manifest.network_mutation is False
    assert (
        manifest.phase54_benchmark_fingerprint
        == PHASE54_FINGERPRINT
    )


def test_release_manifest_is_deterministic() -> None:
    kwargs = {
        "version": "1.0.0",
        "phase54_benchmark_fingerprint": PHASE54_FINGERPRINT,
        "evidence_class": "software/research testbed",
        "network_mutation": False,
        "excluded_artifacts": (
            ".venv",
            "__pycache__",
            "*.pyc",
        ),
        "runtime": {
            "python_version": "3.11.0",
            "platform": "test",
        },
    }

    first = build_release_manifest(ROOT, **kwargs)
    second = build_release_manifest(ROOT, **kwargs)

    assert first == second