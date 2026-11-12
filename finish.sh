#!/usr/bin/env bash
# =============================================================================
# finish.sh — single-command post-change routine.
#
# Run this at the end of ANY template change instead of remembering 4 steps:
#   ./finish.sh "<commit message>"
#
# Flags:
#   --local          Review mode: sync + commit only. Skips the stamp, push,
#                    and tag. Use while iterating; finish the batch with a
#                    full run (no flag) to release.
#   --minor          Bump the MINOR version segment (v1.x.0) instead of the
#                    patch segment. Use for multi-feature releases.
#   --prompt "text"  Append the user prompt to chat_history/opencode_prompts.txt
#                    BEFORE anything else runs (AGENTS.md rule 3), so the log
#                    lands in the same commit.
#
#   It executes, in order:
#   0. ./verify — local quality gate (compactor CSS + template invariants
#                 + builder + layout; skipped silently when tests/ is absent).
#                 This already builds and validates the release apkg.
#   1. version stamp  — compute the next release tag and rewrite the CSS
#                        header Version: line (full runs only; the stamp is
#                        what Anki receives in step 2, so it never lags)
#   2. sync_to_anki.py — push templates+CSS into Anki via Anki-Connect
#                        (also snapshots live Anki state into backups/)
#   3. git commit     — stage everything (incl. chat_history log) & commit
#   4. push main + tag — push the commit to origin/main, then push the tag.
#                        The tag push triggers release.yml: CI runs
#                        ./verify, builds the apkg from the tagged commit,
#                        and publishes the GitHub release (ADR 007 — the
#                        desktop never builds or uploads the release asset).
#
#   Publishing is CI-owned: this script never builds the artifact itself,
#   never creates a GitHub release, and never uploads the apkg. To build
#   the artifact locally (e.g. the one-time scratch-profile import check),
#   run `python3 build_sample_apkg.py` on demand.
#
# Any failure stops the chain with a clear message (set -e). Requires: Anki
# running with Anki-Connect. (gh is only used by release.yml on the runner.)
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"

# ---------- flag parsing ----------
LOCAL=0
BUMP_KIND=patch
PROMPT_TEXT=""
COMMIT_MSG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --local)  LOCAL=1 ;;
    --minor)  BUMP_KIND=minor ;;
    --prompt) shift; PROMPT_TEXT="${1:?--prompt requires a text argument}" ;;
    -h|--help)
      sed -n '2,31p' "$0"; exit 0 ;;
    *)
      if [ -z "$COMMIT_MSG" ]; then
        COMMIT_MSG="$1"
      else
        echo "ERROR: unexpected extra argument: $1 (commit message already set)" >&2
        exit 1
      fi ;;
  esac
  shift
done

[ -n "$COMMIT_MSG" ] || { echo 'Usage: ./finish.sh "<commit message>" [--local] [--minor] [--prompt "text"]' >&2; exit 1; }

# ---------- optional prompt archiving (before anything else) ----------
if [ -n "$PROMPT_TEXT" ]; then
  if printf '%s' "$PROMPT_TEXT" | grep -Ei -q 'api[_-]?key|token|passwd|password|secret|BEGIN .*PRIVATE KEY'; then
    echo "Refusing: --prompt text looks like it contains a secret; archive it manually after redacting." >&2
    exit 1
  fi
  printf '\n---\n\n%s\n' "$PROMPT_TEXT" >> chat_history/opencode_prompts.txt
  echo "    (prompt archived to chat_history/opencode_prompts.txt)"
fi

# ---------- step 0: regression tests (delegates to ./verify, the local gate) ----------
if [ -d tests ]; then
  echo "==> [0/4] Running regression tests (./verify)"
  ./verify
fi

# ---------- step 1: version stamp (BEFORE the sync so Anki gets the new tag) ----------
# Local runs skip it: no release is published, so the stamp stays at the
# last released version and the working tree is not polluted.
NEW_TAG=""
if [ "$LOCAL" -eq 0 ]; then
  echo "==> [1/4] Stamping version"
  git fetch origin "refs/tags/*:refs/tags/*" --quiet
  # Auto-bump version from the latest existing tag (v<major>.<minor>.<patch>)
  LATEST_TAG="$(git tag --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)"
  if [ -z "$LATEST_TAG" ]; then
    NEW_TAG="v1.0.1"
  else
    NEW_TAG="$(python3 - "$LATEST_TAG" "$BUMP_KIND" <<'PY'
import sys
major, minor, patch = sys.argv[1][1:].split(".")
if sys.argv[2] == "minor":
    print(f"v{major}.{int(minor) + 1}.0")
else:
    print(f"v{major}.{minor}.{int(patch) + 1}")
PY
)"
  fi
  # Rewrite the Version: line in the CSS header comment. The stamp is what
  # step 2 pushes to Anki and what step 3 commits — tag, tree and the live
  # template can never disagree.
  python3 - "$NEW_TAG" <<'PY'
import re, sys
tag = sys.argv[1]
path = "Card 1 - Style.css"
css = open(path, encoding="utf-8").read()
new, n = re.subn(
    r"( \* Version: )v[0-9]+\.[0-9]+\.[0-9]+[^\n]*",
    rf"\g<1>{tag} — auto-bumped by finish.sh; matches the GitHub release tag",
    css, count=1)
if n and new != css:
    open(path, "w", encoding="utf-8").write(new)
    print(f"    (stamped {tag} into Card 1 - Style.css header)")
PY
fi

echo "==> [2/4] Syncing templates to Anki (Anki-Connect)"
python3 sync_to_anki.py

echo "==> [3/4] Committing changes"
git add -A
CHANGED=0
if git diff --cached --quiet; then
  echo "    (nothing to commit)"
else
  git commit -m "$COMMIT_MSG"
  CHANGED=1
fi

if [ "$LOCAL" -eq 1 ]; then
  echo ""
  echo "Local run complete (synced, committed)."
  exit 0
fi

if [ "$CHANGED" -eq 0 ]; then
  echo "    No changes detected. Nothing to push or release."
  exit 0
fi

echo "==> [4/4] Pushing main, then tag $NEW_TAG (CI builds and publishes the release)"
git push origin main
git tag "$NEW_TAG"
git push origin "$NEW_TAG"

echo ""
echo "All done: synced, committed, pushed; release.yml is building $NEW_TAG."
echo "Watch: gh run watch (or the Actions tab). The release appears when the run completes."
