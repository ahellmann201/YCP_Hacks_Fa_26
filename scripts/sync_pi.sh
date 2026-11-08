#!/usr/bin/env bash
# Sync code to origin/training while keeping runtime state out of the stash.
set -euo pipefail
cached=false
if [[ "${1:-}" == --cached ]]; then cached=true; elif [[ $# -gt 0 ]]; then
    echo "Usage: bash sync_pi.sh [--cached]"; exit 1
fi
root="$(git rev-parse --show-toplevel)"
cd "$root"
origin="$(git remote get-url origin)"
case "$origin" in
    https://github.com/ahellmann201/YCP_Hacks_Fa_26.git|git@github.com:ahellmann201/YCP_Hacks_Fa_26.git) ;;
    *) echo "Run this in the YCP_Hacks_Fa_26 checkout with its expected origin remote."; exit 1 ;;
esac
echo "Stop the scanner server before running this sync."
if [[ "$cached" == false ]]; then
    git fetch origin refs/heads/training:refs/remotes/origin/training
fi
git rev-parse --verify origin/training >/dev/null
protected=(uploads '.venv*' 'scanner.sqlite3*' .env '.env.*' models test-crops .scanner-backups)
if [[ -n "$(git ls-files -- "${protected[@]}")" ]] ||
   [[ -n "$(git ls-tree -r --name-only origin/training -- "${protected[@]}")" ]]; then
    echo "Runtime data/environment files are tracked by Git. Sync stopped to protect them."
    exit 1
fi
if [[ -f .git/MERGE_HEAD ]] || [[ -d .git/rebase-merge ]] || [[ -d .git/rebase-apply ]]; then
    echo "A merge/rebase is in progress. Resolve or abort it before syncing."; exit 1
fi
stamp="$(date +%Y%m%d-%H%M%S)-$$"
git branch "backup/pi-before-sync-$stamp" HEAD
if git show-ref --verify --quiet refs/heads/training; then
    git branch "backup/pi-training-$stamp" training
fi
before="$(git rev-parse --verify refs/stash 2>/dev/null || true)"
code_paths=()
declare -A seen=()
while IFS= read -r -d '' path; do
    case "$path" in
        uploads|uploads/*|.venv*|scanner.sqlite3*|.env|.env.*|models|models/*|test-crops|test-crops/*|.scanner-backups|.scanner-backups/*|benchmark-results.json|thread-benchmark-results.json) continue ;;
    esac
    if [[ -z "${seen[$path]+present}" ]]; then
        code_paths+=("$path"); seen[$path]=1
    fi
done < <(git ls-files --cached --others --exclude-standard -z; git diff --name-only HEAD -z)
if [[ ${#code_paths[@]} -gt 0 ]]; then
    git stash push --include-untracked -m "Pi code before training sync $stamp" -- "${code_paths[@]}"
fi
after="$(git rev-parse --verify refs/stash 2>/dev/null || true)"
if [[ "$after" != "$before" ]]; then
    echo "Local code changes backed up in Git stash: $after"
fi
git switch -C training origin/training
git branch --set-upstream-to=origin/training training
echo "Code synced to origin/training. Runtime data and environment were excluded from the stash."
echo "Saved code is in backup/pi-* branches and, when changes existed, git stash list."
echo "Review git status; do not automatically apply the old stash onto the updated code."
git status --short
echo "Start: bash scripts/start_demo.sh"
