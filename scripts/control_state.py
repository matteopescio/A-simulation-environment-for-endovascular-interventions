from __future__ import annotations

import threading


def _clamp(value, min_value, max_value):
    return max(float(min_value), min(float(max_value), float(value)))


class ControlState:
    def __init__(self, config, catheter_enabled=False):
        self._lock = threading.Lock()
        self._config = config
        self._catheter_enabled = bool(catheter_enabled)
        self._roi_force_intensity = config.aorta.default_force_intensity
        self._catheter_insertion = config.catheter.initial_xtip
        self._catheter_rotation_deg = config.catheter.rotation
        self._catheter_auto_speed = config.catheter.speed
        self._catheter_auto_insert = False

    def catheter_enabled(self):
        with self._lock:
            return self._catheter_enabled

    def get_roi_force(self):
        with self._lock:
            return self._roi_force_intensity

    def set_roi_force(self, intensity=None):
        with self._lock:
            if intensity is not None:
                self._roi_force_intensity = _clamp(intensity, 0.0, self._config.aorta.max_force_intensity)
            return self._roi_force_intensity

    def get_catheter(self):
        with self._lock:
            return self._catheter_insertion, self._catheter_rotation_deg

    def get_catheter_speed(self):
        with self._lock:
            return self._catheter_auto_speed

    def set_catheter_speed(self, speed):
        with self._lock:
            self._catheter_auto_speed = _clamp(speed, 0.001, 0.035)
            return self._catheter_auto_speed

    def catheter_auto_running(self):
        with self._lock:
            return self._catheter_auto_insert

    def set_catheter_auto(self, running):
        with self._lock:
            self._catheter_auto_insert = bool(running) and self._catheter_enabled
            return self._catheter_auto_insert

    def toggle_catheter_auto(self):
        with self._lock:
            self._catheter_auto_insert = (not self._catheter_auto_insert) and self._catheter_enabled
            return self._catheter_auto_insert

    def advance_catheter_auto(self, dt):
        catheter = self._config.catheter
        with self._lock:
            if not self._catheter_enabled or not self._catheter_auto_insert:
                return self._catheter_insertion, self._catheter_rotation_deg
            next_insertion = self._catheter_insertion + float(dt) * self._catheter_auto_speed
            self._catheter_insertion = _clamp(next_insertion, catheter.min_insertion, catheter.max_insertion)
            if self._catheter_insertion >= catheter.max_insertion:
                self._catheter_auto_insert = False
            return self._catheter_insertion, self._catheter_rotation_deg

    def set_catheter(self, insertion=None, rotation_deg=None):
        catheter = self._config.catheter
        with self._lock:
            if insertion is not None:
                self._catheter_insertion = _clamp(insertion, catheter.min_insertion, catheter.max_insertion)
            if rotation_deg is not None:
                self._catheter_rotation_deg = _clamp(
                    rotation_deg,
                    catheter.min_rotation_deg,
                    catheter.max_rotation_deg,
                )
            return self._catheter_insertion, self._catheter_rotation_deg

    def reset_catheter(self):
        self.set_catheter_auto(False)
        return self.set_catheter(
            insertion=self._config.catheter.initial_xtip,
            rotation_deg=self._config.catheter.rotation,
        )

    def stop_and_set_catheter_insertion(self, insertion):
        catheter = self._config.catheter
        with self._lock:
            self._catheter_auto_insert = False
            self._catheter_insertion = _clamp(insertion, catheter.min_insertion, catheter.max_insertion)
            return self._catheter_insertion, self._catheter_rotation_deg
