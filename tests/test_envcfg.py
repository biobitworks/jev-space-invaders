import gymnasium as gym
import numpy as np

from src.envcfg import make_env


def _run(env, seed, n=300):
    obs, info = env.reset(seed=seed)
    out = []
    for t in range(n):
        obs, r, term, trunc, info = env.step((7 * t + seed) % 6)
        out.append((float(r), int(info["lives"]), int(info["episode_frame_number"]), bool(term)))
        if term or trunc:
            break
    return out


def test_wrapper_matches_builtin_frameskip_dynamics():
    import ale_py
    gym.register_envs(ale_py)
    for seed in (1, 2, 3):
        ref = gym.make("ALE/SpaceInvaders-v5", obs_type="rgb", frameskip=4, repeat_action_probability=0.25)
        assert _run(make_env(), seed) == _run(ref, seed)


def test_bombs_visible_after_pooling():
    env = make_env()
    env.reset(seed=1)
    seen = 0
    for t in range(400):
        obs, *_ = env.step(4 if (t // 30) % 2 == 0 else 5)
        g = (obs[20:195] == (142, 142, 142)).all(-1)
        seen = max(seen, len(set(np.nonzero(g)[1])))
    assert seen >= 2  # own shot + at least one enemy bomb in some frame
