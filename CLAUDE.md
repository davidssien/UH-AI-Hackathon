# CLAUDE.md

Follow FINAL_PROMPT.md.

- Env: `source .venv/bin/activate` (adds torch/lib to LD_LIBRARY_PATH for LightGBM, loads .env).
- Background jobs: `./run.sh <id> <cmd...>` → `logs/<id>.log`.
- Read logs with `tail -n 20` only.
