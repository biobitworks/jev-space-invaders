#!/usr/bin/env python3
"""Fresh Tenki sandbox -> clone -> pin exact commit -> run seed-declared verifiers -> terminate.
Usage: tenki_execute_seed.py <repo_url> <commit> <session_label> <out.json> <plan.json>
plan.json: {"setup": [cmd...], "verifiers": [{"name","cmd","receipt_path"?}]}   ({PY} = the sandbox venv python)
Key only via TENKI_API_KEY env; nothing secret is sent into the sandbox. Termination happens inside the client scope."""
import json, os, sys
from tenki import Client

repo, commit, session, outp, plan_path = sys.argv[1:6]
plan = json.load(open(plan_path))
key = os.environ["TENKI_API_KEY"]
res = {"schema": "TENKI_EXECUTION_RAW_RESULT_V1", "execution_locus": "TENKI_SANDBOX", "pre_tenki_commit": commit,
       "session_label": session, "sandbox_create": "NOT_EXECUTED", "tenki_session_id": None, "source_pin": "NOT_EXECUTED",
       "commands": [], "receipts": {}, "terminated": "NOT_EXECUTED"}


def tail(b, n=2500):
    return b.decode(errors="replace")[-n:].replace(key, "<redacted>")


def run(sb, name, cmd, cwd=None, timeout=900):
    r = sb.exec("bash", "-c", cmd, cwd=cwd, timeout=timeout)
    res["commands"].append({"name": name, "exit_code": r.exit_code, "timed_out": r.timed_out,
                            "stdout_tail": tail(r.stdout), "stderr_tail": tail(r.stderr, 800)})
    return r


def execute(sb):
    if run(sb, "git_clone", f"git clone -q {repo} repo").exit_code != 0:
        return
    run(sb, "git_checkout", f"git checkout -q {commit}", cwd="repo")
    head = run(sb, "git_rev_parse", "git rev-parse HEAD", cwd="repo").stdout_text.strip()
    res["observed_head"], res["source_pin"] = head, ("PASS" if head == commit else "FAIL")
    if res["source_pin"] != "PASS":
        return
    for i, cmd in enumerate(plan.get("setup", [])):
        run(sb, f"setup_{i}", cmd.replace("{PY}", ".venv/bin/python"), cwd="repo", timeout=1200)
    for v in plan["verifiers"]:
        run(sb, v["name"], v["cmd"].replace("{PY}", ".venv/bin/python"), cwd="repo")
        if v.get("receipt_path"):
            try:
                res["receipts"][v["name"]] = json.loads(sb.fs.read_text(v["receipt_path"]))
            except Exception as e:  # noqa: BLE001
                res["receipts"][v["name"]] = {"_error": type(e).__name__}


try:
    with Client(api_key=key) as c:
        sb = None
        try:
            sb = c.create(name=f"vithia-fcg-{session[-16:].lower()}", cpu_cores=2, memory_mb=4096, sticky=False,
                          max_duration=1800, metadata={"purpose": "vithia-fcg-doctor3-verification"})
            res["sandbox_create"], res["tenki_session_id"] = "PASS", sb.id
            execute(sb)
        finally:
            if sb is not None:
                try:
                    sb.close_if_open(); res["terminated"] = "PASS"
                except Exception as e:  # noqa: BLE001
                    res["terminated"], res["terminate_error"] = "FAIL", type(e).__name__
except Exception as e:  # noqa: BLE001
    res["error_class"], res["error"] = type(e).__name__, str(e).replace(key, "<redacted>")[:400]
finally:
    open(outp, "w").write(json.dumps(res, indent=1, sort_keys=True) + "\n")
print(json.dumps({k: res[k] for k in ("sandbox_create", "tenki_session_id", "source_pin", "terminated")}))
