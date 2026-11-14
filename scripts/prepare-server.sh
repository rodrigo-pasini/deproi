#!/usr/bin/env bash
# Deproi — prepare a server for one environment (https://github.com/rodrigo-pasini/deproi)
#
# Run on the SERVER, as root. Idempotent: running it again only fixes what drifted.
#
#   sudo ./prepare-server.sh --name myapp-prod --checkout /srv/myapp-prod \
#        [--public-key "ssh-ed25519 AAAA… deproi:myapp-prod"] [--script deploy/deproi.py]
#   sudo ./prepare-server.sh --name myapp-prod --uninstall
#
# What it does (nothing else):
#   1. checks the prerequisites (python3 ≥ 3.10, docker compose v2, git, sudo…);
#   2. creates the system user `deproi` (no password, not in the docker group);
#   3. installs <checkout>/<script> as /usr/local/sbin/deproi-<name> (root, 0755);
#   4. creates /etc/deproi (root) and a starter /etc/deproi/<name>.json (0600) if missing;
#   5. writes /etc/sudoers.d/deproi-<name> (validated with visudo first);
#   6. with --public-key, writes the key's line in /home/deproi/.ssh/authorized_keys,
#      locked to `sudo -n /usr/local/sbin/deproi-<name>`.
#
# Standard tools only. Read it before running it: it is short on purpose.
set -euo pipefail

NAME=""
CHECKOUT=""
PUBLIC_KEY=""
SCRIPT_PATH="deploy/deproi.py"
UNINSTALL=0
DEPLOY_USER="deproi"
INSTALL_DIR="/usr/local/sbin"
CONFIG_DIR="/etc/deproi"
STATE_DIR="/var/lib/deproi"

ok() { printf '  ✅ %s\n' "$*"; }
warn() { printf '  ⚠️  %s\n' "$*"; }
fail() {
  printf '  ❌ %s\n' "$*" >&2
  exit 1
}
step() { printf '\n▶ %s\n' "$*"; }

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="${2:-}"; shift 2 ;;
    --checkout) CHECKOUT="${2:-}"; shift 2 ;;
    --public-key) PUBLIC_KEY="${2:-}"; shift 2 ;;
    --script) SCRIPT_PATH="${2:-}"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h | --help) usage 0 ;;
    *) printf 'Unknown option: %s\n\n' "$1" >&2; usage 2 ;;
  esac
done

[ "$(id -u)" -eq 0 ] || fail "run as root (sudo $0 …)"
[[ "$NAME" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || fail "--name must be lowercase letters, digits and -, e.g. myapp-prod"

COMMAND="$INSTALL_DIR/deproi-$NAME"
SUDOERS="/etc/sudoers.d/deproi-$NAME"
CONFIG="$CONFIG_DIR/$NAME.json"
HOME_DIR="/home/$DEPLOY_USER"
KEYS="$HOME_DIR/.ssh/authorized_keys"

remove_key_line() {
  [ -f "$KEYS" ] || return 0
  local temporary
  temporary=$(mktemp)
  grep -v " deproi:$NAME\$" "$KEYS" > "$temporary" || true
  install -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0600 "$temporary" "$KEYS"
  rm -f "$temporary"
}

if [ "$UNINSTALL" -eq 1 ]; then
  step "Removing Deproi for $NAME"
  rm -f "$SUDOERS" && ok "removed $SUDOERS"
  remove_key_line && ok "removed the key line deproi:$NAME"
  rm -f "$COMMAND" && ok "removed $COMMAND"
  warn "kept $CONFIG, its credential files and $STATE_DIR/$NAME — remove them by hand if you want"
  warn "kept the user $DEPLOY_USER (other environments may use it): userdel -r $DEPLOY_USER"
  exit 0
fi

[ -n "$CHECKOUT" ] || fail "--checkout is required (the git checkout of the project on this server)"
[ -d "$CHECKOUT/.git" ] || fail "$CHECKOUT is not a git checkout"
OWNER=$(stat -c %U "$CHECKOUT")
[ "$OWNER" != "root" ] || fail "$CHECKOUT is owned by root: give it to the user that runs git (chown -R <user> $CHECKOUT)"
case "$SCRIPT_PATH" in /* | ..*) fail "--script must be a path inside the checkout" ;; esac
SOURCE="$CHECKOUT/$SCRIPT_PATH"
[ -f "$SOURCE" ] || fail "$SOURCE does not exist: commit deproi.py to the project first"

step "Prerequisites"
[ -x /usr/bin/python3 ] || fail "/usr/bin/python3 is missing"
/usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' ||
  fail "/usr/bin/python3 is $(/usr/bin/python3 -V 2>&1); Deproi needs 3.10 or newer"
ok "$(/usr/bin/python3 -V 2>&1)"
command -v docker > /dev/null || fail "docker is missing"
docker compose version > /dev/null 2>&1 || fail "docker compose v2 is missing (the 'docker compose' plugin)"
ok "$(docker compose version | head -n 1)"
for tool in git runuser logger visudo sudo flock nice ionice; do
  command -v "$tool" > /dev/null || fail "$tool is missing"
done
ok "git, runuser, logger, sudo, visudo, flock, nice, ionice"
if sshd -T 2> /dev/null | grep -qi '^passwordauthentication yes'; then
  warn "SSH accepts passwords. Recommended: PasswordAuthentication no (keys only)."
fi
if ! command -v fail2ban-client > /dev/null; then
  warn "fail2ban is not installed (recommended on a server with SSH open to the internet)"
fi

step "User $DEPLOY_USER"
if id "$DEPLOY_USER" > /dev/null 2>&1; then
  ok "exists"
else
  useradd --system --create-home --home-dir "$HOME_DIR" --shell /bin/sh "$DEPLOY_USER"
  ok "created (system user, no password)"
fi
passwd -l "$DEPLOY_USER" > /dev/null 2>&1 || true
# Checked by capability, not by group name: any group that can write the socket is root without sudo.
SOCKET=/var/run/docker.sock
if [ -S "$SOCKET" ] && runuser -u "$DEPLOY_USER" -- test -w "$SOCKET"; then
  fail "$DEPLOY_USER can write $SOCKET — that is root without sudo. Remove it from the socket's group ($(stat -c %G "$SOCKET"))"
fi
ok "cannot use Docker directly"

step "Deploy command $COMMAND"
/usr/bin/python3 -I -B -c '
import importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader("deproi_check", sys.argv[1])
module = importlib.util.module_from_spec(importlib.util.spec_from_loader("deproi_check", loader))
sys.modules["deproi_check"] = module
loader.exec_module(module)
assert module.SELF_UPDATING is True and callable(module.main)
print(module.DEPROI_VERSION)
' "$SOURCE" > /dev/null || fail "$SOURCE does not load as Deproi"
install -o root -g root -m 0755 "$SOURCE" "$COMMAND"
ok "installed $(sed -n 's/^DEPROI_VERSION = "\(.*\)"$/\1/p' "$COMMAND") (root:root 0755)"

step "Configuration $CONFIG"
install -d -o root -g root -m 0755 "$CONFIG_DIR"
install -d -o root -g root -m 0700 "$STATE_DIR"
if [ -f "$CONFIG" ]; then
  ok "exists (not touched)"
else
  temporary=$(mktemp)
  cat > "$temporary" << EOF
{
  "\$schema": "https://raw.githubusercontent.com/rodrigo-pasini/deproi/main/deproi.schema.json",
  "name": "$NAME",
  "language": "en",
  "checkout": {
    "path": "$CHECKOUT",
    "owner": "$OWNER",
    "branch": "main"
  },
  "compose": {
    "project": "$NAME",
    "web_service": "web",
    "image": "$NAME"
  }
}
EOF
  install -o root -g root -m 0600 "$temporary" "$CONFIG"
  rm -f "$temporary"
  warn "created a starter config — EDIT IT before the first deploy: $CONFIG"
fi
chown root:root "$CONFIG"
chmod go-w "$CONFIG"

step "sudo rule $SUDOERS"
temporary=$(mktemp)
cat > "$temporary" << EOF
# /etc/sudoers.d/deproi-$NAME — written by Deproi's prepare-server.sh.
# The $DEPLOY_USER user may run exactly one command as root, without arguments
# (the trailing "" forbids any). Defaults only keeps two variables for the syslog.
Defaults!$COMMAND env_keep += "SSH_ORIGINAL_COMMAND SSH_CLIENT"
$DEPLOY_USER ALL=(root) NOPASSWD: $COMMAND ""
EOF
visudo -cf "$temporary" > /dev/null || {
  rm -f "$temporary"
  fail "the sudo rule did not validate; nothing was installed"
}
install -o root -g root -m 0440 "$temporary" "$SUDOERS"
rm -f "$temporary"
ok "installed and validated"

step "SSH key"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0700 "$HOME_DIR/.ssh"
[ -f "$KEYS" ] || install -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0600 /dev/null "$KEYS"
if [ -n "$PUBLIC_KEY" ]; then
  read -r key_type key_body _ <<< "$PUBLIC_KEY"
  [ "$key_type" = "ssh-ed25519" ] || fail "--public-key must be an ssh-ed25519 public key"
  [[ "$key_body" =~ ^[A-Za-z0-9+/=]+$ ]] || fail "--public-key does not look like a public key"
  remove_key_line
  printf 'restrict,command="sudo -n %s" ssh-ed25519 %s deproi:%s\n' "$COMMAND" "$key_body" "$NAME" >> "$KEYS"
  chown "$DEPLOY_USER:$DEPLOY_USER" "$KEYS"
  chmod 0600 "$KEYS"
  ok "key line deproi:$NAME written (locked to sudo -n $COMMAND)"
elif grep -q " deproi:$NAME\$" "$KEYS"; then
  ok "key line deproi:$NAME already present"
else
  warn "no key yet: run create-deploy-key.sh on your machine, then this script again with --public-key"
fi

step "Next steps"
cat << EOF
  1. Edit $CONFIG (schema and examples: https://github.com/rodrigo-pasini/deproi/blob/main/docs/configuration.md)
  2. Put secrets in root-only files (0600) under $CONFIG_DIR — never in the repository.
  3. Check everything:     sudo ./doctor.sh --name $NAME
  4. First deploy by hand: sudo $COMMAND
EOF
