from __future__ import annotations

import math
from pathlib import Path
import struct

from math_utils import as_rows3, modulus3, normalize3, scale3, sum_rows3

try:
    import Sofa
except Exception:
    Sofa = None


ControllerBase = Sofa.Core.Controller if Sofa is not None else object


def _set_data(component, data_name, value):
    try:
        component.findData(data_name).value = value
        return True
    except Exception:
        pass
    try:
        setattr(component, data_name, value)
        return True
    except Exception:
        return False


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


def _indices_in_box(positions, box):
    if not box:
        return []
    x0, y0, z0, x1, y1, z1 = [float(value) for value in box]
    xmin, xmax = min(x0, x1), max(x0, x1)
    ymin, ymax = min(y0, y1), max(y0, y1)
    zmin, zmax = min(z0, z1), max(z0, z1)
    return [
        index
        for index, point in enumerate(positions)
        if xmin <= point[0] <= xmax and ymin <= point[1] <= ymax and zmin <= point[2] <= zmax
    ]


def _mean_vector(rows):
    if not rows:
        return [0.0, 0.0, 0.0]
    count = float(len(rows))
    return [sum(row[i] for row in rows) / count for i in range(3)]


def _sub3(a, b):
    return [float(a[i]) - float(b[i]) for i in range(3)]


def _dot3(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _distance_to_segment(point, start, end):
    segment = _sub3(end, start)
    length_squared = _dot3(segment, segment)
    if length_squared <= 1.0e-16:
        return modulus3(_sub3(point, start))
    t = max(0.0, min(1.0, _dot3(_sub3(point, start), segment) / length_squared))
    closest = [float(start[i]) + t * segment[i] for i in range(3)]
    return modulus3(_sub3(point, closest))


class CenterlineFixture:
    def __init__(self, points, radius):
        self.points = [list(point) for point in points or []]
        self.radius = float(radius)

    def contains(self, point):
        if len(self.points) < 2 or self.radius <= 0.0:
            return True
        return min(_distance_to_segment(point, self.points[index], self.points[index + 1]) for index in range(len(self.points) - 1)) <= self.radius


def _load_binary_stl_triangles(path):
    mesh_path = Path(path)
    data = mesh_path.read_bytes()
    if len(data) < 84:
        return []
    triangle_count = struct.unpack("<I", data[80:84])[0]
    triangles = []
    offset = 84
    for _index in range(triangle_count):
        if offset + 50 > len(data):
            break
        values = struct.unpack("<12fH", data[offset : offset + 50])
        triangle = [
            [float(values[3]), float(values[4]), float(values[5])],
            [float(values[6]), float(values[7]), float(values[8])],
            [float(values[9]), float(values[10]), float(values[11])],
        ]
        triangles.append(triangle)
        offset += 50
    return triangles


def _ray_intersects_triangle_x(origin, triangle, epsilon=1.0e-10):
    oy = origin[1]
    oz = origin[2]
    p0, p1, p2 = triangle
    y0, z0 = p0[1], p0[2]
    y1, z1 = p1[1], p1[2]
    y2, z2 = p2[1], p2[2]
    denominator = (y1 - y2) * (z0 - z2) + (z2 - z1) * (y0 - y2)
    if abs(denominator) <= epsilon:
        return None
    a = ((y1 - y2) * (oz - z2) + (z2 - z1) * (oy - y2)) / denominator
    b = ((y2 - y0) * (oz - z2) + (z0 - z2) * (oy - y2)) / denominator
    c = 1.0 - a - b
    if a < -epsilon or b < -epsilon or c < -epsilon:
        return None
    x = a * p0[0] + b * p1[0] + c * p2[0]
    if x <= origin[0] + epsilon:
        return None
    return x


class MeshInteriorTest:
    def __init__(self, mesh_path):
        self.triangles = _load_binary_stl_triangles(mesh_path)
        points = [point for triangle in self.triangles for point in triangle]
        self.bounds = [
            min(point[0] for point in points),
            min(point[1] for point in points),
            min(point[2] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
            max(point[2] for point in points),
        ] if points else None

    def contains(self, point, margin=0.001):
        if not self.triangles or self.bounds is None:
            return True
        x, y, z = [float(value) for value in point[:3]]
        xmin, ymin, zmin, xmax, ymax, zmax = self.bounds
        if x < xmin - margin or x > xmax + margin or y < ymin - margin or y > ymax + margin or z < zmin - margin or z > zmax + margin:
            return False
        intersections = []
        for triangle in self.triangles:
            hit_x = _ray_intersects_triangle_x([x, y, z], triangle)
            if hit_x is None:
                continue
            intersections.append(hit_x)
        intersections.sort()
        unique = []
        for hit_x in intersections:
            if not unique or abs(hit_x - unique[-1]) > 1.0e-6:
                unique.append(hit_x)
        return len(unique) % 2 == 1


class AortaForceController(ControllerBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.control_state = kwargs["control_state"]
        self.force_field = kwargs["force_field"]
        self.direction = normalize3(kwargs["direction"])
        self.telemetry = kwargs.get("telemetry")
        self.roi_center = list(kwargs.get("roi_center", [0.0, 0.0, 0.0]))
        self._last_force = [0.0, 0.0, 0.0]

    def onAnimateBeginEvent(self, event):
        force = scale3(self.direction, self.control_state.get_roi_force())
        self._last_force = force
        if not _set_data(self.force_field, "totalForce", force):
            _set_data(self.force_field, "force", force)
        if self.telemetry is not None:
            self.telemetry.update(applied_roi_force=force, roi_center=self.roi_center)


class CatheterControlController(ControllerBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.control_state = kwargs["control_state"]
        self.deploy_controller = kwargs["deploy_controller"]
        self.telemetry = kwargs.get("telemetry")
        self.insertion_step = float(kwargs.get("insertion_step", 0.0001))
        self.target_point = [float(value) for value in kwargs.get("target_point", [float("nan"), float("nan"), float("nan")])]
        self.target_stop_distance = float(kwargs.get("target_stop_distance", 0.0))
        self.boundary = MeshInteriorTest(kwargs["boundary_mesh_path"]) if kwargs.get("boundary_mesh_path") else None
        self.fixture = CenterlineFixture(kwargs.get("virtual_fixture_centerline"), kwargs.get("virtual_fixture_radius", 0.0))
        self.catheter_collision_mechanical = kwargs.get("catheter_collision_mechanical")
        self._applied_insertion = None
        self._last_safe_insertion = 0.0
        self._last_warning_step = -1000
        self._target_reached = False
        self._step = 0

    def _context_dt(self):
        try:
            return float(self.getContext().findData("dt").value)
        except Exception:
            return 0.0

    def onAnimateBeginEvent(self, event):
        self._step += 1
        dt = self._context_dt()
        self.control_state.advance_catheter_auto(dt)
        requested_insertion, rotation_deg = self.control_state.get_catheter()
        if self._applied_insertion is None:
            self._applied_insertion = requested_insertion
        delta = requested_insertion - self._applied_insertion
        max_delta = max(1.0e-6, dt * self.control_state.get_catheter_speed(), self.insertion_step)
        if abs(delta) <= max_delta:
            self._applied_insertion = requested_insertion
        else:
            self._applied_insertion += max_delta if delta > 0.0 else -max_delta
        _set_data(self.deploy_controller, "xtip", [self._applied_insertion])
        _set_data(self.deploy_controller, "rotationInstrument", [math.radians(rotation_deg)])
        if self.telemetry is not None:
            self.telemetry.update(catheter_insertion=self._applied_insertion, catheter_rotation_deg=rotation_deg)

    def _catheter_inside_boundary(self):
        if self.catheter_collision_mechanical is None:
            return True
        points = as_rows3(_read_data(self.catheter_collision_mechanical, "position", []))
        if not points:
            return True
        # The entry point lies on the cap, so ignore the first sample closest to the base.
        checked_points = points[1:] if len(points) > 1 else points
        if len(self.fixture.points) >= 2:
            return all(self.fixture.contains(point) for point in checked_points)
        if self.boundary is None:
            return True
        return all(self.boundary.contains(point) for point in checked_points)

    def onAnimateEndEvent(self, event):
        if self._applied_insertion is None:
            return
        points = as_rows3(_read_data(self.catheter_collision_mechanical, "position", []))
        if points and self.target_stop_distance > 0.0:
            tip_distance = modulus3(_sub3(points[-1], self.target_point))
            if tip_distance <= self.target_stop_distance:
                self.control_state.set_catheter_auto(False)
                if not self._target_reached:
                    print(
                        "[CatheterControl] target reached; "
                        f"tip-target distance {tip_distance * 1000.0:.3f} mm"
                    )
                self._target_reached = True
                self._last_safe_insertion = self._applied_insertion
                return
        if self._catheter_inside_boundary():
            self._last_safe_insertion = self._applied_insertion
            return
        self._applied_insertion = self._last_safe_insertion
        self.control_state.set_catheter(insertion=self._last_safe_insertion)
        _set_data(self.deploy_controller, "xtip", [self._last_safe_insertion])
        if self._step - self._last_warning_step > 50:
            print(
                "[CatheterBoundary] catheter left the AbdominalAorta mesh; "
                f"rolled insertion back to {self._last_safe_insertion * 1000.0:.2f} mm"
            )
            self._last_warning_step = self._step


class ForceTelemetryController(ControllerBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.telemetry = kwargs["telemetry"]
        self.aorta_mechanical = kwargs.get("aorta_mechanical")
        self.catheter_collision_mechanical = kwargs.get("catheter_collision_mechanical")
        self.catheter_dofs_mechanical = kwargs.get("catheter_dofs_mechanical")
        self.control_state = kwargs["control_state"]
        self.roi = kwargs.get("roi")
        self.roi_box = kwargs.get("roi_box")
        self._roi_indices = None
        self._initial_roi_points = None

    def _context_time(self):
        try:
            return float(self.getContext().findData("time").value)
        except Exception:
            return 0.0

    def _roi_sample(self, positions):
        if self.roi is None:
            return {}
        if self._roi_indices is None:
            self._roi_indices = _flat_indices(_read_data(self.roi, "indices", []))
            if not self._roi_indices:
                self._roi_indices = _indices_in_box(positions, self.roi_box)
        points = [positions[index] for index in self._roi_indices if 0 <= index < len(positions)]
        if self._initial_roi_points is None and points:
            self._initial_roi_points = [list(point) for point in points]
        initial = self._initial_roi_points or []
        displacements = [
            [point[0] - start[0], point[1] - start[1], point[2] - start[2]]
            for point, start in zip(points, initial)
        ]
        sample = self.telemetry.snapshot()
        total_force = [float(value) for value in sample.get("applied_roi_force", [0.0, 0.0, 0.0])]
        count = max(1, len(points))
        return {
            "roi_points": points,
            "roi_average_force": [value / count for value in total_force],
            "roi_average_displacement": _mean_vector(displacements),
        }

    def onAnimateBeginEvent(self, event):
        aorta_force = sum_rows3(_read_data(self.aorta_mechanical, "force", []))
        aorta_positions = as_rows3(_read_data(self.aorta_mechanical, "position", []))
        catheter_forces = as_rows3(_read_data(self.catheter_collision_mechanical, "force", []))
        catheter_force = sum_rows3(catheter_forces)
        catheter_path = as_rows3(_read_data(self.catheter_collision_mechanical, "position", []))
        catheter_tip = catheter_path[-1] if catheter_path else [float("nan"), float("nan"), float("nan")]
        tip_wall_force = [-value for value in catheter_forces[-1]] if catheter_forces else [0.0, 0.0, 0.0]
        catheter_dofs = _read_data(self.catheter_dofs_mechanical, "position", [])
        tip_orientation = [float("nan"), float("nan"), float("nan"), float("nan")]
        try:
            if catheter_dofs is not None and len(catheter_dofs) > 0:
                last_dof = list(catheter_dofs[-1])
                if len(last_dof) >= 7:
                    tip_orientation = [float(value) for value in last_dof[3:7]]
        except Exception:
            pass
        insertion, rotation_deg = self.control_state.get_catheter()
        catheter_speed = self.control_state.get_catheter_speed()

        self.telemetry.update(
            time=self._context_time(),
            aorta_force=aorta_force,
            catheter_force=catheter_force,
            catheter_tip_wall_force=tip_wall_force,
            catheter_path=catheter_path,
            catheter_tip=catheter_tip,
            catheter_tip_orientation=tip_orientation,
            catheter_insertion=insertion,
            catheter_speed=catheter_speed,
            catheter_rotation_deg=rotation_deg,
            **self._roi_sample(aorta_positions),
        )


class StabilityDiagnosticsController(ControllerBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.telemetry = kwargs["telemetry"]
        self.aorta_mechanical = kwargs.get("aorta_mechanical")
        self.catheter_mechanical = kwargs.get("catheter_mechanical")
        self.control_state = kwargs["control_state"]
        self.target_point = [float(v) for v in kwargs["target_point"]]
        self.success_radius = float(kwargs["success_radius"])
        self.max_insertion = float(kwargs["max_insertion"])
        self.collision_debug = bool(kwargs.get("collision_debug", False))
        self.print_every = max(1, int(kwargs.get("print_every", 25)))
        self._initial_aorta_positions = None
        self._step = 0

    def _store_initial_positions(self, positions):
        if self._initial_aorta_positions is None and positions:
            self._initial_aorta_positions = [list(point) for point in positions]

    def _displacements(self, positions):
        if not self._initial_aorta_positions or len(positions) != len(self._initial_aorta_positions):
            return 0.0, 0.0
        values = []
        for point, initial in zip(positions, self._initial_aorta_positions):
            values.append(modulus3([point[0] - initial[0], point[1] - initial[1], point[2] - initial[2]]))
        if not values:
            return 0.0, 0.0
        return max(values), sum(values) / len(values)

    def _has_nan(self, rows):
        for row in rows:
            for value in row[:3]:
                if not math.isfinite(float(value)):
                    return True
        return False

    def _update(self):
        self._step += 1
        aorta_positions = as_rows3(_read_data(self.aorta_mechanical, "position", []))
        catheter_path = as_rows3(_read_data(self.catheter_mechanical, "position", []))
        self._store_initial_positions(aorta_positions)

        max_displacement, mean_displacement = self._displacements(aorta_positions)
        catheter_tip = catheter_path[-1] if catheter_path else [float("nan"), float("nan"), float("nan")]
        tip_valid = not self._has_nan([catheter_tip])
        tip_target_distance = (
            modulus3([catheter_tip[0] - self.target_point[0], catheter_tip[1] - self.target_point[1], catheter_tip[2] - self.target_point[2]])
            if tip_valid
            else float("nan")
        )
        insertion, _rotation_deg = self.control_state.get_catheter()
        success = bool(tip_valid and tip_target_distance < self.success_radius)

        self.telemetry.update(
            max_phantom_displacement=max_displacement,
            mean_phantom_displacement=mean_displacement,
            tip_target_distance=tip_target_distance,
            target_reached=success,
        )

        if self._has_nan(aorta_positions):
            print("[Diagnostics] NaN detected in phantom DOFs")
        if catheter_path and self._has_nan(catheter_path):
            print("[Diagnostics] NaN detected in catheter DOFs")
        if max_displacement > 0.005:
            print(f"[Diagnostics] large phantom displacement: max={max_displacement:.6g} m")
        if insertion > self.max_insertion + 1.0e-9:
            print(f"[Diagnostics] insertion exceeds configured max: {insertion:.6g} > {self.max_insertion:.6g}")
        if not tip_valid and catheter_path:
            print("[Diagnostics] invalid catheter tip position")

        if self.collision_debug and self._step % self.print_every == 0:
            print(
                "[Diagnostics] "
                f"step={self._step} insertion={insertion:.6g} "
                f"maxDisp={max_displacement:.6g} meanDisp={mean_displacement:.6g} "
                f"tip={catheter_tip} targetDist={tip_target_distance:.6g}"
            )

    def onAnimateEndEvent(self, event):
        self._update()
