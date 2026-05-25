from __future__ import annotations

import math

from aorta import create_aorta
from catheter_model import create_catheter
from config import load_scene_config
from control_panel import start_catheter_control_panel_once, start_force_control_panel_once
from control_state import ControlState
from controllers import (
    AortaForceController,
    CatheterControlController,
    ForceTelemetryController,
    StabilityDiagnosticsController,
)
from recorders import CatheterTipCsvRecorder, RoiDisplacementCsvRecorder
from telemetry import TelemetryState


CONFIG = load_scene_config()
CONTROL = None
TELEMETRY = None
FEM_MODEL = "Elastic"
SCENE_MODE = "forces"
RECORDING_STATE = None


def configure_scene(mode="forces", fem_model="Elastic"):
    global CONTROL, TELEMETRY, FEM_MODEL, SCENE_MODE, RECORDING_STATE
    SCENE_MODE = str(mode)
    FEM_MODEL = "Elastic" if SCENE_MODE == "catheter" else str(fem_model)
    RECORDING_STATE = {
        "displacement_requested": False,
        "insertion_requested": False,
    }
    CONTROL = ControlState(CONFIG, catheter_enabled=SCENE_MODE == "catheter")
    TELEMETRY = TelemetryState()


def _box_center(box):
    return [
        (float(box[0]) + float(box[3])) * 0.5,
        (float(box[1]) + float(box[4])) * 0.5,
        (float(box[2]) + float(box[5])) * 0.5,
    ]


def _camera_pose():
    if SCENE_MODE == "forces":
        return {
            "position": [-0.050, -0.044, 0.050],
            "look_at": [-0.012, -0.040, 0.008],
            "field_of_view": 32,
        }
    return {
        "position": list(CONFIG.camera.position),
        "look_at": list(CONFIG.camera.look_at),
        "field_of_view": 45,
    }


def _fem_filename_label(fem_model):
    model = str(fem_model).strip()
    if model == "Neo Hookean":
        return "Neo-Hookean"
    return model.replace(" ", "-")


def _icosahedron_marker(center, radius):
    phi = (1.0 + math.sqrt(5.0)) * 0.5
    raw_vertices = [
        [-1.0, phi, 0.0],
        [1.0, phi, 0.0],
        [-1.0, -phi, 0.0],
        [1.0, -phi, 0.0],
        [0.0, -1.0, phi],
        [0.0, 1.0, phi],
        [0.0, -1.0, -phi],
        [0.0, 1.0, -phi],
        [phi, 0.0, -1.0],
        [phi, 0.0, 1.0],
        [-phi, 0.0, -1.0],
        [-phi, 0.0, 1.0],
    ]
    vertices = []
    for vertex in raw_vertices:
        norm = math.sqrt(sum(value * value for value in vertex))
        vertices.append([center[i] + radius * vertex[i] / norm for i in range(3)])
    triangles = [
        [0, 11, 5],
        [0, 5, 1],
        [0, 1, 7],
        [0, 7, 10],
        [0, 10, 11],
        [1, 5, 9],
        [5, 11, 4],
        [11, 10, 2],
        [10, 7, 6],
        [7, 1, 8],
        [3, 9, 4],
        [3, 4, 2],
        [3, 2, 6],
        [3, 6, 8],
        [3, 8, 9],
        [4, 9, 5],
        [2, 4, 11],
        [6, 2, 10],
        [8, 6, 7],
        [9, 8, 1],
    ]
    return vertices, triangles


def _add_marker_sphere(parent, name, center, color, radius=0.003):
    marker = parent.addChild(name)
    vertices, triangles = _icosahedron_marker([float(value) for value in center], radius)
    marker.addObject(
        "OglModel",
        name="VisualMarker",
        position=vertices,
        triangles=triangles,
        color=color,
    )


def _add_plugins(root):
    plugins = root.addChild("Plugins")
    plugins.addObject("RequiredPlugin", name="BeamAdapterPlugin", pluginName="BeamAdapter")
    plugins.addObject(
        "RequiredPlugin",
        name="CoreComponents",
        pluginName=(
            "Sofa.Component.AnimationLoop "
            "Sofa.Component.Collision.Detection.Algorithm "
            "Sofa.Component.Collision.Detection.Intersection "
            "Sofa.Component.Collision.Geometry "
            "Sofa.Component.Collision.Response.Contact "
            "Sofa.Component.Constraint.Lagrangian.Correction "
            "Sofa.Component.Constraint.Lagrangian.Solver "
            "Sofa.Component.Constraint.Projective "
            "Sofa.Component.Engine.Select "
            "Sofa.Component.IO.Mesh "
            "Sofa.Component.LinearSolver.Direct "
            "Sofa.Component.LinearSolver.Iterative "
            "Sofa.Component.Mapping.Linear "
            "Sofa.Component.Mass "
            "Sofa.Component.MechanicalLoad "
            "Sofa.Component.ODESolver.Backward "
            "Sofa.Component.SolidMechanics.FEM.Elastic "
            "Sofa.Component.SolidMechanics.FEM.HyperElastic "
            "Sofa.Component.SolidMechanics.Spring "
            "Sofa.Component.StateContainer "
            "Sofa.Component.Topology.Container.Constant "
            "Sofa.Component.Topology.Container.Dynamic "
            "Sofa.Component.Topology.Container.Grid "
            "Sofa.Component.Topology.Mapping "
            "Sofa.Component.Visual "
            "Sofa.GUI.Component "
            "Sofa.GL.Component.Rendering3D"
        ),
    )


def _add_markers(root):
    markers = root.addChild("NavigationMarkers")
    _add_marker_sphere(markers, "CatheterStartSphere", CONFIG.catheter.insertion_point, [1.0, 0.82, 0.0, 1.0])
    markers.addObject(
        "MechanicalObject",
        name="StartMarkerPosition",
        template="Vec3d",
        position=[list(CONFIG.catheter.insertion_point)],
    )
    markers.addObject(
        "ConstantForceField",
        name="StartMarker",
        indices=[0],
        forces=[[0.0, 0.001, 0.0]],
        showArrowSize=0.01,
    )
    target = markers.addChild("Target")
    _add_marker_sphere(target, "CatheterTargetSphere", CONFIG.catheter.target_point, [0.0, 0.85, 1.0, 1.0])
    target.addObject(
        "MechanicalObject",
        name="TargetMarkerPosition",
        template="Vec3d",
        position=[list(CONFIG.catheter.target_point)],
    )
    target.addObject(
        "ConstantForceField",
        name="TargetMarker",
        indices=[0],
        forces=[[0.0, 0.0, -0.001]],
        showArrowSize=0.01,
    )


def createScene(rootNode, mode=None, fem_model=None):
    if CONTROL is None or any(value is not None for value in (mode, fem_model)):
        configure_scene(
            mode=SCENE_MODE if mode is None else mode,
            fem_model=FEM_MODEL if fem_model is None else fem_model,
        )

    rootNode.dt = CONFIG.simulation.dt
    rootNode.gravity = list(CONFIG.simulation.gravity)
    rootNode.bbox = " ".join(str(v) for v in CONFIG.simulation.bbox)
    rootNode.showBoundingTree = 0

    _add_plugins(rootNode)
    rootNode.addObject(
        "VisualStyle",
        displayFlags="showVisualModels hideBehaviorModels hideCollisionModels hideBoundingCollisionModels hideMappings hideForceFields hideInteractionForceFields",
    )
    rootNode.addObject("OglSceneFrame", style="Arrows", alignment="TopRight")
    camera = _camera_pose()
    rootNode.addObject(
        "InteractiveCamera",
        name="camera",
        position=camera["position"],
        lookAt=camera["look_at"],
        fieldOfView=camera["field_of_view"],
        zNear=0.0001,
        zFar=1000.0,
        computeZClip=0,
        activated=1,
        listening=1,
        fixedLookAt=0,
    )

    rootNode.addObject("FreeMotionAnimationLoop")
    rootNode.addObject("DefaultVisualManagerLoop")
    collision = CONFIG.collision
    rootNode.addObject(
        "LCPConstraintSolver",
        name="constraintSolver",
        mu=collision.friction,
        tolerance=collision.constraint_solver_tolerance,
        maxIt=collision.constraint_solver_max_iterations,
        build_lcp=False,
    )
    rootNode.addObject(
        "CollisionPipeline",
        draw=collision.collision_debug,
        depth=6,
        verbose=collision.collision_debug,
    )
    rootNode.addObject("BruteForceBroadPhase", name="broadPhase")
    rootNode.addObject("BVHNarrowPhase", name="narrowPhase")
    rootNode.addObject(
        "LocalMinDistance",
        name="proximity",
        contactDistance=collision.contact_distance,
        alarmDistance=collision.alarm_distance,
        angleCone=collision.angle_cone,
        filterIntersection=False,
        useLMDFilters=False,
    )
    rootNode.addObject(
        "CollisionResponse",
        name="contactResponse",
        response="FrictionContactConstraint",
        responseParams=f"mu={collision.friction}",
    )

    if SCENE_MODE == "catheter":
        start_catheter_control_panel_once(CONTROL, CONFIG, recording_state=RECORDING_STATE)
    else:
        start_force_control_panel_once(CONTROL, CONFIG, recording_state=RECORDING_STATE)

    aorta = create_aorta(
        rootNode,
        CONFIG,
        fem_model=FEM_MODEL,
        enable_collision=collision.enable_aorta_collision,
        rigid_collision_debug=False,
        mesh="catheter" if SCENE_MODE == "catheter" else "aneurysm",
        enable_force_roi=SCENE_MODE == "forces",
    )
    catheter_handles = None
    if SCENE_MODE == "catheter":
        catheter_handles = create_catheter(rootNode, CONFIG, enable_collision=collision.enable_catheter_collision)
        _add_markers(rootNode)

    if SCENE_MODE == "forces":
        rootNode.addObject(
            AortaForceController(
                name="ROIForceController",
                listening=True,
                control_state=CONTROL,
                force_field=aorta["force_field"],
                direction=aorta["force_direction"],
                roi_center=_box_center(CONFIG.aorta.force_box.box),
                telemetry=TELEMETRY,
            )
        )

    if catheter_handles is not None:
        rootNode.addObject(
            CatheterControlController(
                name="CatheterControlController",
                listening=True,
                control_state=CONTROL,
                deploy_controller=catheter_handles["controller"],
                telemetry=TELEMETRY,
                insertion_step=CONFIG.catheter.step,
                catheter_collision_mechanical=catheter_handles["collision_mechanical"],
                target_point=CONFIG.catheter.target_point,
                target_stop_distance=collision.contact_distance,
                boundary_mesh_path=CONFIG.paths.aorta_stl,
                virtual_fixture_centerline=CONFIG.catheter.navigation_centerline,
                virtual_fixture_radius=CONFIG.catheter.virtual_fixture_radius,
            )
        )

    rootNode.addObject(
        ForceTelemetryController(
            name="ForceTelemetryController",
            listening=True,
            telemetry=TELEMETRY,
            aorta_mechanical=aorta["mechanical"],
            catheter_collision_mechanical=(
                catheter_handles["collision_mechanical"] or catheter_handles["dofs"] if catheter_handles else None
            ),
            catheter_dofs_mechanical=catheter_handles["dofs"] if catheter_handles else None,
            control_state=CONTROL,
            roi=aorta["force_roi"] if SCENE_MODE == "forces" else None,
            roi_box=CONFIG.aorta.force_box.box if SCENE_MODE == "forces" else None,
        )
    )
    rootNode.addObject(
        StabilityDiagnosticsController(
            name="StabilityDiagnosticsController",
            listening=True,
            telemetry=TELEMETRY,
            aorta_mechanical=aorta["mechanical"],
            catheter_mechanical=(
                catheter_handles["collision_mechanical"] or catheter_handles["dofs"] if catheter_handles else None
            ),
            control_state=CONTROL,
            target_point=CONFIG.catheter.target_point,
            success_radius=collision.contact_distance,
            max_insertion=CONFIG.catheter.max_insertion,
            collision_debug=collision.collision_debug,
            print_every=25,
        )
    )

    if SCENE_MODE == "forces":
        rootNode.addObject(
            RoiDisplacementCsvRecorder(
                name="RoiDisplacementCsvRecorder",
                telemetry=TELEMETRY,
                aorta_mechanical=aorta["mechanical"],
                roi=aorta["force_roi"],
                box=CONFIG.aorta.force_box.box,
                recording_state=RECORDING_STATE,
                request_key="displacement_requested",
                output_directory=CONFIG.paths.data_dir,
                output_prefix=f"forces_{_fem_filename_label(FEM_MODEL)}",
            )
        )

    if SCENE_MODE == "catheter" and catheter_handles is not None:
        rootNode.addObject(
            CatheterTipCsvRecorder(
                name="CatheterTipCsvRecorder",
                telemetry=TELEMETRY,
                recording_state=RECORDING_STATE,
                request_key="insertion_requested",
                output_directory=CONFIG.paths.data_dir,
                output_prefix="catheter",
            )
        )

    return rootNode
