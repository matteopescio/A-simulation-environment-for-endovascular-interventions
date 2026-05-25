from __future__ import annotations

import csv
from datetime import datetime
import math
from pathlib import Path

from math_utils import as_rows3

try:
    import Sofa
except Exception:
    Sofa = None


ControllerBase = Sofa.Core.Controller if Sofa is not None else object


def _fmt(value):
    try:
        return f"{float(value):.9g}"
    except Exception:
        return "nan"


def _read_data(component, data_name, default=None):
    if component is None:
        return default
    try:
        return component.findData(data_name).value
    except Exception:
        return default


def _flat_indices(values):
    indices = []
    for value in values or []:
        if isinstance(value, (list, tuple)):
            indices.extend(_flat_indices(value))
        else:
            try:
                indices.append(int(value))
            except Exception:
                pass
    return indices


def _modulus(vector):
    return math.sqrt(sum(float(v) * float(v) for v in vector[:3]))


class _CsvRecorderBase(ControllerBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_directory = Path(kwargs["output_directory"])
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._writer = None
        self.output_path = None
        self.recording_state = kwargs.get("recording_state")
        self.request_key = kwargs.get("request_key")
        self.output_prefix = kwargs.get("output_prefix")

    def _requested(self):
        if self.recording_state is None or self.request_key is None:
            return True
        return bool(self.recording_state.get(self.request_key, False))

    def _make_output_path(self):
        stem = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.output_prefix}_{stem}.csv" if self.output_prefix else f"{stem}.csv"
        path = self.output_directory / filename
        suffix = 1
        while path.exists():
            filename = f"{self.output_prefix}_{stem}_{suffix:02d}.csv" if self.output_prefix else f"{stem}_{suffix:02d}.csv"
            path = self.output_directory / filename
            suffix += 1
        return path

    def _open(self):
        if self._file is not None:
            return
        self.output_path = self._make_output_path()
        self._file = self.output_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(self.headers())
        self._file.flush()
        print(f"[Recorder] writing {self.output_path}")

    def headers(self):
        raise NotImplementedError

    def write_step(self):
        raise NotImplementedError

    def onAnimateBeginEvent(self, event):
        if not self._requested():
            if self._file is not None:
                self._file.flush()
                self._file.close()
                self._file = None
                self._writer = None
            return
        self._open()
        self.write_step()
        self._file.flush()


class RoiDisplacementCsvRecorder(_CsvRecorderBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.telemetry = kwargs["telemetry"]
        self.aorta_mechanical = kwargs["aorta_mechanical"]
        self.roi = kwargs["roi"]
        self.box = tuple(float(v) for v in kwargs["box"])
        self._indices = None
        self._initial_positions = None
        self._headers = None

    def _positions(self):
        return as_rows3(_read_data(self.aorta_mechanical, "position", []))

    def _ensure_roi_state(self):
        positions = self._positions()
        if self._indices is None:
            indices = _flat_indices(_read_data(self.roi, "indices", []))
            if not indices:
                x0, y0, z0, x1, y1, z1 = self.box
                xmin, xmax = min(x0, x1), max(x0, x1)
                ymin, ymax = min(y0, y1), max(y0, y1)
                zmin, zmax = min(z0, z1), max(z0, z1)
                indices = [
                    index
                    for index, point in enumerate(positions)
                    if xmin <= point[0] <= xmax and ymin <= point[1] <= ymax and zmin <= point[2] <= zmax
                ]
            self._indices = indices
            self._headers = ["time", "roi_force_modulus"]
            for index in self._indices:
                self._headers.extend([f"node_{index}_dx", f"node_{index}_dy", f"node_{index}_dz"])
        if self._initial_positions is None and positions and self._indices is not None:
            self._initial_positions = {
                index: list(positions[index]) for index in self._indices if 0 <= index < len(positions)
            }
        return positions

    def headers(self):
        self._ensure_roi_state()
        return self._headers or ["time"]

    def onAnimateBeginEvent(self, event):
        self._ensure_roi_state()
        super().onAnimateBeginEvent(event)

    def write_step(self):
        sample = self.telemetry.snapshot()
        positions = self._positions()
        row = [_fmt(sample["time"]), _fmt(_modulus(sample["applied_roi_force"]))]
        for index in self._indices or []:
            if 0 <= index < len(positions) and index in (self._initial_positions or {}):
                initial = self._initial_positions[index]
                displacement = [
                    positions[index][0] - initial[0],
                    positions[index][1] - initial[1],
                    positions[index][2] - initial[2],
                ]
            else:
                displacement = [float("nan"), float("nan"), float("nan")]
            row.extend(_fmt(value) for value in displacement)
        self._writer.writerow(row)


class CatheterTipCsvRecorder(_CsvRecorderBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.telemetry = kwargs["telemetry"]

    def headers(self):
        return [
            "time",
            "insertion_speed",
            "insertion",
            "rotation_deg",
            "tip_x",
            "tip_y",
            "tip_z",
            "tip_qx",
            "tip_qy",
            "tip_qz",
            "tip_qw",
            "tip_wall_force_x",
            "tip_wall_force_y",
            "tip_wall_force_z",
            "tip_wall_force_modulus",
            "tip_target_distance",
        ]

    def write_step(self):
        sample = self.telemetry.snapshot()
        force = [float(value) for value in sample["catheter_tip_wall_force"]]
        self._writer.writerow(
            [
                _fmt(sample["time"]),
                _fmt(sample["catheter_speed"]),
                _fmt(sample["catheter_insertion"]),
                _fmt(sample["catheter_rotation_deg"]),
                *[_fmt(value) for value in sample["catheter_tip"]],
                *[_fmt(value) for value in sample["catheter_tip_orientation"]],
                *[_fmt(value) for value in force],
                _fmt(_modulus(force)),
                _fmt(sample["tip_target_distance"]),
            ]
        )
