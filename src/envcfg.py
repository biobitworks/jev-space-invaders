"""Single source of the environment configuration used by every run and smoke test."""
from __future__ import annotations

from src.actions import ACTIONS

ENV_CONFIG = {
    "env_id": "ALE/SpaceInvaders-v5",
    "frameskip": 4,   # effective: each decision is held for 4 emulator frames (see wrappers)
    "repeat_action_probability": 0.25,
    "full_action_space": False,
    "max_num_frames_per_episode": 108000,
    "obs_type": "rgb",
    "wrappers": ["RepeatActionMaxPool(k=4, pool=max of last 2 frames) over ALE frameskip=1"],
    "decision_interval_steps": 1,
}
# Why: Space Invaders draws enemy bombs on alternate frames. With the built-in frameskip=4
# the returned frame always has the same parity and never shows a bomb. Stepping frame by
# frame and max-pooling the last two frames is the standard Atari preprocessing; the
# emulator receives exactly the same ale.act sequence, so dynamics, rewards, sticky-action
# RNG and episode_frame_number are unchanged (checked in tests/test_envcfg.py).
K = 4


class RepeatActionMaxPool:
    def __init__(self, env):
        self.env = env
        self.unwrapped = env.unwrapped

    def reset(self, **kw):
        return self.env.reset(**kw)

    def step(self, action):
        import numpy as np

        total, prev, obs = 0.0, None, None
        term = trunc = False
        info = {}
        for _ in range(K):
            prev = obs
            obs, r, term, trunc, info = self.env.step(action)
            total += float(r)
            if term or trunc:
                break
        pooled = obs if prev is None else np.maximum(prev, obs)
        return pooled, total, term, trunc, info

    def close(self):
        self.env.close()


def make_env():
    import ale_py
    import gymnasium as gym

    gym.register_envs(ale_py)
    c = ENV_CONFIG
    env = gym.make(c["env_id"], obs_type=c["obs_type"], frameskip=1,
                   repeat_action_probability=c["repeat_action_probability"],
                   full_action_space=c["full_action_space"],
                   max_num_frames_per_episode=c["max_num_frames_per_episode"])
    meanings = tuple(env.unwrapped.get_action_meanings())
    if meanings != ACTIONS:
        raise RuntimeError(f"ALE action set {meanings} != expected {ACTIONS}")
    return RepeatActionMaxPool(env)


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
