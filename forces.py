from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from entry_utils import run_gui, scene_args


def parse_args():
    parser = argparse.ArgumentParser(description="Run the endovascular aneurysm force-loading scene.")
    parser.add_argument(
        "-f",
        "--fem",
        choices=("Elastic", "Ogden", "Mooney-Rivlin", "Neo-Hookean"),
        default="Elastic",
        help="aneurysm FEM material model",
    )
    return parser.parse_args(scene_args())


def _fem_name(value):
    return "Neo Hookean" if value == "Neo-Hookean" else value


def createScene(rootNode):
    args = parse_args()
    from endovascular_scene import configure_scene, createScene as create_endovascular_scene

    configure_scene(
        mode="forces",
        fem_model=_fem_name(args.fem),
    )
    return create_endovascular_scene(rootNode)


def main():
    args = parse_args()
    run_gui(
        __file__,
        mode="forces",
        fem_model=_fem_name(args.fem),
    )


if __name__ == "__main__":
    main()
