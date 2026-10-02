# Contributing

## Engineering rules

1. Keep physical models deterministic and unit-aware.
2. Do not introduce random values to simulate network behavior unless randomness is an explicit modeled assumption and is seeded.
3. Add a test for every new physics/model rule.
4. Keep domain models separate from orchestration and presentation code.
5. Record non-obvious engineering decisions in `docs/`.
6. Compare new algorithms with a clearly defined baseline.
7. Never present simulation output as real-world measurement.
8. Keep configuration outside application code where practical.
