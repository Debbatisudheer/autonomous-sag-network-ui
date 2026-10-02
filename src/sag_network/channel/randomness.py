from __future__ import annotations

import hashlib
import math


def _digest(seed: int, key: str) -> bytes:
    return hashlib.sha256(f"{seed}:{key}".encode()).digest()


def uniform(seed: int, key: str) -> float:
    """Deterministic U[0, 1) variate derived from a stable SHA-256 key."""
    raw = int.from_bytes(_digest(seed, key)[:8], byteorder="big", signed=False)
    return (raw + 0.5) / 2**64


def normal_pair(seed: int, key: str) -> tuple[float, float]:
    """Deterministic standard-normal pair using Box-Muller."""
    u1 = max(uniform(seed, f"{key}:u1"), 1e-15)
    u2 = uniform(seed, f"{key}:u2")
    radius = math.sqrt(-2.0 * math.log(u1))
    angle = 2.0 * math.pi * u2
    return radius * math.cos(angle), radius * math.sin(angle)


def complex_normal(seed: int, key: str) -> tuple[float, float]:
    """Deterministic unit-power circular complex Gaussian sample components."""
    real, imag = normal_pair(seed, key)
    scale = 1.0 / math.sqrt(2.0)
    return real * scale, imag * scale
