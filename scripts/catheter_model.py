from __future__ import annotations

import math

from math_utils import normalize3


def _normalize_quaternion(quaternion):
    norm = math.sqrt(sum(float(v) * float(v) for v in quaternion))
    if norm <= 1.0e-12:
        return [0.0, 0.0, 0.0, 1.0]
    return [float(v) / norm for v in quaternion]


def compute_starting_pose(insertion_point, insertion_direction):
    direction = normalize3(insertion_direction)
    if direction == [0.0, 0.0, 0.0]:
        direction = [1.0, 0.0, 0.0]

    dot = direction[0]
    if dot < -0.999999:
        quaternion = [0.0, 0.0, 1.0, 0.0]
    else:
        axis = [0.0, -direction[2], direction[1]]
        quaternion = _normalize_quaternion([axis[0], axis[1], axis[2], 1.0 + dot])
    return [float(insertion_point[0]), float(insertion_point[1]), float(insertion_point[2])] + quaternion


def create_catheter(root, config, enable_collision=True):
    catheter = config.catheter
    use_j_tip = catheter.shape.lower() == "j"

    topo = root.addChild("CatheterTopology")
    topo.addObject(
        "RodStraightSection",
        name="StraightSection",
        length=catheter.straight_length,
        radius=catheter.radius,
        nbBeams=catheter.straight_nb_beams,
        nbEdgesCollis=catheter.straight_nb_edges_collis,
        nbEdgesVisu=catheter.straight_nb_edges_visu,
        youngModulus=catheter.young_modulus_straight,
        massDensity=catheter.mass_density,
        poissonRatio=catheter.poisson_ratio,
    )
    wire_materials = "@StraightSection"

    if use_j_tip:
        topo.addObject(
            "RodSpireSection",
            name="JTipSection",
            length=catheter.j_tip_length,
            radius=catheter.radius,
            nbBeams=catheter.j_tip_nb_beams,
            nbEdgesCollis=catheter.j_tip_nb_edges_collis,
            nbEdgesVisu=catheter.j_tip_nb_edges_visu,
            spireDiameter=catheter.j_tip_diameter,
            spireHeight=0.0,
            youngModulus=catheter.young_modulus_tip,
            massDensity=catheter.mass_density,
            poissonRatio=catheter.poisson_ratio,
        )
        wire_materials = "@StraightSection @JTipSection"

    topo.addObject("WireRestShape", name="CatheterRestShape", template="Rigid3d", wireMaterials=wire_materials)
    topo.addObject("EdgeSetTopologyContainer", name="meshLines")
    topo.addObject("EdgeSetTopologyModifier", name="modifier")
    topo.addObject("EdgeSetGeometryAlgorithms", name="geometry", template="Rigid3d")
    topo.addObject("MechanicalObject", name="dofTopo", template="Rigid3d")

    model = root.addChild("Catheter")
    model.addObject("EulerImplicitSolver", name="ode", rayleighStiffness=0.2, rayleighMass=0.1)
    model.addObject("BTDLinearSolver", name="linearSolver", verification=False, subpartSolve=False, verbose=False)
    model.addObject(
        "RegularGridTopology",
        name="MeshLines",
        nx=catheter.straight_nb_beams + (catheter.j_tip_nb_beams if use_j_tip else 0) + 1,
        ny=1,
        nz=1,
        xmin=0.0,
        xmax=0.0,
        ymin=0.0,
        ymax=0.0,
        zmin=0.0,
        zmax=0.0,
        p0=[0.0, 0.0, 0.0],
    )
    dofs = model.addObject("MechanicalObject", name="DOFs", template="Rigid3d", showIndices=False)
    interpolation = model.addObject(
        "WireBeamInterpolation",
        name="BeamInterpolation",
        WireRestShape="@../CatheterTopology/CatheterRestShape",
        printLog=False,
    )
    model.addObject(
        "AdaptiveBeamForceFieldAndMass",
        name="BeamForceField",
        massDensity=catheter.mass_density,
        interpolation="@BeamInterpolation",
        printLog=False,
    )
    controller = model.addObject(
        "InterventionalRadiologyController",
        name="DeployController",
        template="Rigid3d",
        instruments="BeamInterpolation",
        topology="@MeshLines",
        startingPos=compute_starting_pose(catheter.insertion_point, catheter.insertion_direction),
        xtip=[catheter.initial_xtip],
        rotationInstrument=[math.radians(catheter.rotation)],
        step=catheter.step,
        speed=catheter.speed,
        listening=True,
        controlledInstrument=0,
        printLog=False,
    )
    model.addObject("LinearSolverConstraintCorrection", name="constraintCorrection", wire_optimization=True, printLog=False)
    model.addObject("FixedProjectiveConstraint", name="fixedBase", indices=0)
    model.addObject(
        "RestShapeSpringsForceField",
        name="baseSpring",
        points="@DeployController.indexFirstNode",
        angularStiffness=1e8,
        stiffness=1e8,
    )

    collision_mo = None
    if enable_collision:
        collision = model.addChild("Collision")
        collision.activated = True
        collision.addObject("EdgeSetTopologyContainer", name="collisEdgeSet")
        collision.addObject("EdgeSetTopologyModifier", name="collisEdgeModifier")
        collision_mo = collision.addObject("MechanicalObject", name="CollisionDOFs")
        collision.addObject(
            "MultiAdaptiveBeamMapping",
            name="collisMap",
            controller="@../DeployController",
            useCurvAbs=True,
            printLog=False,
        )
        collision.addObject("LineCollisionModel", name="lines", contactDistance=0.0, bothSide=True)
        collision.addObject("PointCollisionModel", name="points", contactDistance=0.0, bothSide=True)

    visual = model.addChild("Visual")
    visual.addObject("MechanicalObject", name="Quads")
    visual.addObject("QuadSetTopologyContainer", name="Container")
    visual.addObject("QuadSetTopologyModifier", name="Modifier")
    visual.addObject("QuadSetGeometryAlgorithms", name="Geometry", template="Vec3d")
    visual.addObject(
        "Edge2QuadTopologicalMapping",
        name="EdgeToQuad",
        radius=catheter.visual_radius,
        listening=True,
        input="@../../CatheterTopology/meshLines",
        nbPointsOnEachCircle=catheter.visual_points_on_circle,
        flipNormals=True,
        output="@Container",
    )
    visual.addObject(
        "AdaptiveBeamMapping",
        name="visualMap",
        interpolation="@../BeamInterpolation",
        output="@Quads",
        isMechanical=False,
        input="@../DOFs",
        useCurvAbs=True,
        printLog=False,
    )
    ogl = visual.addChild("Ogl")
    ogl.addObject("OglModel", name="VisualModel", color=list(catheter.color), quads="@../Container.quads")
    ogl.addObject("IdentityMapping", input="@../Quads", output="@VisualModel")

    return {
        "node": model,
        "dofs": dofs,
        "controller": controller,
        "interpolation": interpolation,
        "collision_mechanical": collision_mo,
        "j_tip_enabled": use_j_tip,
    }
