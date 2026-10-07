# __dev/usage — what get_codeblock's call logs say, and a replay to guard refactors

Every project's `__HQ/tools/_logs/get_codeblock.log.jsonl` records each call's argv (not the
output). Written 2026-10-07 for hermes-filetools `Plan30`; paths inside the scripts are the
owner's machine — edit the lists at the top.

- `stat_arrays.py` — per log: calls by mode (query / outline / ladder / name), single vs `--line`
  array, array sizes. Found: arrays are 20–42% of `--query`.
- `stat_flags.py` — all logs together: flag counts, `--level`/`--ancestor-level` values, top flag
  combinations. Found: `--level` never as an array; `--force` on ~1/3 of queries.
- `stat_after_ladder.py` — what follows a ladder call (`--line` alone) on the same file, and the
  first call on a new file. Found: a ladder is followed by `--query` only 3% of the time — it is
  reconnaissance, not a step before reading.
- `replay_logged_calls.py` — replays every distinct logged call on two copies of the tool (OLD =
  `git archive HEAD`, NEW = the working tree, each with `LOG_ENABLED_TOOLS = []` appended to its
  `CONFIG__TOOLS.py` so the replay does not write into the real logs) and compares stdout, exit
  code and the last stderr line. `views.py` refactor: 1482 calls, 0 differ.

```
git archive HEAD get_codeblock get_codeblock.py CONFIG__TOOLS.py termstyle.py | tar -x -C <ramdisk>/gcb_old
cp -r get_codeblock get_codeblock.py CONFIG__TOOLS.py termstyle.py <ramdisk>/gcb_new/
printf '\nLOG_ENABLED_TOOLS = []\n' >> <ramdisk>/gcb_old/CONFIG__TOOLS.py   # same for gcb_new
python __dev/usage/replay_logged_calls.py [last-N]
```
