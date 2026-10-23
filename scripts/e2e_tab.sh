#!/bin/bash
# demo end-to-end run of all tabular models
cd ~/hack && source .venv/bin/activate
r() { id=$1; shift; timeout 15m "$@" --id $id --change demo > logs/$id.log 2>&1; grep -hE "RESULT|BEST" logs/$id.log || { echo "FAIL $id"; tail -n 4 logs/$id.log; }; }
# r d_tabpfn python src/train_tabpfn.py --max-train 5000
r d_tabicl python src/train_tabicl.py
r d_realmlp python src/train_pytabkit.py --model realmlp
r d_tabm python src/train_pytabkit.py --model tabm
# r d_lgbm_log python src/train_lgbm.py --tt log1p
# r d_lgbm_fe python src/train_lgbm.py --fe base+count+combos --te
# r d_tune python src/tune.py --model lgbm --timeout 60
r d_ag python src/train_autogluon.py --presets best_quality --time-limit 240
