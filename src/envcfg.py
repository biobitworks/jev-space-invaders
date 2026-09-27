"""Single source of the environment configuration used by every run and smoke test."""
from __future__ import annotations

from src.actions import ACTIONS

ENV_CONFIG = {
    "env_id": "ALE/SpaceInvaders-v5",
    "frameskip": 4,
    "repeat_action_probability": 0.25,
    "full_action_space": False,
    "max_num_frames_per_episode": 108000,
    "obs_type": "rgb",
    "wrappers": [],
    "decision_interval_steps": 1,
}


def make_env():
    import ale_py
    import gymnasium as gym

    gym.register_envs(ale_py)
    c = ENV_CONFIG
    env = gym.make(c["env_id"], obs_type=c["obs_type"], frameskip=c["frameskip"],
                   repeat_action_probability=c["repeat_action_probability"],
                   full_action_space=c["full_action_space"],
                   max_num_frames_per_episode=c["max_num_frames_per_episode"])
    meanings = tuple(env.unwrapped.get_action_meanings())
    if meanings != ACTIONS:
        raise RuntimeError(f"ALE action set {meanings} != expected {ACTIONS}")
    return env


def runtime_versions() -> dict:
    import platform
    import sys
    from importlib.metadata import version

    def v(name):
        try:
            return version(name)
        except Exception:
            return None

    return {"python": sys.version.split()[0], "platform": platform.platform(),
            "ale_py": v("ale-py"), "gymnasium": v("gymnasium"), "numpy": v("numpy")}
