from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from entry_utils import run_gui, scene_args


def parse_args():
    parser = argparse.ArgumentParser(description="Run the endovascular catheter-navigation scene.")
    return parser.parse_args(scene_args())


def createScene(rootNode):
    args = parse_args()
    from endovascular_scene import configure_scene, createScene as create_endovascular_scene

    configure_scene(
        mode="catheter",
        fem_model="Elastic",
    )
    return create_endovascular_scene(rootNode)


def main():
    args = parse_args()
    run_gui(
        __file__,
        mode="catheter",
        fem_model="Elastic",
    )


if __name__ == "__main__":
    main()
