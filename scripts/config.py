from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import importlib.util
from pathlib import Path


@dataclass(frozen=True)
class PathsConfig:
    data_dir: str
    forces_dir: str
    catheter_dir: str
    aneurysm_stl: str
    aneurysm_msh: str
    aorta_stl: str
    aorta_msh: str


@dataclass(frozen=True)
class MaterialModelConfig:
    young_modulus: float | None = None
    poisson_ratio: float | None = None
    material_name: str | None = None
    parameter_set: tuple[float, ...] = ()


@dataclass(frozen=True)
class BoxROIConfig:
    name: str
    box: tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class SimulationConfig:
    dt: float
    gravity: tuple[float, float, float]
    bbox: tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class CollisionConfig:
    alarm_distance: float
    contact_distance: float
    angle_cone: float
    friction: float
    constraint_solver_tolerance: float
    constraint_solver_max_iterations: int
    enable_catheter_collision: bool
    enable_aorta_collision: bool
    collision_debug: bool


@dataclass(frozen=True)
class AortaConfig:
    scale: float
    rotation: tuple[float, float, float]
    translation: tuple[float, float, float]
    total_mass: float
    material_models: dict[str, MaterialModelConfig]
    catheter_material: MaterialModelConfig
    fixed_boxes: tuple[BoxROIConfig, ...]
    catheter_fixed_boxes: tuple[BoxROIConfig, ...]
    force_box: BoxROIConfig
    force_arrow_size: float
    default_force_intensity: float
    max_force_intensity: float


@dataclass(frozen=True)
class CatheterConfig:
    enabled: bool
    shape: str
    total_length: float
    straight_length: float
    j_tip_length: float
    j_tip_diameter: float
    radius: float
    poisson_ratio: float
    mass_density: float
    young_modulus_straight: float
    young_modulus_tip: float
    insertion_point: tuple[float, float, float]
    insertion_direction: tuple[float, float, float]
    target_point: tuple[float, float, float]
    navigation_centerline: tuple[tuple[float, float, float], ...]
    virtual_fixture_radius: float
    success_radius: float
    initial_xtip: float
    min_insertion: float
    max_insertion: float
    rotation: float
    min_rotation_deg: float
    max_rotation_deg: float
    speed: float
    slow_debug_speed: float
    step: float
    straight_nb_beams: int
    j_tip_nb_beams: int
    straight_nb_edges_collis: int
    j_tip_nb_edges_collis: int
    straight_nb_edges_visu: int
    j_tip_nb_edges_visu: int
    visual_radius: float
    visual_points_on_circle: int
    color: tuple[float, float, float, float]


@dataclass(frozen=True)
class CameraConfig:
    position: tuple[float, float, float]
    look_at: tuple[float, float, float]


@dataclass(frozen=True)
class SceneConfig:
    paths: PathsConfig
    simulation: SimulationConfig
    collision: CollisionConfig
    aorta: AortaConfig
    catheter: CatheterConfig
    camera: CameraConfig


def _load_python_config(config_path: str | None = None) -> dict:
    cfg_path = Path(config_path) if config_path is not None else Path(__file__).with_name("scene_config.py")
    spec = importlib.util.spec_from_file_location("_endovascular_scene_config", cfg_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {cfg_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = getattr(module, "SCENE_CONFIG", None)
    if not isinstance(raw, dict):
        raise TypeError(f"{cfg_path} must define SCENE_CONFIG as a dict")
    return deepcopy(raw)


def _vec3(value):
    return (float(value[0]), float(value[1]), float(value[2]))


def _box_roi(raw_box):
    return BoxROIConfig(
        name=str(raw_box["name"]),
        box=tuple(float(v) for v in raw_box["box"]),
    )


def _material_models(raw_models):
    models = {}
    for name, values in raw_models.items():
        models[str(name)] = MaterialModelConfig(
            young_modulus=float(values["young_modulus"]) if "young_modulus" in values else None,
            poisson_ratio=float(values["poisson_ratio"]) if "poisson_ratio" in values else None,
            material_name=str(values["material_name"]) if "material_name" in values else None,
            parameter_set=tuple(float(v) for v in values.get("parameter_set", ())),
        )
    return models


def load_scene_config(config_path: str | None = None) -> SceneConfig:
    raw = _load_python_config(config_path)
    paths = raw["paths"]
    sim = raw["simulation"]
    collision = raw["collision"]
    aorta = raw["aorta"]
    catheter = raw["catheter"]
    camera = raw["camera"]

    return SceneConfig(
        paths=PathsConfig(**{key: str(value) for key, value in paths.items()}),
        simulation=SimulationConfig(
            dt=float(sim["dt"]),
            gravity=_vec3(sim["gravity"]),
            bbox=tuple(float(v) for v in sim["bbox"]),
        ),
        collision=CollisionConfig(
            alarm_distance=float(collision["alarm_distance"]),
            contact_distance=float(collision["contact_distance"]),
            angle_cone=float(collision["angle_cone"]),
            friction=float(collision["friction"]),
            constraint_solver_tolerance=float(collision["constraint_solver_tolerance"]),
            constraint_solver_max_iterations=int(collision["constraint_solver_max_iterations"]),
            enable_catheter_collision=bool(collision["enable_catheter_collision"]),
            enable_aorta_collision=bool(collision["enable_aorta_collision"]),
            collision_debug=bool(collision["collision_debug"]),
        ),
        aorta=AortaConfig(
            scale=float(aorta["scale"]),
            rotation=_vec3(aorta["rotation"]),
            translation=_vec3(aorta["translation"]),
            total_mass=float(aorta["total_mass"]),
            material_models=_material_models(aorta["material_models"]),
            catheter_material=_material_models({"catheter": aorta["catheter_material"]})["catheter"],
            fixed_boxes=tuple(_box_roi(box) for box in aorta["fixed_boxes"]),
            catheter_fixed_boxes=tuple(_box_roi(box) for box in aorta["catheter_fixed_boxes"]),
            force_box=_box_roi(aorta["force_box"]),
            force_arrow_size=float(aorta["force_arrow_size"]),
            default_force_intensity=float(aorta["default_force_intensity"]),
            max_force_intensity=float(aorta["max_force_intensity"]),
        ),
        catheter=CatheterConfig(
            enabled=bool(catheter["enabled"]),
            shape=str(catheter["shape"]),
            total_length=float(catheter["total_length"]),
            straight_length=float(catheter["straight_length"]),
            j_tip_length=float(catheter["j_tip_length"]),
            j_tip_diameter=float(catheter["j_tip_diameter"]),
            radius=float(catheter["radius"]),
            poisson_ratio=float(catheter["poisson_ratio"]),
            mass_density=float(catheter["mass_density"]),
            young_modulus_straight=float(catheter["young_modulus_straight"]),
            young_modulus_tip=float(catheter["young_modulus_tip"]),
            insertion_point=_vec3(catheter["insertion_point"]),
            insertion_direction=_vec3(catheter["insertion_direction"]),
            target_point=_vec3(catheter["target_point"]),
            navigation_centerline=tuple(_vec3(point) for point in catheter.get("navigation_centerline", ())),
            virtual_fixture_radius=float(catheter.get("virtual_fixture_radius", 0.0)),
            success_radius=float(catheter["success_radius"]),
            initial_xtip=float(catheter["initial_xtip"]),
            min_insertion=float(catheter["min_insertion"]),
            max_insertion=float(catheter["max_insertion"]),
            rotation=float(catheter["rotation"]),
            min_rotation_deg=float(catheter["min_rotation_deg"]),
            max_rotation_deg=float(catheter["max_rotation_deg"]),
            speed=float(catheter["speed"]),
            slow_debug_speed=float(catheter["slow_debug_speed"]),
            step=float(catheter["step"]),
            straight_nb_beams=int(catheter["straight_nb_beams"]),
            j_tip_nb_beams=int(catheter["j_tip_nb_beams"]),
            straight_nb_edges_collis=int(catheter["straight_nb_edges_collis"]),
            j_tip_nb_edges_collis=int(catheter["j_tip_nb_edges_collis"]),
            straight_nb_edges_visu=int(catheter["straight_nb_edges_visu"]),
            j_tip_nb_edges_visu=int(catheter["j_tip_nb_edges_visu"]),
            visual_radius=float(catheter["visual_radius"]),
            visual_points_on_circle=int(catheter["visual_points_on_circle"]),
            color=tuple(float(v) for v in catheter["color"]),
        ),
        camera=CameraConfig(position=_vec3(camera["position"]), look_at=_vec3(camera["look_at"])),
    )
