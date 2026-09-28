# Local Claude Red-Team Loop

The intended trigger is a durable Ollarma event after a committed, pushed
HEAD, not every file save:

```json
{"event":"READY_FOR_REDTEAM","branch":"<branch>","head":"<sha>","prompt_version":"PER_SEAT_REDTEAM_V02","prompt_file":"live_demo/redteam/CLAUDE_REDTEAM_PROMPT.md","safe_to_test":true}
```

The watcher must invoke the discovered Claude-capable bridge with that exact
HEAD and persist a result receipt. A P0 result should produce
`REDTEAM_P0_FOUND`, then `CODEX_REPAIR_REQUESTED`, a new successor commit, and
`READY_FOR_RETEST`. Zero P0 findings produces `REDTEAM_CLEAR`.

Current discovery is intentionally conservative: the local Ollarma service and
unrelated overnight supervisors are present, but no project-matched
Claude-capable watcher/bridge or authenticated Claude target was evidenced.
The current state is therefore `CLAUDE_AUTOTRIGGER=BLOCKED_NOT_EVIDENCED`.
