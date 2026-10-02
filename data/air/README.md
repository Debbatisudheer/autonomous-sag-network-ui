# Phase 27 aerial trajectory data

The Phase 27 trajectory adapter supports external UAV and HAPS trajectory files and projects them into the existing `AirNetwork` contract.

## Real UAV source wired into the project

The loader is compatible with the public ORION drone trajectory files:

`https://github.com/ssciancalepore/orion-data`

The ORION repository describes its files as data from real drone flights and specifies acquisition timestamp (milliseconds), latitude and longitude fields. The repository is GPL-3.0 licensed.

Files:

- `allowed_traj_1.txt`
- `allowed_traj_2.txt`
- `disallowed_traj.txt`

The project does **not** vendor the full ORION files. Use the upstream repository as the authoritative source and preserve its attribution/license when storing local copies for experiments.

Example command after downloading `allowed_traj_1.txt`:

```powershell
python -c "from sag_network.trajectory.loader import load_jsonl_trajectory; from sag_network.domain.air import AirPlatformType; ds=load_jsonl_trajectory('data/air/allowed_traj_1.txt', dataset_id='orion-allowed-1', source_name='ORION real drone trajectory', attribution='ORION drone trajectory dataset; see data/air/README.md', platform_id='uav-orion-01', platform_type=AirPlatformType.UAV, source_uri='https://github.com/ssciancalepore/orion-data/blob/main/allowed_traj_1.txt'); print(len(ds.trajectories[0].points))"
```

## HAPS

The common trajectory contract supports `AirPlatformType.HAPS` and `AerialTrajectorySourceType.HAPS_EXTERNAL`, so a real HAPS trajectory can be loaded without changing the core AirNetwork model. No bundled real HAPS trajectory is claimed here because an authoritative openly redistributable HAPS trajectory source was not established for this phase.
