# Gum Doctor Sponsor Runner

Submission-critical helper for Vithia-Space. It keeps credentials local and
Git-ignored, reports only credential presence, verifies the current Git/replay
state, and gives Claude one bounded task file to execute.

## One-time setup

```bash
git fetch origin
git checkout tools/gum-doctor-sponsor-runner-v01
git pull --ff-only origin tools/gum-doctor-sponsor-runner-v01

python3 tools/gum_doctor_sponsor/configure_env.py
```

The credential file is written to:

```
.private/sponsor-proof/.env
```

The repository already ignores files named `.env`.

## Run the doctor

```bash
bash tools/gum_doctor_sponsor/run.sh
```

This never prints credential values. It writes a sanitized local status file:

```
.private/sponsor-proof/gum_doctor_status.json
```

## Claude

Give Claude exactly:

```
Read tools/gum_doctor_sponsor/CLAUDE_TASK.md and execute it from the current
repository. Start by running bash tools/gum_doctor_sponsor/run.sh. Do not print
credentials.
```

Claude is the sole repository writer for this cycle. Local Ollarma/Qwen/Liquid
and OpenJEV are workers/execution substrates only. Completed public-safe
receipts must be committed and pushed immediately.
