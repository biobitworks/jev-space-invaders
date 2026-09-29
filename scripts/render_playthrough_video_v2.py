#!/usr/bin/env python3
"""v2 of render_playthrough_video.py (immutable atom of UFA-JEV-COMP-BP-0011).
Fixes: reverifies with verify_playthrough_custody_v2.py immediately before
encoding (fresh, not a possibly-stale receipt), and bounds ffmpeg's input to
exactly the freshly-verified frame count instead of an unbounded glob.
"""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def main() -> int:
    d = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "evidence/competition/frames/smoke")

    reverify = subprocess.run([sys.executable, str(ROOT / "scripts/verify_playthrough_custody_v2.py"), str(d)],
                               capture_output=True, text=True)
    if reverify.returncode != 0:
        raise SystemExit(f"refusing to render: fresh reverification failed\n{reverify.stdout}\n{reverify.stderr}")
    verify = json.loads((d / "PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V2.json").read_text())
    if verify["PLAYTHROUGH_VERIFY"] != "PASS":
        raise SystemExit(f"refusing to render: PLAYTHROUGH_VERIFY={verify['PLAYTHROUGH_VERIFY']}")

    frame_count = verify["frames_checked"]
    actual_png_count = len(list(d.glob("frame_*.png")))
    if actual_png_count != frame_count:
        raise SystemExit(f"refusing to render: {actual_png_count} PNG files present but only "
                          f"{frame_count} were just reverified (stale/extra frames in {d})")
    input_fps = 15
    output_fps = 15
    out_path = d / "canonical.mp4"
    cmd = ["ffmpeg", "-y", "-framerate", str(input_fps), "-i", str(d / "frame_%04d.png"),
           "-frames:v", str(frame_count), "-r", str(output_fps), "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-crf", "18", "-g", "15", "-an", str(out_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        raise SystemExit(f"ffmpeg failed rc={proc.returncode}\n{proc.stderr[-2000:]}")

    probe = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,nb_frames,codec_name",
                "-of", "json", str(out_path)])
    probe_json = json.loads(probe)["streams"][0]
    video_bytes = out_path.read_bytes()
    manifest = {
        "schema": "VIDEO_ENCODING_MANIFEST_V2",
        "ffmpeg_version": sh(["ffmpeg", "-version"]).splitlines()[0],
        "codec": probe_json.get("codec_name"),
        "resolution": f"{probe_json.get('width')}x{probe_json.get('height')}",
        "input_fps": input_fps, "output_fps": output_fps, "pixel_format": "yuv420p",
        "crf": 18, "gop": 15, "exact_command": " ".join(cmd),
        "frame_count_input": frame_count, "frame_count_output_reported": probe_json.get("nb_frames"),
        "video_file": str(out_path.relative_to(ROOT)), "video_bytes": len(video_bytes),
        "video_sha256": hashlib.sha256(video_bytes).hexdigest(),
        "source_playthrough_mmr_root": verify["recomputed_mmr_root"],
        "source_verify_state": verify["PLAYTHROUGH_VERIFY"],
        "reverified_immediately_before_encode": True,
        "label": "SETUP_SMOKE_NON_SUBMISSION_NON_EXPERIMENTAL",
    }
    (d / "VIDEO_ENCODING_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
