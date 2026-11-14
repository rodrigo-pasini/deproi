#!/usr/bin/env bash
# Deproi end-to-end test: the whole path, for real.
#
#   GitHub-like client (this machine) → ssh with a locked key → forced command →
#   sudo → deproi.py → docker compose → health → rollback…
#
# A container plays the server (sshd, sudo, git, Python 3.10, Docker CLI on the
# host's daemon). prepare-server.sh and doctor.sh run inside it as an operator
# would. The example app is the project. Needs Docker; leaves nothing behind.
#
#   tests/e2e/run.sh
#
# Options (environment variables):
#   DEPROI_E2E_PORT=2222          host port for the server's SSH
#   DEPROI_E2E_LANGUAGE=pt-BR     language of Deproi's messages (default en)
#   DEPROI_E2E_SAVE=<dir>         keep each deploy's output there (the docs' terminal image uses it)
# Single-quoted commands run inside the server container: they expand there, on purpose.
# shellcheck disable=SC2016
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
NAME="deproi-example-prod"
SERVER_IMAGE="deproi-e2e-server"
SERVER="deproi-e2e-server"
PORT="${DEPROI_E2E_PORT:-2222}"
LANGUAGE="${DEPROI_E2E_LANGUAGE:-en}"
SAVE="${DEPROI_E2E_SAVE:-}"
WORK=$(mktemp -d)
STEP=0

cleanup() {
  set +e
  docker rm -f "$SERVER" > /dev/null 2>&1
  docker ps -aq --filter "label=com.docker.compose.project=$NAME" | xargs -r docker rm -f > /dev/null
  docker network rm "${NAME}_default" > /dev/null 2>&1
  docker volume rm "${NAME}_data" > /dev/null 2>&1
  docker images -q deproi-example | sort -u | xargs -r docker rmi -f > /dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT

scenario() {
  STEP=$((STEP + 1))
  printf '\n\033[1m━━ %d. %s\033[0m\n' "$STEP" "$*"
}
pass() { printf '   ✅ %s\n' "$*"; }
fail() {
  printf '   ❌ %s\n' "$*" >&2
  [ -f "$WORK/out" ] && sed 's/^/      │ /' "$WORK/out" >&2
  exit 1
}
on_server() { docker exec "$SERVER" bash -c "$1"; }
as_app() { docker exec -u app -w /home/app/project "$SERVER" bash -c "$1"; }

commit() {
  as_app "$1 && git add -A && git commit -qm '$2' && git push -q origin main"
  as_app "git rev-parse --short=12 HEAD"
}

deploy() {
  # Exactly what the GitHub workflow does: no remote command, strict host key.
  ssh -i "$WORK/key" -p "$PORT" -o IdentitiesOnly=yes -o UserKnownHostsFile="$WORK/known_hosts" \
    -o StrictHostKeyChecking=yes -o BatchMode=yes deproi@127.0.0.1 "$@" > "$WORK/out" 2>&1 || true
  if [ -n "$SAVE" ]; then
    mkdir -p "$SAVE"
    grep -v '^Pseudo-terminal' "$WORK/out" > "$SAVE/$(printf '%02d' "$STEP").log" || true
  fi
}

expect() {
  local situation="$1"
  grep -q "^result: $situation " "$WORK/out" || fail "expected result $situation"
  pass "$(grep '^result: ' "$WORK/out")"
}

web_says() {
  local web
  web=$(docker ps -q --filter "label=com.docker.compose.project=$NAME" --filter "label=com.docker.compose.service=web-prod")
  docker exec "$web" python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/').read().decode())"
}

scenario "Server container (Ubuntu 22.04, Python 3.10)"
docker build -q -t "$SERVER_IMAGE" "$ROOT/tests/e2e" > /dev/null
docker run -d --name "$SERVER" -p "127.0.0.1:$PORT:22" -v /var/run/docker.sock:/var/run/docker.sock "$SERVER_IMAGE" > /dev/null
on_server "python3 -V && docker compose version | head -n 1" | sed 's/^/   /'

scenario "Project repository with Deproi vendored, and its checkout on the server"
# Give the host's docker socket group a name inside the container, so the system users created
# later never get its gid by coincidence (which would let them use Docker).
on_server 'gid=$(stat -c %g /var/run/docker.sock); getent group "$gid" > /dev/null || groupadd -g "$gid" docker-host'
on_server "useradd -m -s /bin/bash app && git init -q --bare -b main /srv/origin.git && chown -R app /srv/origin.git"
docker cp "$ROOT/example/." "$SERVER:/home/app/project"
docker cp "$ROOT/deproi.py" "$SERVER:/home/app/project/deploy/deproi.py"
on_server "chown -R app:app /home/app/project && sed -i 's/^WEB_PORT=.*/WEB_PORT=18080/' /home/app/project/deploy/prod.compose.env"
as_app "git init -q -b main && git config user.email e2e@example.com && git config user.name e2e && \
  git remote add origin /srv/origin.git && git add -A && git commit -qm 'first' && git push -q origin main"
on_server "install -d -o app -g app /srv/$NAME && runuser -u app -- git clone -q /srv/origin.git /srv/$NAME"
pass "origin, project and checkout ready"

scenario "prepare-server.sh, as an operator would run it"
ssh-keygen -q -t ed25519 -N "" -C "deproi:$NAME" -f "$WORK/key"
docker cp "$ROOT/scripts/prepare-server.sh" "$SERVER:/root/prepare-server.sh"
docker cp "$ROOT/scripts/doctor.sh" "$SERVER:/root/doctor.sh"
on_server "/root/prepare-server.sh --name $NAME --checkout /srv/$NAME --public-key '$(cut -d' ' -f1,2 "$WORK/key.pub")'" |
  sed 's/^/   │ /'
docker cp "$ROOT/example/deploy/server-config.json" "$SERVER:/etc/deproi/$NAME.json"
on_server "sed -i 's/\"language\": \"en\"/\"language\": \"$LANGUAGE\"/' /etc/deproi/$NAME.json"
on_server "chown root:root /etc/deproi/$NAME.json && chmod 600 /etc/deproi/$NAME.json"
on_server "/root/prepare-server.sh --name $NAME --checkout /srv/$NAME" > /dev/null || fail "prepare-server.sh is not idempotent"
pass "idempotent"

scenario "doctor.sh"
on_server "/root/doctor.sh --name $NAME" > "$WORK/out" 2>&1 || fail "doctor found problems"
pass "all checks passed"

ssh-keyscan -p "$PORT" -t ed25519 127.0.0.1 2> /dev/null > "$WORK/known_hosts"

scenario "First deploy"
FIRST=$(as_app "git rev-parse --short=12 HEAD")
deploy
expect SUCCESS
grep -q "previous=- " "$WORK/out" || fail "a first deploy has no previous version"
web_says | grep -q "\"version\": \"$FIRST\", \"schema\": \"3\"" || fail "web is not serving $FIRST with the migrated schema"
pass "web serves $FIRST, migration hook ran"

scenario "A new commit"
SECOND=$(commit "sed -i 's/\"hello\"/\"hi\"/' app/server.py" "second")
deploy
expect SUCCESS
grep -q "commit=$SECOND previous=$FIRST " "$WORK/out" || fail "expected $FIRST → $SECOND"
web_says | grep -q "\"version\": \"$SECOND\"" || fail "web is not serving $SECOND"
pass "web serves $SECOND"

scenario "The key is locked: a requested command is ignored"
deploy "id; cat /etc/shadow"
expect SUCCESS
grep -q "uid=" "$WORK/out" && fail "the requested command ran"
grep -q "Same commit already live\|Mesmo commit que já está no ar" "$WORK/out" || fail "expected a republish"
pass "only the deploy ran (a republish, force-recreated)"
# -W asks for a forwarding channel at once; restrict makes the server refuse it.
timeout 30 ssh -i "$WORK/key" -p "$PORT" -o IdentitiesOnly=yes -o UserKnownHostsFile="$WORK/known_hosts" \
  -o BatchMode=yes -W 127.0.0.1:22 deproi@127.0.0.1 < /dev/null > /dev/null 2>&1 &&
  fail "port forwarding was allowed"
pass "port forwarding refused (restrict)"

scenario "A broken version rolls back by itself"
BROKEN=$(commit "touch app/BROKEN" "broken")
deploy
expect FAILED_ROLLED_BACK
web_says | grep -q "\"version\": \"$SECOND\"" || fail "web did not go back to $SECOND"
pass "$BROKEN never went live; web serves $SECOND again"

scenario "A busy protected service stays on its version"
THIRD=$(commit "git rm -q app/BROKEN" "fixed")
WORKER=$(docker ps -q --filter "label=com.docker.compose.project=$NAME" --filter "label=com.docker.compose.service=worker-prod")
docker exec "$WORKER" touch /tmp/job
deploy
expect SUCCESS_PROTECTED_DEFERRED
docker inspect --format '{{.Config.Image}}' "$WORKER" | grep -q ":$SECOND$" || fail "the busy worker was recreated"
docker exec "$WORKER" rm /tmp/job
pass "worker stayed on $SECOND while web went to $THIRD"
deploy
expect SUCCESS
grep -q "protected=worker-prod:updated" "$WORK/out" || fail "the idle worker was not updated"
pass "idle again: updated on the next deploy"

scenario "Self-update from the commit"
commit "sed -i 's/^SELF_UPDATING = True$/SELF_UPDATING = True  # e2e/' deploy/deproi.py" "update deproi" > /dev/null
deploy
expect SUCCESS
grep -q "script=updated:" "$WORK/out" || fail "the script did not update itself"
on_server "grep -q '^SELF_UPDATING = True  # e2e$' /usr/local/sbin/deproi-$NAME" || fail "the installed script did not change"
pass "installed script replaced and re-executed"

scenario "Refusals change nothing"
on_server "echo '# local edit' >> /srv/$NAME/compose.yaml"
deploy
expect REFUSED
grep -q "compose.yaml" "$WORK/out" || fail "expected the dirty checkout message"
on_server "runuser -u app -- git -C /srv/$NAME checkout -q -- compose.yaml"
pass "dirty checkout refused, nothing touched"
on_server "runuser -u deproi -- sudo -n /usr/local/sbin/deproi-$NAME --anything" > /dev/null 2>&1 &&
  fail "sudo accepted an argument"
pass "sudo refuses arguments"
on_server "runuser -u deproi -- docker ps" > /dev/null 2>&1 && fail "the deproi user can use docker"
pass "the deproi user cannot use docker"

scenario "prepare-server.sh refuses a deproi user that can use Docker"
on_server 'usermod -aG "$(stat -c %G /var/run/docker.sock)" deproi'
on_server "/root/prepare-server.sh --name $NAME --checkout /srv/$NAME" > "$WORK/out" 2>&1 && fail "accepted"
grep -q "root without sudo" "$WORK/out" || fail "expected the docker socket message"
on_server "/root/doctor.sh --name $NAME" > "$WORK/out" 2>&1 && fail "doctor did not notice"
on_server 'gpasswd -d deproi "$(stat -c %G /var/run/docker.sock)"' > /dev/null
pass "both prepare-server.sh and doctor.sh notice it"

scenario "doctor.sh after all of it"
on_server "/root/doctor.sh --name $NAME" > "$WORK/out" 2>&1 || fail "doctor found problems"
pass "all checks passed"

printf '\n\033[1;32mEnd-to-end: all %d scenarios passed.\033[0m\n' "$STEP"
