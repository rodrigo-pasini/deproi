#!/usr/bin/env bash
# Deproi — create the deploy key of one environment (https://github.com/rodrigo-pasini/deproi)
#
# Run on YOUR MACHINE (not the server). Needs ssh-keygen, ssh-keyscan and an
# authenticated GitHub CLI (gh auth status).
#
#   ./create-deploy-key.sh --name myapp-prod --host 203.0.113.10 \
#       --repo acme/myapp --environment production --branch main [--port 22] [--no-github]
#
# What it does:
#   1. generates a new ed25519 key pair in a temporary folder;
#   2. shows the command to authorize the public key on the server (prepare-server.sh);
#   3. reads the server's host key and asks you to compare its fingerprint;
#   4. creates the GitHub environment (deploys only from --branch) and stores
#      DEPROI_SSH_KEY, DEPROI_KNOWN_HOSTS and DEPROI_HOST in it;
#   5. deletes the private key from this machine. Only GitHub keeps it.
set -euo pipefail

NAME=""
HOST=""
REPO=""
ENVIRONMENT=""
BRANCH=""
PORT="22"
GITHUB=1

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="${2:-}"; shift 2 ;;
    --host) HOST="${2:-}"; shift 2 ;;
    --repo) REPO="${2:-}"; shift 2 ;;
    --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    --port) PORT="${2:-}"; shift 2 ;;
    --no-github) GITHUB=0; shift ;;
    -h | --help) usage 0 ;;
    *) printf 'Unknown option: %s\n\n' "$1" >&2; usage 2 ;;
  esac
done

fail() {
  printf '❌ %s\n' "$*" >&2
  exit 1
}
[[ "$NAME" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || fail "--name must match the server's deproi-<name>, e.g. myapp-prod"
[ -n "$HOST" ] || fail "--host is required (the server's address)"
[[ "$PORT" =~ ^[0-9]+$ ]] || fail "--port must be a number"
for tool in ssh-keygen ssh-keyscan; do command -v "$tool" > /dev/null || fail "$tool is missing"; done
if [ "$GITHUB" -eq 1 ]; then
  [[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || fail "--repo must be owner/name"
  [ -n "$ENVIRONMENT" ] || fail "--environment is required (GitHub environment, e.g. production)"
  [ -n "$BRANCH" ] || fail "--branch is required (the branch this environment deploys)"
  command -v gh > /dev/null || fail "the GitHub CLI (gh) is missing — or use --no-github"
  gh auth status > /dev/null 2>&1 || fail "gh is not authenticated: gh auth login"
fi

WORK=$(mktemp -d)
cleanup() {
  if [ -f "$WORK/key" ]; then
    shred -u "$WORK/key" 2> /dev/null || rm -f "$WORK/key"
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "▶ 1/5 Generating a new ed25519 key for $NAME"
ssh-keygen -q -t ed25519 -N "" -C "deproi:$NAME" -f "$WORK/key"
PUBLIC=$(cut -d' ' -f1,2 "$WORK/key.pub")

cat << EOF

▶ 2/5 Authorize the key on the server. Run THERE, as root:

    sudo ./prepare-server.sh --name $NAME --checkout <path of the checkout> \\
         --public-key "$PUBLIC"

EOF
read -r -p "Press Enter when it is done… " _

echo
echo "▶ 3/5 Server identity"
ssh-keyscan -p "$PORT" -t ed25519 "$HOST" 2> /dev/null > "$WORK/known_hosts" || true
[ -s "$WORK/known_hosts" ] || fail "could not read the host key of $HOST:$PORT"
echo "  Fingerprint seen from here:"
ssh-keygen -lf "$WORK/known_hosts" | sed 's/^/    /'
echo "  On the server, run:  ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub"
read -r -p "  Do the two fingerprints match exactly? [y/N] " answer
[[ "$answer" =~ ^[yY] ]] || fail "fingerprints differ or were not checked — stopping (nothing was stored)"

if [ "$GITHUB" -eq 0 ]; then
  cat << EOF

▶ 4/5 Store these as secrets of your GitHub environment (Settings → Environments):
  DEPROI_HOST         $HOST
  DEPROI_KNOWN_HOSTS  (below)
$(sed 's/^/    /' "$WORK/known_hosts")
  DEPROI_SSH_KEY      (below — copy it now; it is deleted when this script ends)
$(sed 's/^/    /' "$WORK/key")
EOF
  read -r -p "Press Enter after storing them… " _
else
  echo
  echo "▶ 4/5 GitHub environment $ENVIRONMENT in $REPO"
  gh api -X PUT "repos/$REPO/environments/$ENVIRONMENT" --silent \
    -F "deployment_branch_policy[protected_branches]=false" \
    -F "deployment_branch_policy[custom_branch_policies]=true"
  gh api -X POST "repos/$REPO/environments/$ENVIRONMENT/deployment-branch-policies" --silent \
    -f name="$BRANCH" -f type=branch 2> /dev/null || true
  echo "  environment ready (deploys only from $BRANCH)"
  gh secret set DEPROI_SSH_KEY --repo "$REPO" --env "$ENVIRONMENT" < "$WORK/key"
  gh secret set DEPROI_KNOWN_HOSTS --repo "$REPO" --env "$ENVIRONMENT" < "$WORK/known_hosts"
  printf '%s' "$HOST" | gh secret set DEPROI_HOST --repo "$REPO" --env "$ENVIRONMENT"
  if [ "$PORT" != "22" ]; then
    gh variable set DEPROI_SSH_PORT --repo "$REPO" --env "$ENVIRONMENT" --body "$PORT"
  fi
  echo "  secrets stored: DEPROI_SSH_KEY, DEPROI_KNOWN_HOSTS, DEPROI_HOST"
fi

echo
echo "▶ 5/5 Deleting the private key from this machine"
cleanup
trap - EXIT
echo "  done — only GitHub has it now. To rotate the key, run this script again."
cat << EOF

Next: add .github/workflows/deploy-$ENVIRONMENT.yml (render-workflow.sh) and push to ${BRANCH:-the branch}.
Recommended for production: Settings → Environments → $ENVIRONMENT → Required reviewers.
EOF
