from __future__ import annotations

import math


def normalize3(vector):
    norm = math.sqrt(sum(float(v) * float(v) for v in vector[:3]))
    if norm <= 1.0e-12:
        return [0.0, 0.0, 0.0]
    return [float(vector[0]) / norm, float(vector[1]) / norm, float(vector[2]) / norm]


def scale3(vector, scalar):
    return [float(vector[0]) * float(scalar), float(vector[1]) * float(scalar), float(vector[2]) * float(scalar)]


def as_rows3(value):
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    rows = []
    for row in value:
        if len(row) >= 3:
            rows.append([float(row[0]), float(row[1]), float(row[2])])
    return rows


def sum_rows3(value):
    total = [0.0, 0.0, 0.0]
    for row in as_rows3(value):
        total[0] += row[0]
        total[1] += row[1]
        total[2] += row[2]
    return total


def modulus3(vector):
    return math.sqrt(sum(float(v) * float(v) for v in vector[:3]))

