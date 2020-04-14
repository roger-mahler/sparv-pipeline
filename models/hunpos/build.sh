#!/usr/bin/env bash

# Build hunpos.saldo.suc-tags.morphtable
$python -m sparv.modules.hunpos.hunpos_morphtable --out "hunpos.saldo.suc-tags.morphtable" --saldo_model "saldo.pickle" --suc "suc3.morphtable.words" --morphtable_base "hunpos.suc.morphtable" --morphtable_patterns "hunpos.suc.patterns"

# Build hunpos.dalinm-swedberg.saldo.suc-tags.morphtable
$python -m sparv.modules.hunpos.hunpos_morphtable_hist --out "hunpos.dalinm-swedberg.saldo.suc-tags.morphtable" --files "hist_hunposfiles/swedberg-gender.hunpos hist_hunposfiles/dalinm.hunpos" --saldosuc_morphtable "hunpos.saldo.suc-tags.morphtable"
