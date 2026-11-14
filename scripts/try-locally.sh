#!/usr/bin/env bash
# Deproi — rehearse a project's deploy on a disposable local "server" (https://github.com/rodrigo-pasini/deproi)
#
# Run on YOUR MACHINE, from a clone of Deproi, with Docker. Touches no real server.
#
#   scripts/try-locally.sh --project ../myapp --config myapp-prod.json \
#       [--ref my-branch] [--secrets myapp-prod.secrets.env]
#
# A container plays the server (Ubuntu 22.04: sshd, sudo, git, Python 3.10, Docker
# CLI on your Docker daemon). The script:
#   1. publishes the project's <ref> (default: HEAD) as the branch the config deploys;
#   2. runs prepare-server.sh and installs the config (checkout path and owner are
#      rewritten to the container's; everything else is used as is) and the secrets;
#   3. runs doctor.sh, then deploys over SSH with a locked key, exactly like GitHub does;
#   4. commits an empty change and deploys again (a second deploy, with a previous version).
# It expects SUCCESS (or SUCCESS_PROTECTED_DEFERRED) both times, prints each deploy's
# log on failure, and removes everything it created at the end.
#
# Your containers run on your Docker: ports your compose file publishes must be free.
# Single-quoted commands run inside the server container: they expand there, on purpose.
# shellcheck disable=SC2016
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
PROJECT=""
CONFIG=""
REF="HEAD"
SECRETS=""
PORT="${DEPROI_TRY_PORT:-2223}"
SERVER="deproi-try-server"

while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="${2:-}"; shift 2 ;;
    --config) CONFIG="${2:-}"; shift 2 ;;
    --ref) REF="${2:-}"; shift 2 ;;
    --secrets) SECRETS="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

fail() {
  printf '   ❌ %s\n' "$*" >&2
  exit 1
}
[ -d "$PROJECT/.git" ] || fail "--project must be a git repository"
[ -f "$CONFIG" ] || fail "--config must be the server config (JSON) to rehearse"
[ -z "$SECRETS" ] || [ -f "$SECRETS" ] || fail "--secrets file not found"
command -v docker > /dev/null || fail "Docker is required"

read_config() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print($1)" "$CONFIG"; }
NAME=$(read_config 'd["name"]')
BRANCH=$(read_config 'd["checkout"]["branch"]')
COMPOSE_PROJECT=$(read_config 'd["compose"]["project"]')
IMAGE=$(read_config 'd["compose"]["image"]')
SECRETS_PATH=$(read_config 'd["compose"].get("secrets_file") or ""')
SCRIPT_PATH=$(read_config 'd.get("script_path") or "deploy/deproi.py"')
CHECKOUT="/srv/$NAME"

WORK=$(mktemp -d)
cleanup() {
  set +e
  docker rm -f "$SERVER" > /dev/null 2>&1
  docker ps -aq --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" | xargs -r docker rm -f > /dev/null
  docker network ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" | xargs -r docker network rm > /dev/null 2>&1
  docker volume ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" | xargs -r docker volume rm > /dev/null 2>&1
  docker images -q "$IMAGE" | sort -u | xargs -r docker rmi -f > /dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT

step() { printf '\n\033[1m━━ %s\033[0m\n' "$*"; }
pass() { printf '   ✅ %s\n' "$*"; }
on_server() { docker exec "$SERVER" bash -c "$1"; }

deploy() {
  ssh -i "$WORK/key" -p "$PORT" -o IdentitiesOnly=yes -o UserKnownHostsFile="$WORK/known_hosts" \
    -o StrictHostKeyChecking=yes -o BatchMode=yes deproi@127.0.0.1 > "$WORK/out" 2>&1 || true
  if grep -qE '^result: SUCCESS(_PROTECTED_DEFERRED)? ' "$WORK/out"; then
    pass "$(grep '^result: ' "$WORK/out")"
  else
    sed 's/^/      │ /' "$WORK/out" >&2
    fail "the deploy did not succeed (log above)"
  fi
}

step "Server container"
docker build -q -t deproi-e2e-server "$ROOT/tests/e2e" > /dev/null
docker run -d --name "$SERVER" -p "127.0.0.1:$PORT:22" -v /var/run/docker.sock:/var/run/docker.sock deproi-e2e-server > /dev/null
on_server 'gid=$(stat -c %g /var/run/docker.sock); getent group "$gid" > /dev/null || groupadd -g "$gid" docker-host'
on_server "useradd -m -s /bin/bash app"
pass "$(on_server 'python3 -V') · $(on_server 'docker compose version --short')"

step "Project ($REF → branch $BRANCH)"
mkdir "$WORK/project"
git -C "$PROJECT" archive "$REF" | tar -x -C "$WORK/project"
[ -f "$WORK/project/$SCRIPT_PATH" ] || fail "$SCRIPT_PATH is not committed in $REF"
docker cp "$WORK/project/." "$SERVER:/home/app/project"
on_server "chown -R app:app /home/app/project && git init -q --bare -b $BRANCH /srv/origin.git && chown -R app /srv/origin.git"
docker exec -u app -w /home/app/project "$SERVER" bash -c "git init -q -b $BRANCH && git config user.email try@example.com \
  && git config user.name try && git remote add origin /srv/origin.git && git add -A && git commit -qm rehearsal \
  && git push -q origin $BRANCH"
on_server "install -d -o app -g app $CHECKOUT && runuser -u app -- git clone -q -b $BRANCH /srv/origin.git $CHECKOUT"
pass "published and cloned to $CHECKOUT"

step "prepare-server.sh"
ssh-keygen -q -t ed25519 -N "" -C "deproi:$NAME" -f "$WORK/key"
docker cp "$HERE/prepare-server.sh" "$SERVER:/root/"
docker cp "$HERE/doctor.sh" "$SERVER:/root/"
on_server "/root/prepare-server.sh --name $NAME --checkout $CHECKOUT --script $SCRIPT_PATH \
  --public-key '$(cut -d' ' -f1,2 "$WORK/key.pub")'" > "$WORK/out" 2>&1 || { cat "$WORK/out" >&2; fail "prepare-server.sh failed"; }
python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
d['checkout']['path'] = sys.argv[2]
d['checkout']['owner'] = 'app'
json.dump(d, open(sys.argv[3], 'w'), indent=2)
" "$CONFIG" "$CHECKOUT" "$WORK/config.json"
docker cp "$WORK/config.json" "$SERVER:/etc/deproi/$NAME.json"
on_server "chown root:root /etc/deproi/$NAME.json && chmod 600 /etc/deproi/$NAME.json"
if [ -n "$SECRETS_PATH" ]; then
  case "$SECRETS_PATH" in /*) target="$SECRETS_PATH" ;; *) target="$CHECKOUT/$SECRETS_PATH" ;; esac
  if [ -n "$SECRETS" ]; then docker cp "$SECRETS" "$SERVER:$target"; else on_server "touch $target"; fi
  on_server "chown root:root $target && chmod 600 $target"
fi
pass "installed (config, key${SECRETS:+, secrets})"

step "doctor.sh"
on_server "/root/doctor.sh --name $NAME" > "$WORK/out" 2>&1 || { sed 's/^/      │ /' "$WORK/out" >&2; fail "doctor found problems"; }
pass "all checks passed"

ssh-keyscan -p "$PORT" -t ed25519 127.0.0.1 2> /dev/null > "$WORK/known_hosts"

step "First deploy"
deploy

step "Second deploy (a new commit)"
docker exec -u app -w /home/app/project "$SERVER" bash -c "git commit -q --allow-empty -m second && git push -q origin $BRANCH"
deploy
grep -q "previous=-" "$WORK/out" && fail "the second deploy found no previous version"
pass "rolled forward from the first version"

printf '\n\033[1;32mRehearsal passed: %s deploys with Deproi.\033[0m\n' "$NAME"
