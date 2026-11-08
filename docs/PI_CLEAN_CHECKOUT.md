# Clean Pi source checkout without losing the existing environment/data

## Sync the current Pi folder in place

Use this when you want the existing folder aligned to `training`, rather than creating another checkout. Stop the app with **Ctrl+C**, then run in the actual app folder (`~/sample-scanner` or `~/sample-scanner-demo`):

```bash
cd ~/sample-scanner
git fetch origin &&
git show origin/training:scripts/sync_pi.sh > /tmp/sample-scanner-sync.sh &&
bash /tmp/sample-scanner-sync.sh --cached &&
bash scripts/start_demo.sh
```

The helper first creates backup branches for current commits and any existing local `training` branch. It stashes tracked/untracked source changes, explicitly excluding uploads, `.venv*`, SQLite files and sidecars, `.env` files, model/cache folders, backups and benchmark results. It then switches/resets the local **training** branch to the fetched `origin/training` and sets its upstream. Obsolete untracked code is preserved in the stash rather than left mixed into the new layout. Do not automatically reapply the old stash; that would mix old code back into the update.

It stops if protected runtime files are Git-tracked or a normal merge/rebase is in progress. It validates the repository remote and does not run `git clean` or delete runtime data. This is a code synchronization operation, not a history-replaying `git rebase`. The code backup can be inspected with `git stash list` and `git branch --list 'backup/pi-*'`. Backup stashes/branches are local to that Pi, not automatically pushed. The procedure was tested in an isolated Git repository with staged edits, untracked conflicting code, photos, SQLite/WAL, environment and result files; it has not been executed through the user's SSH login.

## Alternative: keep the old source tree and create a new one

The screenshot with many `M`, `A` and `U` markers is consistent with individual `training` files being restored onto an older branch. That updates selected app files but does not switch branches or remove old/untracked root files. The organized layout is committed on `training`; runtime helpers intentionally remain next to `main.py`, while tests, tools, guides and legacy code have their own directories.

Use a separate clean checkout to avoid resetting or deleting that mixed working tree. These instructions assume the old folder is `/home/hacks/sample-scanner`, with an existing `.venv-ocr`, `uploads/` and `scanner.sqlite3`.

**1. Stop the old server with Ctrl+C.** Keep it stopped; run only one app against the shared data.

**2. With internet available, create a new source folder:**

```bash
cd ~
git clone --branch training --single-branch https://github.com/ahellmann201/YCP_Hacks_Fa_26.git sample-scanner-demo
```

Choose a new folder name if `sample-scanner-demo` already exists; do not replace an existing checkout blindly.

**3. Link the existing environment and data, without moving them:**

```bash
test -x "$HOME/sample-scanner/.venv-ocr/bin/python" &&
test -d "$HOME/sample-scanner/uploads" &&
test -f "$HOME/sample-scanner/scanner.sqlite3" &&
ln -s "$HOME/sample-scanner/.venv-ocr" "$HOME/sample-scanner-demo/.venv-ocr" &&
ln -s "$HOME/sample-scanner/uploads" "$HOME/sample-scanner-demo/uploads" &&
ln -s "$HOME/sample-scanner/scanner.sqlite3" "$HOME/sample-scanner-demo/scanner.sqlite3"
```

These links reuse the same Pi environment, session database, photos and cached RapidOCR models. Nothing from the original checkout is deleted or reset. This is same-machine reuse, not copying a Windows environment to the Pi. CSV-and-finish cleanup in the new app still deletes the selected session's shared photos as intended.

**4. Open `/home/hacks/sample-scanner-demo` in VS Code Remote SSH and start it:**

```bash
cd ~/sample-scanner-demo
git status --short
git branch --show-current
bash scripts/start_demo.sh
```

The branch should be `training` and source status should be clean. Resume the existing session when the page prompts. Substitute `~/sample-scanner-demo` for `~/sample-scanner` in the main README's commands. Keep the old folder because the environment/data links point to it.

For later updates, stop the server, run `git pull --ff-only` in this clean checkout, and restart. Do not force/reset if you have made new local code edits. This migration has not been executed remotely on the user's Pi; the Pi requires the user's SSH login.
