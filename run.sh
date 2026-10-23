#!/bin/bash
# Background runner: ./run.sh <id> <command...>   -> logs/<id>.log, killed after $TIMEOUT (default 15m)
# e.g. ./run.sh lgbm1 python src/train_lgbm.py --id lgbm1
#      TIMEOUT=65m ./run.sh ag1 python src/train_autogluon.py --id ag1 --time-limit 3600
cd "$(dirname "$0")"
source .venv/bin/activate
id=$1; shift
nohup timeout "${TIMEOUT:-15m}" "$@" > "logs/$id.log" 2>&1 &
echo "started $id pid $! log logs/$id.log"
