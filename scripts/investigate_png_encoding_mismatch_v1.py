#!/usr/bin/env python3
"""Successor investigation: is the PNG_BYTES mismatch in the environment replay encoder drift only?
Comparison-only use of committed PNGs; does not alter the replay verdict."""
import hashlib, io, json, struct, sys, zlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FR = ROOT / "evidence/competition/final_execution/frames"
sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image
import ale_py, gymnasium as gym
gym.register_envs(ale_py)

def chunks(b):
    i, out = 8, []
    while i < len(b):
        n, t = struct.unpack(">I4s", b[i:i+8]); out.append((t.decode(), n)); i += 12 + n
    return out

rows = [json.loads(l) for l in (FR / "FRAME_BREAKPOINT_LEAVES.jsonl").read_text().splitlines()]
env = gym.make("ALE/SpaceInvaders-v5", obs_type="rgb", frameskip=1, repeat_action_probability=0.25,
               full_action_space=False, max_num_frames_per_episode=108000)
obs, info = env.reset(seed=3)
A = ("NOOP","FIRE","RIGHT","LEFT","RIGHTFIRE","LEFTFIRE")
pix_equal = raw_equal = idat_equal_after_decompress = 0
first_chunks = None
for i, row in enumerate(rows):
    committed = (FR / f"frame_{i:04d}.png").read_bytes()
    cimg = np.array(Image.open(io.BytesIO(committed)).convert("RGB"))
    raw_equal += hashlib.sha256(obs.tobytes()).hexdigest() == json.loads((FR / f"frame_{i:04d}.occurrence.json").read_text())["content_sha256"]
    pix_equal += bool(np.array_equal(cimg, obs))
    buf = io.BytesIO(); Image.fromarray(obs).save(buf, format="PNG"); mine = buf.getvalue()
    def idat(b):
        i0, data = 8, b""
        while i0 < len(b):
            n, t = struct.unpack(">I4s", b[i0:i0+8])
            if t == b"IDAT": data += b[i0+8:i0+8+n]
            i0 += 12 + n
        return zlib.decompress(data)
    idat_equal_after_decompress += idat(committed) == idat(mine)
    if i == 0: first_chunks = {"committed": chunks(committed), "regenerated": chunks(mine)}
    obs, *_ = env.step(A.index(row["action"]))
env.close()
n = len(rows)
res = {"schema": "PNG_ENCODING_MISMATCH_INVESTIGATION_V1", "frames": n,
       "raw_rgb_hash_equal_frames": raw_equal, "decoded_committed_png_pixels_equal_generated_frames": pix_equal,
       "decompressed_idat_stream_equal_frames": idat_equal_after_decompress,
       "frame0_png_chunks": first_chunks, "png_bytes_equal_frames": 0,
       "PIL": Image.__version__ if hasattr(Image, "__version__") else None, "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
       "finding": ("ENCODER_DRIFT_ONLY" if raw_equal == n and pix_equal == n else "PIXEL_LEVEL_DIVERGENCE"),
       "does_not_change": "ENVIRONMENT_REPLAY verdict of the strict contract stays FAIL",
       "proposal_not_applied": "A v2 step-hash contract defined over raw RGB (not PNG bytes) would be encoder-independent; it must be adopted prospectively, not retroactively."}
print(json.dumps({k: v for k, v in res.items() if k != "frame0_png_chunks"}, indent=1))
Path(sys.argv[1]).write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
