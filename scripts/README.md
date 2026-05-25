# Scripts Guide

This folder contains the shared implementation used by the two main SOFA entry points in the project root:

- `../forces.py`
- `../catheter.py`

The root scripts only parse command-line arguments and select the scenario. The actual scene construction, model definitions, controllers, GUI panels, telemetry, and CSV recording are implemented here.

## Scene Flow

Both entry points call `endovascular_scene.configure_scene(...)` and then `endovascular_scene.createScene(rootNode)`.

The scene creation flow is:

1. Load typed configuration from `scene_config.py` through `config.py`.
2. Add required SOFA and BeamAdapter plugins.
3. Add camera, animation loop, collision pipeline, contact solver, and visual style.
4. Build the aorta/phantom model with `aorta.py`.
5. Optionally build the BeamAdapter catheter with `catheter_model.py`.
6. Add controllers from `controllers.py`.
7. Add CSV recorders from `recorders.py`.
8. Start the small Tk control panel from `control_panel.py`.

## File Overview

### `scene_config.py`

Central configuration dictionary for the project. It defines:

- Mesh and output paths.
- Simulation timestep and bounding box.
- Collision/contact parameters.
- Aorta material models and ROI boxes.
- Catheter geometry, material, insertion start/target, speed limits, and virtual fixture centerline.
- Default camera position.

This is the first file to edit when tuning geometry, material parameters, ROI positions, catheter dimensions, or collision distances.

### `config.py`

Typed dataclass wrapper around `scene_config.py`.

It converts the raw dictionary into structured config objects such as `SceneConfig`, `AortaConfig`, `CatheterConfig`, and `CollisionConfig`. The rest of the code uses these typed objects instead of reading the raw dictionary directly.

### `endovascular_scene.py`

Main scene assembly file.

It contains:

- Global scene mode selection: `forces` or `catheter`.
- Plugin loading.
- Camera setup.
- SOFA collision and constraint pipeline.
- Aorta creation.
- Catheter creation for the catheter scene.
- Marker creation for catheter start and target.
- Controller and recorder attachment.

The two supported modes are:

- `forces`: aneurysm phantom, force ROI, displacement recording.
- `catheter`: simplified aorta phantom, J-shaped BeamAdapter catheter, catheter insertion recording.

### `aorta.py`

Builds the deformable phantom/aorta model.

Responsibilities:

- Load the configured `.msh` FEM mesh and `.stl` visual/collision mesh.
- Select the correct topology:
  - tetrahedral FEM for the aneurysm force scene;
  - triangular FEM surface model for the simplified catheter scene.
- Add material force fields:
  - Elastic, Ogden, Mooney-Rivlin, or Neo-Hookean for the aneurysm scene;
  - plastic elastic surface material for the catheter scene.
- Add fixed BoxROI constraints.
- Add the force BoxROI and `ConstantForceField` in the force scene.
- Add mapped visual and collision surface models.

The `_sofa_stl_path(...)` helper creates a cleaned `_sofa.stl` copy if SOFA needs an STL without trailing bytes.

### `catheter_model.py`

Builds the J-shaped catheter using BeamAdapter.

The catheter is assembled from:

- `RodStraightSection` for the shaft.
- `RodSpireSection` for the J-shaped tip.
- `WireRestShape`.
- `WireBeamInterpolation`.
- `AdaptiveBeamForceFieldAndMass`.
- `InterventionalRadiologyController`.
- Beam collision and visual mappings.

The helper `compute_starting_pose(...)` aligns the catheter local axis with the configured insertion direction.

### `controllers.py`

Runtime SOFA controllers.

Important classes:

- `AortaForceController`: reads the GUI force slider and updates the ROI `ConstantForceField`.
- `CatheterControlController`: advances catheter insertion, applies rotation, checks target distance, and rolls back unsafe catheter states that leave the virtual fixture.
- `ForceTelemetryController`: samples aorta forces, catheter forces, ROI points, catheter tip pose, and catheter path data into shared telemetry.
- `StabilityDiagnosticsController`: monitors phantom displacement, catheter tip validity, NaNs, insertion bounds, and target distance.

It also contains geometric helper classes for the catheter virtual fixture and basic mesh-bound checks.

### `control_state.py`

Thread-safe state shared between the SOFA simulation loop and the Tk GUI.

It stores:

- ROI force intensity.
- Catheter insertion.
- Catheter rotation.
- Catheter insertion speed.
- Autonomous insertion start/stop state.

### `control_panel.py`

Tk GUI panels.

The force scene panel contains:

- ROI force intensity slider.
- `Record Displacement` / `Stop Recording` button.

The catheter scene panel contains:

- Catheter insertion speed slider in `mm/s`.
- Catheter rotation slider.
- `Start Insertion` / `Stop Insertion`.
- `Catheter Reset`.
- `Record Insertion` / `Stop Recording`.

The GUI is intentionally separate from SOFA state updates. It only writes to `ControlState` and recording flags.

### `telemetry.py`

Thread-safe telemetry buffer.

Controllers write the latest simulation values here, and recorders read snapshots from it. Stored data includes:

- Time.
- Aorta force.
- Applied ROI force.
- ROI points and average displacement.
- Catheter path.
- Catheter tip position and orientation.
- Catheter tip-wall force.
- Insertion speed, insertion length, rotation, and tip-target distance.

### `recorders.py`

CSV recording controllers.

Recorders open files only when the corresponding GUI record button is active.

Outputs:

- `RoiDisplacementCsvRecorder`
  - `data/forces_FEMTYPE_YYYYMMDD_HHMMSS.csv`
  - Columns begin with `time`, `roi_force_modulus`, then `node_ID_dx`, `node_ID_dy`, `node_ID_dz` for every node in the force ROI.
- `CatheterTipCsvRecorder`
  - `data/catheter_YYYYMMDD_HHMMSS.csv`
  - Columns include time, insertion speed, insertion length, rotation, tip position, tip quaternion, tip-wall force, force modulus, and tip-target distance.

### `entry_utils.py`

Utilities used by the root entry scripts.

It handles:

- `--argv` expansion for SOFA command-line usage.
- Programmatic GUI launch through SOFA Python APIs.
- Shared path setup for local script imports.

### `math_utils.py`

Small vector helpers used by controllers and scene construction:

- row conversion;
- vector normalization;
- vector scaling;
- vector sums;
- vector modulus.

### `__init__.py`

Marks this folder as a Python package. The project mostly uses direct script imports because SOFA Python scenes are commonly loaded as files rather than installed packages.

## Data Flow

Force scene:

```text
GUI slider
  -> ControlState
  -> AortaForceController
  -> ConstantForceField on force ROI
  -> ForceTelemetryController
  -> RoiDisplacementCsvRecorder
```

Catheter scene:

```text
GUI speed/start/rotation controls
  -> ControlState
  -> CatheterControlController
  -> InterventionalRadiologyController
  -> BeamAdapter catheter model
  -> ForceTelemetryController
  -> CatheterTipCsvRecorder
```

## Tuning Notes

- Mesh and material changes should start in `scene_config.py`.
- Collision distances are in meters. The current defaults are millimetre-scale.
- The catheter virtual fixture is a manually configured centerline corridor. If the catheter stops too early or is allowed too far from the lumen, tune `navigation_centerline` and `virtual_fixture_radius`.
- The force scene and catheter scene intentionally use different aorta meshes and material assumptions.
