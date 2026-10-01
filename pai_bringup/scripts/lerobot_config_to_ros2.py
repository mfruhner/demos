#!/usr/bin/env python3
"""Convert LeRobot calibration JSON files to feetech_ros2_driver YAML configs.

Usage:
    python3 scripts/lerobot_config_to_ros2.py config/lerobot/my_awesome_follower_arm.json config/hardware/follower.yaml
    python3 scripts/lerobot_config_to_ros2.py config/lerobot/my_awesome_leader_arm.json config/hardware/leader.yaml

The script reads calibration values (homing_offset, range_min, range_max) from
the JSON file and merges them into the existing YAML file, preserving all other
parameters (PID, acceleration, protection settings, etc.).

If the YAML file does not exist, a new one is created with sensible defaults
(leader gets minimal params, follower gets PID + protection for gripper).

First copy the lerobot config files to the config/lerobot directory:
cp ~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/my_awesome_leader_arm.json demos/pai_bringup/config/lerobot/
cp ~/.cache/huggingface/lerobot/calibration/robots/so_follower/my_awesome_follower_arm.json demos/pai_bringup/config/lerobot/
"""

import json
import sys
from pathlib import Path

import yaml


# Default extra params per variant
LEADER_DEFAULTS = {
    "return_delay_time": 0,
    "acceleration": 254,
}

FOLLOWER_DEFAULTS = {
    "p_coefficient": 16,
    "i_coefficient": 0,
    "d_coefficient": 32,
    "return_delay_time": 0,
    "acceleration": 254,
}

FOLLOWER_GRIPPER_EXTRAS = {
    "max_torque_limit": 500,
    "protection_current": 250,
    "overload_torque": 25,
}

# Fields to take from JSON calibration
CALIBRATION_KEYS = ("id", "homing_offset", "range_min", "range_max")


def detect_variant(json_path: str, yaml_path: str) -> str:
    """Guess leader/follower from file names."""
    combined = (json_path + yaml_path).lower()
    if "follower" in combined:
        return "follower"
    return "leader"


def load_existing_yaml(yaml_path: Path) -> dict:
    """Load existing YAML if present, return joints dict."""
    if not yaml_path.exists():
        return {}
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("joints", {})


def convert(json_path: str, yaml_path: str) -> None:
    with open(json_path) as f:
        calibration = json.load(f)

    variant = detect_variant(json_path, yaml_path)
    existing = load_existing_yaml(Path(yaml_path))

    joints = {}
    for joint_name, cal in calibration.items():
        # Start from existing YAML params if available
        params = dict(existing.get(joint_name, {}))

        # Apply calibration values from JSON (overwrite)
        for key in CALIBRATION_KEYS:
            if key in cal:
                params[key] = cal[key]

        # Fill in defaults for any missing non-calibration params
        defaults = FOLLOWER_DEFAULTS if variant == "follower" else LEADER_DEFAULTS
        for k, v in defaults.items():
            params.setdefault(k, v)

        if variant == "follower" and joint_name == "gripper":
            for k, v in FOLLOWER_GRIPPER_EXTRAS.items():
                params.setdefault(k, v)

        joints[f"{joint_name}_joint"] = params

    # Write YAML with consistent ordering
    output = {"joints": joints}
    with open(yaml_path, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False)

    print(f"Wrote {yaml_path} ({variant}, {len(joints)} joints)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.yaml>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
