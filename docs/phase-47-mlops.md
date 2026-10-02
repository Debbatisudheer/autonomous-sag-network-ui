# Phase 47 — MLOps

Phase 47 adds reproducible machine-learning lifecycle controls on top of the locked Phase 45 wireless integration baseline. Phase 46 Security Hardening is intentionally skipped and is not implemented in this phase.

## Implemented

- Versioned model artifact metadata.
- Dataset lineage and deterministic dataset fingerprints.
- Feature-schema and training-configuration fingerprints.
- Evaluation records containing holdout metrics and sample counts.
- Deterministic promotion gates.
- Registered → validated → production/rejected lifecycle states.
- Replacement of an existing production version for the same model ID.
- Auditable promotion-decision fingerprints.
- Deterministic registry fingerprints.
- No external model deployment.
- No network-state mutation.

The registry stores reproducibility metadata and does not claim to be a remote model-serving platform. Model weights remain owned by the existing predictive modules.

## Evidence boundary

The Phase 47 demo uses a synthetic historical telemetry fixture. Its metrics validate the MLOps implementation and promotion workflow; they are not evidence of production model accuracy. `model_deployed_externally=false` makes the deployment boundary explicit.

## Validation

Run:

```powershell
ruff check .
mypy src
pytest -q
python scripts\run_phase47_mlops.py
```
