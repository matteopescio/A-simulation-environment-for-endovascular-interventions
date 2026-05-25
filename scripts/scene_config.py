from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MESHES_DIR = PROJECT_ROOT / "meshes"
DATA_DIR = PROJECT_ROOT / "data"


SCENE_CONFIG = {
    "paths": {
        "data_dir": str(DATA_DIR),
        "forces_dir": str(DATA_DIR / "forces"),
        "catheter_dir": str(DATA_DIR / "catheter"),
        "aneurysm_stl": str(MESHES_DIR / "AbdominalAorticAneurysm.stl"),
        "aneurysm_msh": str(MESHES_DIR / "AbdominalAorticAneurysm.msh"),
        "aorta_stl": str(MESHES_DIR / "AbdominalAorta.stl"),
        "aorta_msh": str(MESHES_DIR / "AbdominalAorta.msh"),
    },
    "simulation": {
        "dt": 0.006,
        "gravity": [0.0, 0.0, 0.0],
        "bbox": [-0.09, -0.12, -0.06, 0.09, 0.16, 0.07],
    },
    "collision": {
        "alarm_distance": 0.0012,
        "contact_distance": 0.0006,
        "angle_cone": 0.02,
        "friction": 0.001,
        "constraint_solver_tolerance": 1.0e-4,
        "constraint_solver_max_iterations": 2000,
        "enable_catheter_collision": True,
        "enable_aorta_collision": True,
        "collision_debug": False,
    },
    "aorta": {
        "scale": 1.0,
        "rotation": [0.0, 0.0, 0.0],
        "translation": [0.0, 0.0, 0.0],
        "total_mass": 0.002,
        "material_models": {
            "Elastic": {
                "young_modulus": 0.46e6,
                "poisson_ratio": 0.4,
            },
            "Neo Hookean": {
                "material_name": "NeoHookean",
                "parameter_set": [0.04e6, 200.0e6],
            },
            "Ogden": {
                "material_name": "Ogden",
                "parameter_set": [200.0e6, 0.2e6, 1.4],
            },
            "Mooney-Rivlin": {
                "material_name": "MooneyRivlin",
                "parameter_set": [0.09e6, 0.02e6, 200.0e6],
            },
        },
        "catheter_material": {
            "young_modulus": 5.0e9,
            "poisson_ratio": 0.4,
        },
        "fixed_boxes": [
            {
                "name": "fixedIliacEnd",
                "box": [-0.029, -0.006, -0.006, 0.004, -0.003, 0.006],
            },
            {
                "name": "fixedProximalEnd",
                "box": [-0.019, -0.080, 0.015, -0.008, -0.075, 0.025],
            },
        ],
        "catheter_fixed_boxes": [
            {
                "name": "fixedDistalEnd",
                "box": [-0.070, -0.092, -0.052, 0.082, -0.084, 0.026],
            },
            {
                "name": "fixedProximalEnd",
                "box": [-0.070, 0.134, -0.052, 0.082, 0.142, 0.026],
            },
        ],
        "force_box": {
            "name": "forceIliacROI",
            "box": [-0.009, -0.020, -0.006, 0.000, -0.010, 0.006],
        },
        "force_arrow_size": 0.3,
        "default_force_intensity": 0.0,
        "max_force_intensity": 2.0,
    },
    "catheter": {
        "enabled": False,
        "shape": "j",
        "total_length": 0.450,
        "straight_length": 0.4348,
        "j_tip_length": 0.0152,
        "j_tip_diameter": 0.0242,
        "radius": 0.0006,
        "poisson_ratio": 0.49,
        "mass_density": 2.1e-5,
        "young_modulus_straight": 8.0e4,
        "young_modulus_tip": 1.7e4,
        "insertion_point": [-0.051, 0.134, 0.004],
        "insertion_direction": [0.35, -0.934, -0.072],
        "target_point": [0.001, -0.084, 0.001],
        "navigation_centerline": [
            [-0.051, 0.134, 0.004],
            [-0.0475, 0.123, 0.0035],
            [-0.0404, 0.108, 0.0029],
            [-0.0326, 0.092, 0.0017],
            [-0.0258, 0.0777, 0.0003],
            [-0.0180, 0.062, 0.0002],
            [-0.0100, 0.047, -0.0006],
            [-0.0082, 0.033, 0.0003],
            [-0.0060, 0.016, 0.0060],
            [-0.0040, 0.000, 0.0070],
            [-0.0060, -0.020, 0.0060],
            [-0.0100, -0.040, 0.0048],
            [-0.0080, -0.060, 0.0030],
            [0.001, -0.084, 0.001],
        ],
        "virtual_fixture_radius": 0.024,
        "success_radius": 0.0006,
        "initial_xtip": 0.0,
        "min_insertion": 0.0,
        "max_insertion": 0.300,
        "rotation": 0.0,
        "min_rotation_deg": -180.0,
        "max_rotation_deg": 180.0,
        "speed": 0.001,
        "slow_debug_speed": 0.001,
        "step": 0.0001,
        "straight_nb_beams": 40,
        "j_tip_nb_beams": 22,
        "straight_nb_edges_collis": 44,
        "j_tip_nb_edges_collis": 31,
        "straight_nb_edges_visu": 218,
        "j_tip_nb_edges_visu": 8,
        "visual_radius": 0.0006,
        "visual_points_on_circle": 10,
        "color": [0.0, 0.0, 0.0, 1.0],
    },
    "camera": {
        "position": [-0.075, 0.020, 0.055],
        "look_at": [0.000, 0.020, 0.000],
    },
}
