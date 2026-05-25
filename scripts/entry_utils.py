from __future__ import annotations

from pathlib import Path
import shlex
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def scene_args():
    args = list(sys.argv[1:])
    expanded = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--argv" and index + 1 < len(args):
            expanded.extend(shlex.split(args[index + 1]))
            index += 2
            continue
        if arg.startswith("--argv="):
            expanded.extend(shlex.split(arg.split("=", 1)[1]))
            index += 1
            continue
        if arg.lstrip().startswith("-") and any(char.isspace() for char in arg):
            expanded.extend(shlex.split(arg))
            index += 1
            continue
        expanded.append(arg)
        index += 1
    return expanded


def yes_no(value):
    normalized = str(value).strip().lower()
    if normalized == "yes":
        return True
    if normalized == "no":
        return False
    raise ValueError(f"Expected yes or no, got {value!r}")


def run_gui(script_file, mode, fem_model="Elastic"):
    import Sofa
    import Sofa.Gui
    import Sofa.Simulation

    from endovascular_scene import configure_scene, createScene

    configure_scene(
        mode=mode,
        fem_model=fem_model,
    )
    root = Sofa.Core.Node("root")
    createScene(root)
    Sofa.Simulation.initRoot(root)

    Sofa.Gui.GUIManager.Init(f"endovascular_{mode}", "imgui")
    Sofa.Gui.GUIManager.createGUI(root, script_file)
    Sofa.Gui.GUIManager.SetDimension(1280, 900)
    Sofa.Gui.GUIManager.MainLoop(root)
    Sofa.Gui.GUIManager.closeGUI()
