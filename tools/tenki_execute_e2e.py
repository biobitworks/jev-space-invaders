#!/usr/bin/env python3
"""Fresh Tenki sandbox -> clone -> pin exact commit -> run verifiers -> collect sanitized results -> terminate.
Usage: tenki_execute_e2e.py <commit> <session_id> <result.json>. Key only via TENKI_API_KEY env; nothing secret
is ever sent into the sandbox (public repo clone only). Termination happens inside the client scope."""
import json, os, sys
from tenki import Client

commit, session, outp = sys.argv[1], sys.argv[2], sys.argv[3]
REPO = "https://github.com/biobitworks/jev-space-invaders.git"
key = os.environ["TENKI_API_KEY"]
res = {"schema": "TENKI_EXECUTION_RAW_RESULT_V1", "execution_locus": "TENKI_SANDBOX", "pre_tenki_commit": commit,
       "session_label": session, "sandbox_create": "NOT_EXECUTED", "tenki_session_id": None,
       "source_pin": "NOT_EXECUTED", "commands": [], "terminated": "NOT_EXECUTED"}


def tail(b, n=2500):
    return b.decode(errors="replace")[-n:].replace(key, "<redacted>")


def run(sb, name, cmd, cwd=None, timeout=900):
    r = sb.exec("bash", "-c", cmd, cwd=cwd, timeout=timeout)
    res["commands"].append({"name": name, "exit_code": r.exit_code, "timed_out": r.timed_out,
                            "stdout_tail": tail(r.stdout), "stderr_tail": tail(r.stderr, 800)})
    print(f"[{name}] exit={r.exit_code}", file=sys.stderr)
    return r


def execute(sb):
    run(sb, "tooling", "python3 --version; git --version; uname -sm")
    if run(sb, "git_clone", f"git clone -q {REPO} repo").exit_code != 0:
        return
    run(sb, "git_checkout", f"git checkout -q {commit}", cwd="repo")
    head = run(sb, "git_rev_parse", "git rev-parse HEAD", cwd="repo").stdout_text.strip()
    res["observed_head"] = head
    res["source_pin"] = "PASS" if head == commit else "FAIL"
    if res["source_pin"] != "PASS":
        return
    run(sb, "venv", "python3 -m venv .venv || (apt-get install -y -qq python3-venv >/dev/null 2>&1; python3 -m venv .venv)", cwd="repo")
    run(sb, "pip_install", ".venv/bin/pip install -q gymnasium==1.3.0 ale-py==0.12.1 numpy==2.5.3 pillow cryptography", cwd="repo", timeout=1200)
    run(sb, "versions", ".venv/bin/python -c \"import sys,ale_py,gymnasium,numpy,PIL,cryptography as c;print({'python':sys.version.split()[0],'ale_py':ale_py.__version__,'gymnasium':gymnasium.__version__,'numpy':numpy.__version__,'PIL':PIL.__version__,'cryptography':c.__version__})\"", cwd="repo")
    P = ".venv/bin/python"
    run(sb, "env_replay", f"{P} scripts/verify_environment_replay_v1.py --receipt /tmp/tenki_env_replay.json --locus TENKI_SANDBOX", cwd="repo")
    try:
        res["env_replay_receipt"] = json.loads(sb.fs.read_text("/tmp/tenki_env_replay.json"))
    except Exception as e:  # noqa: BLE001
        res["env_replay_receipt_error"] = type(e).__name__
    run(sb, "playthrough_custody", f"{P} scripts/verify_final_playthrough_custody_v2.py evidence/competition/final_execution/frames", cwd="repo")
    run(sb, "competition_lineage", f"{P} scripts/verify_competition_lineage.py", cwd="repo")
    run(sb, "claims_verifier", f"{P} tools/verify_mitosis_tenki_claims.py", cwd="repo")
    run(sb, "e2e_breakpoints", f"{P} scripts/verify_e2e_breakpoints.py --upto {sys.argv[4] if len(sys.argv) > 4 else 'VITHIA-E2E-POSTSUBMISSION-BP-0001'}", cwd="repo")


try:
    with Client(api_key=key) as c:
        sb = None
        try:
            sb = c.create(name=f"vithia-e2e-{session[-16:].lower()}", cpu_cores=2, memory_mb=4096, sticky=False,
                          max_duration=1800, metadata={"purpose": "vithia-e2e-postsubmission-verification"})
            res["sandbox_create"], res["tenki_session_id"] = "PASS", sb.id
            execute(sb)
        finally:
            if sb is not None:
                try:
                    sb.close_if_open()
                    res["terminated"] = "PASS"
                except Exception as e:  # noqa: BLE001
                    res["terminated"], res["terminate_error"] = "FAIL", type(e).__name__
except Exception as e:  # noqa: BLE001
    res["error_class"], res["error"] = type(e).__name__, str(e).replace(key, "<redacted>")[:400]
finally:
    open(outp, "w").write(json.dumps(res, indent=1, sort_keys=True) + "\n")
print(json.dumps({k: res[k] for k in ("sandbox_create", "tenki_session_id", "source_pin", "terminated")}))
