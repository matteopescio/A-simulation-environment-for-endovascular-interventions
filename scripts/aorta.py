from __future__ import annotations

from pathlib import Path
import math
import struct


def _require_mesh(path):
    if Path(path).exists():
        return
    raise FileNotFoundError(
        f"Required mesh not found: {path}\n"
        f"Place the configured STL/MSH pair under {Path(path).parent}."
    )


def _sofa_stl_path(path):
    source = Path(path)
    with source.open("rb") as handle:
        header = handle.read(84)
    if len(header) != 84:
        return str(source)

    triangle_count = struct.unpack("<I", header[80:84])[0]
    expected_size = 84 + triangle_count * 50
    actual_size = source.stat().st_size
    if actual_size == expected_size:
        return str(source)
    if actual_size < expected_size:
        return str(source)

    cleaned = source.with_name(f"{source.stem}_sofa.stl")
    if cleaned.exists() and cleaned.stat().st_size == expected_size:
        return str(cleaned)

    with source.open("rb") as src, cleaned.open("wb") as dst:
        remaining = expected_size
        while remaining > 0:
            chunk = src.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            dst.write(chunk)
            remaining -= len(chunk)
    return str(cleaned)


def _normalize_fem_model(fem_model):
    normalized = str(fem_model).strip().lower().replace("_", " ").replace("-", " ")
    if normalized in {"neo hookean", "neohookean"}:
        return "Neo Hookean"
    if normalized == "ogden":
        return "Ogden"
    if normalized in {"mooney rivlin", "mooneyrivlin"}:
        return "Mooney-Rivlin"
    return "Elastic"


def _add_material_forcefield(node, config, fem_model, topology="tetra"):
    model_name = _normalize_fem_model(fem_model)
    if topology == "triangle":
        material = config.aorta.catheter_material
        print(
            "[Endovascular] FEM model: Plastic elastic surface "
            f"(TriangularFEMForceField, youngModulus={material.young_modulus}, "
            f"poissonRatio={material.poisson_ratio})"
        )
        node.addObject(
            "TriangularFEMForceField",
            name="SurfaceElasticMaterial",
            template="Vec3d",
            youngModulus=material.young_modulus,
            poissonRatio=material.poisson_ratio,
            method="large",
        )
        return "Elastic"

    material = config.aorta.material_models[model_name]
    if model_name == "Elastic":
        print(
            "[Endovascular] FEM model: Elastic "
            f"(TetrahedronFEMForceField, youngModulus={material.young_modulus}, "
            f"poissonRatio={material.poisson_ratio})"
        )
        node.addObject(
            "TetrahedronFEMForceField",
            name="ElasticMaterial",
            template="Vec3d",
            youngModulus=material.young_modulus,
            poissonRatio=material.poisson_ratio,
            method="large",
        )
    else:
        parameters = " ".join(str(value) for value in material.parameter_set)
        print(
            "[Endovascular] FEM model: "
            f"{model_name} (TetrahedronHyperelasticityFEMForceField, "
            f"materialName={material.material_name}, ParameterSet={parameters})"
        )
        node.addObject(
            "TetrahedronHyperelasticityFEMForceField",
            name="HyperElasticMaterial",
            materialName=material.material_name,
            ParameterSet=parameters,
            AnisotropyDirections="",
        )
    return model_name


def _positive_x_negative_y_box_direction(box):
    x0, y0, _z0, x1, y1, _z1 = box
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    norm = math.sqrt(dx * dx + dy * dy)
    if norm <= 1.0e-12:
        return [1.0, -1.0, 0.0]
    return [dx / norm, -dy / norm, 0.0]


def _mesh_paths(config, mesh):
    if mesh == "catheter":
        return config.paths.aorta_stl, config.paths.aorta_msh
    return config.paths.aneurysm_stl, config.paths.aneurysm_msh


def create_aorta(
    root,
    config,
    fem_model="Elastic",
    enable_collision=True,
    rigid_collision_debug=False,
    mesh="aneurysm",
    enable_force_roi=True,
):
    stl_path, msh_path = _mesh_paths(config, mesh)
    _require_mesh(stl_path)
    _require_mesh(msh_path)
    stl_path = _sofa_stl_path(stl_path)

    aorta_cfg = config.aorta
    topology = "triangle" if mesh == "catheter" else "tetra"
    node = root.addChild("Aorta")
    node.addObject("EulerImplicitSolver", name="ode", rayleighStiffness=0.2, rayleighMass=0.1)
    node.addObject("CGLinearSolver", name="linearSolver", iterations=200, tolerance=1e-09, threshold=1e-09)
    node.addObject("MeshGmshLoader", name="volumeLoader", filename=msh_path, createSubelements=True, flipNormals=False)
    if topology == "triangle":
        node.addObject("TriangleSetTopologyContainer", name="topology", src="@volumeLoader")
        node.addObject("TriangleSetTopologyModifier", name="topologyModifier")
        node.addObject("TriangleSetGeometryAlgorithms", name="geometry", template="Vec3d")
    else:
        node.addObject("TetrahedronSetTopologyContainer", name="topology", src="@volumeLoader")
        node.addObject("TetrahedronSetTopologyModifier", name="topologyModifier")
        node.addObject("TetrahedronSetGeometryAlgorithms", name="geometry", template="Vec3d")
    mechanical = node.addObject(
        "MechanicalObject",
        name="MechanicalModel",
        template="Vec3d",
        src="@volumeLoader",
        scale=aorta_cfg.scale,
        rotation=list(aorta_cfg.rotation),
        translation=list(aorta_cfg.translation),
        showObject=False,
        showObjectScale=0.0,
    )
    material_model = _add_material_forcefield(node, config, fem_model, topology=topology)
    node.addObject("MeshMatrixMass", name="mass", totalMass=aorta_cfg.total_mass)

    fixed_boxes = aorta_cfg.catheter_fixed_boxes if mesh == "catheter" else aorta_cfg.fixed_boxes
    for index, roi in enumerate(fixed_boxes):
        node.addObject("BoxROI", name=roi.name, box=list(roi.box), drawBoxes=True)
        node.addObject("FixedProjectiveConstraint", name=f"fixedEnd{index + 1}", indices=f"@{roi.name}.indices")

    force_roi = None
    force_field = None
    force_direction = [0.0, 0.0, 0.0]
    if enable_force_roi:
        force_roi = aorta_cfg.force_box
        node.addObject("BoxROI", name=force_roi.name, box=list(force_roi.box), drawBoxes=True)
        force_kwargs = {
            "name": "ROIOutwardForce",
            "indices": f"@{force_roi.name}.indices",
            "totalForce": [0.0, 0.0, 0.0],
            "showArrowSize": aorta_cfg.force_arrow_size,
        }
        force_field = node.addObject("ConstantForceField", **force_kwargs)
        force_direction = _positive_x_negative_y_box_direction(force_roi.box)
    node.addObject("UncoupledConstraintCorrection")

    collision_mo = None
    if enable_collision:
        collision = node.addChild("Collision")
        collision.addObject("MeshSTLLoader", name="surfaceLoader", filename=stl_path, triangulate=True, flipNormals=False)
        collision.addObject("TriangleSetTopologyContainer", name="topology", src="@surfaceLoader")
        collision_mo = collision.addObject(
            "MechanicalObject",
            name="CollisionMO",
            src="@surfaceLoader",
            scale=aorta_cfg.scale,
            rotation=list(aorta_cfg.rotation),
            translation=list(aorta_cfg.translation),
        )
        moving = not rigid_collision_debug
        simulated = not rigid_collision_debug
        collision.addObject("TriangleCollisionModel", name="triangles", moving=moving, simulated=simulated, bothSide=True)
        collision.addObject("LineCollisionModel", name="lines", moving=moving, simulated=simulated, bothSide=True)
        collision.addObject("PointCollisionModel", name="points", moving=moving, simulated=simulated, bothSide=True)
        if not rigid_collision_debug:
            collision.addObject("BarycentricMapping", name="mapping", input="@../MechanicalModel", output="@CollisionMO")

    visual = node.addChild("Visual")
    visual.addObject("MeshSTLLoader", name="surfaceLoader", filename=stl_path, triangulate=True, flipNormals=False)
    visual_color = [1.0, 1.0, 1.0, 0.42] if mesh == "catheter" else [0.85, 0.12, 0.12, 0.55]
    visual.addObject(
        "OglModel",
        name="VisualModel",
        src="@surfaceLoader",
        color=visual_color,
        scale=aorta_cfg.scale,
        rotation=list(aorta_cfg.rotation),
        translation=list(aorta_cfg.translation),
    )
    visual.addObject("BarycentricMapping", name="mapping", input="@../MechanicalModel", output="@VisualModel")

    return {
        "node": node,
        "mechanical": mechanical,
        "force_field": force_field,
        "force_roi": force_roi,
        "force_direction": force_direction,
        "collision_mechanical": collision_mo,
        "material_model": material_model,
    }
