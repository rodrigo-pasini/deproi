#!/usr/bin/env bash
# Deproi — render the GitHub workflows of one environment (https://github.com/rodrigo-pasini/deproi)
#
# Run from a clone of the Deproi repository. Prints to stdout.
#
#   ./render-workflow.sh deploy --name myapp-prod --branch main --environment production \
#       > .github/workflows/deploy-production.yml
#   ./render-workflow.sh update [--script-path deploy/deproi.py] > .github/workflows/deproi-update.yml
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TEMPLATES="$HERE/../templates/github"
KIND="${1:-}"
[ $# -gt 0 ] && shift
NAME=""
BRANCH=""
ENVIRONMENT=""
SCRIPT_PATH="deploy/deproi.py"

while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
    --script-path) SCRIPT_PATH="${2:-}"; shift 2 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

fail() {
  printf '%s\n' "$*" >&2
  exit 2
}

case "$KIND" in
  deploy)
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || fail "--name must match the server's deproi-<name>"
    [[ "$BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]] || fail "--branch is required"
    [[ "$ENVIRONMENT" =~ ^[A-Za-z0-9._-]+$ ]] || fail "--environment is required (letters, digits, . _ -)"
    sed -e "s|__DEPROI_NAME__|$NAME|g" -e "s|__DEPROI_BRANCH__|$BRANCH|g" \
      -e "s|__DEPROI_ENVIRONMENT__|$ENVIRONMENT|g" "$TEMPLATES/deploy.yml"
    ;;
  update)
    [[ "$SCRIPT_PATH" =~ ^[A-Za-z0-9._/-]+$ && "$SCRIPT_PATH" != /* && "$SCRIPT_PATH" != ..* ]] ||
      fail "--script-path must be a path inside the repository"
    sed -e "s|__DEPROI_SCRIPT_PATH__|$SCRIPT_PATH|g" "$TEMPLATES/deproi-update.yml"
    ;;
  *)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
