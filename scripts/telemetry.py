from __future__ import annotations

import threading


class TelemetryState:
    def __init__(self):
        self._lock = threading.Lock()
        self._sample = {
            "time": 0.0,
            "aorta_force": [0.0, 0.0, 0.0],
            "catheter_force": [0.0, 0.0, 0.0],
            "applied_roi_force": [0.0, 0.0, 0.0],
            "roi_average_force": [0.0, 0.0, 0.0],
            "roi_average_displacement": [0.0, 0.0, 0.0],
            "roi_center": [0.0, 0.0, 0.0],
            "roi_points": [],
            "catheter_tip": [float("nan"), float("nan"), float("nan")],
            "catheter_tip_orientation": [float("nan"), float("nan"), float("nan"), float("nan")],
            "catheter_tip_wall_force": [0.0, 0.0, 0.0],
            "catheter_path": [],
            "catheter_insertion": 0.0,
            "catheter_speed": 0.0,
            "catheter_rotation_deg": 0.0,
            "max_phantom_displacement": 0.0,
            "mean_phantom_displacement": 0.0,
            "tip_target_distance": float("nan"),
            "target_reached": False,
        }

    def update(self, **kwargs):
        with self._lock:
            self._sample.update(kwargs)

    def snapshot(self):
        with self._lock:
            sample = dict(self._sample)
            sample["aorta_force"] = list(sample["aorta_force"])
            sample["catheter_force"] = list(sample["catheter_force"])
            sample["applied_roi_force"] = list(sample["applied_roi_force"])
            sample["roi_average_force"] = list(sample["roi_average_force"])
            sample["roi_average_displacement"] = list(sample["roi_average_displacement"])
            sample["roi_center"] = list(sample["roi_center"])
            sample["roi_points"] = [list(point) for point in sample["roi_points"]]
            sample["catheter_tip"] = list(sample["catheter_tip"])
            sample["catheter_tip_orientation"] = list(sample["catheter_tip_orientation"])
            sample["catheter_tip_wall_force"] = list(sample["catheter_tip_wall_force"])
            sample["catheter_path"] = [list(point) for point in sample["catheter_path"]]
            return sample
