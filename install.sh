#!/usr/bin/env bash
# goalgoal — one-line installer
#
#   curl -fsSL https://raw.githubusercontent.com/NewTurn2017/goalgoal/main/install.sh | bash
#
# Installs the goalgoal skill into every agent skills directory found on this
# machine: Claude Code (~/.claude/skills) and Codex (~/.codex/skills), plus any
# path in $AGENT_SKILLS_DIR. Re-running updates an existing install (git pull).

set -euo pipefail

REPO="${GOALGOAL_REPO:-https://github.com/NewTurn2017/goalgoal.git}"
NAME="goalgoal"

say()  { printf '\033[1;36m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }

command -v git >/dev/null 2>&1 || { warn "git is required but not found."; exit 1; }

# Collect target skills directories.
targets=()
[ -d "$HOME/.claude" ] && targets+=("$HOME/.claude/skills")
[ -d "$HOME/.codex" ]  && targets+=("$HOME/.codex/skills")
[ -n "${AGENT_SKILLS_DIR:-}" ] && targets+=("$AGENT_SKILLS_DIR")

# Default to Claude Code location if nothing detected.
if [ ${#targets[@]} -eq 0 ]; then
  warn "No ~/.claude or ~/.codex found — defaulting to ~/.claude/skills"
  targets+=("$HOME/.claude/skills")
fi

installed=0
for base in "${targets[@]}"; do
  dest="$base/$NAME"
  mkdir -p "$base"
  if [ -d "$dest/.git" ]; then
    say "Updating $dest"
    git -C "$dest" pull --ff-only --quiet && ok "Updated $dest"
  elif [ -e "$dest" ]; then
    warn "Skipping $dest (exists but not a git checkout — move it aside to reinstall)"
    continue
  else
    say "Cloning into $dest"
    git clone --depth 1 --quiet "$REPO" "$dest" && ok "Installed $dest"
  fi
  installed=$((installed + 1))
done

echo
ok "goalgoal installed to $installed location(s)."
cat <<'USAGE'

Next:
  Open Claude Code (or Codex) and say:

      목표 잡아줘 — <your one-line idea>

  goalgoal will interview you, write goal.json, and hand off with:

      /goal @goal.json

USAGE
