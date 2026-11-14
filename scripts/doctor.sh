#!/usr/bin/env bash
# Deproi — check one environment on this server (https://github.com/rodrigo-pasini/deproi)
#
# Run on the SERVER, as root. Read-only: it changes nothing and never deploys.
#
#   sudo ./doctor.sh --name myapp-prod
#
# Exit 0 when every check passes, 1 otherwise.
set -uo pipefail

NAME=""
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo $0 --name …)" >&2; exit 2; }
[[ "$NAME" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || { echo "--name is required, e.g. myapp-prod" >&2; exit 2; }

COMMAND="/usr/local/sbin/deproi-$NAME"
CONFIG="/etc/deproi/$NAME.json"
SUDOERS="/etc/sudoers.d/deproi-$NAME"
KEYS="/home/deproi/.ssh/authorized_keys"
FAILED=0

pass() { printf '  ✅ %s\n' "$*"; }
# verdict "<passing message>" "<failing message>" command… — one check, one line.
verdict() {
  local good="$1" bad="$2"
  shift 2
  if "$@"; then pass "$good"; else problem "$bad"; fi
}
problem() {
  printf '  ❌ %s\n' "$*"
  FAILED=1
}
note() { printf '  ⚠️  %s\n' "$*"; }
section() { printf '\n▶ %s\n' "$*"; }

owned_by_root() { [ "$(stat -c %u "$1")" = "0" ]; }
mode_of() { stat -c %a "$1"; }

section "Deploy command"
if [ -f "$COMMAND" ]; then
  if owned_by_root "$COMMAND" && [ "$(mode_of "$COMMAND")" = "755" ]; then
    pass "$COMMAND (root, 0755), version $(sed -n 's/^DEPROI_VERSION = "\(.*\)"$/\1/p' "$COMMAND")"
  else
    problem "$COMMAND must be root:root 0755"
  fi
else
  problem "$COMMAND is missing — run prepare-server.sh"
fi

section "Configuration"
if [ -f "$CONFIG" ]; then
  if owned_by_root "$CONFIG" && [ $((8#$(mode_of "$CONFIG") & 8#022)) -eq 0 ]; then
    pass "$CONFIG is owned by root and not writable by others"
  else
    problem "$CONFIG must be owned by root and not writable by group or others"
  fi
  if [ -f "$COMMAND" ]; then
    if check=$(/usr/bin/python3 -I -B -c '
import importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader("deproi_doctor", sys.argv[1])
module = importlib.util.module_from_spec(importlib.util.spec_from_loader("deproi_doctor", loader))
sys.modules["deproi_doctor"] = module
loader.exec_module(module)
try:
    cfg = module.load_config(sys.argv[2])
except module.ConfigError as problem:
    print("ERROR", problem)
    sys.exit(1)
print(cfg.checkout_path, cfg.checkout_owner, cfg.branch, cfg.remote, cfg.secrets_file or "-", cfg.project)
' "$COMMAND" "$NAME" 2>&1); then
      read -r checkout owner branch remote secrets project <<< "$check"
      pass "valid (project $project, branch $branch)"
    else
      problem "invalid: ${check#ERROR }"
      checkout=""
    fi
  fi
else
  problem "$CONFIG is missing"
  checkout=""
fi

if [ -n "${checkout:-}" ]; then
  section "Checkout $checkout"
  if [ -d "$checkout/.git" ]; then
    pass "git checkout"
    current=$(runuser -u "$owner" -- git -C "$checkout" rev-parse --abbrev-ref HEAD 2>&1)
    verdict "on branch $branch" "on branch $current, expected $branch" [ "$current" = "$branch" ]
    dirty=$(runuser -u "$owner" -- git -C "$checkout" status --porcelain --untracked-files=no 2>&1)
    verdict "no local changes to tracked files" "local changes: $(echo "$dirty" | head -n 3 | tr '\n' ' ')" [ -z "$dirty" ]
    if runuser -u "$owner" -- env HOME="$(getent passwd "$owner" | cut -d: -f6)" git -C "$checkout" ls-remote --exit-code "$remote" "$branch" > /dev/null 2>&1; then
      pass "$owner can fetch $branch from $remote"
    else
      problem "$owner cannot fetch $branch from $remote (deploy key or credentials of the checkout?)"
    fi
  else
    problem "$checkout is not a git checkout"
  fi
  if [ "$secrets" != "-" ]; then
    case "$secrets" in /*) path="$secrets" ;; *) path="$checkout/$secrets" ;; esac
    if [ -f "$path" ]; then
      if owned_by_root "$path" && [ $((8#$(mode_of "$path") & 8#077)) -eq 0 ]; then
        pass "secrets file $path is root-only"
      else
        note "secrets file $path should be root:root 0600"
      fi
    else
      problem "secrets file $path is missing"
    fi
  fi
fi

section "sudo and SSH"
if [ -f "$SUDOERS" ]; then
  verdict "$SUDOERS validates" "$SUDOERS does not validate" visudo -qcf "$SUDOERS"
  verdict "one command, no arguments" "$SUDOERS does not have the exact rule (rerun prepare-server.sh)" \
    grep -q "^deproi ALL=(root) NOPASSWD: $COMMAND \"\"\$" "$SUDOERS"
else
  problem "$SUDOERS is missing"
fi
if id deproi > /dev/null 2>&1; then
  if [ -S /var/run/docker.sock ] && runuser -u deproi -- test -w /var/run/docker.sock; then
    problem "user deproi can write /var/run/docker.sock (group $(stat -c %G /var/run/docker.sock)) — that is root without sudo"
  else
    pass "user deproi exists and cannot use Docker directly"
  fi
else
  problem "user deproi is missing"
fi
if [ -f "$KEYS" ] && grep -q " deproi:$NAME\$" "$KEYS"; then
  line=$(grep " deproi:$NAME\$" "$KEYS")
  if [[ "$line" == "restrict,command=\"sudo -n $COMMAND\" ssh-ed25519 "* ]]; then
    pass "key deproi:$NAME is locked to its command"
  else
    problem "key deproi:$NAME is not locked (restrict,command=…)"
  fi
else
  note "no key for $NAME in $KEYS yet"
fi

section "Docker"
if docker compose version > /dev/null 2>&1; then
  pass "$(docker compose version | head -n 1)"
else
  problem "docker compose v2 is missing"
fi
free=$(df -BG --output=avail /var/lib/docker 2> /dev/null | tail -n 1 | tr -dc '0-9')
if [ -n "$free" ]; then pass "${free} GB free for Docker"; else note "could not read the free space"; fi

section "Last deploys"
if command -v journalctl > /dev/null; then
  journalctl -t "deproi-$NAME" --no-pager -o cat 2> /dev/null | grep '^result: ' | tail -n 5 | sed 's/^/  /' ||
    true
fi

echo
if [ "$FAILED" -eq 0 ]; then
  echo "All checks passed."
else
  echo "Some checks failed — see ❌ above."
fi
exit "$FAILED"
