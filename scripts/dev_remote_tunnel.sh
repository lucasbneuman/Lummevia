#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

require_var() {
  local name="$1"

  if [[ -z "${!name:-}" ]]; then
    printf 'Missing required variable: %s\n' "${name}" >&2
    exit 1
  fi
}

command -v ssh >/dev/null 2>&1 || {
  printf 'OpenSSH client not found. Install ssh before opening the remote development tunnel.\n' >&2
  exit 1
}

require_var SSH_TUNNEL_HOST
require_var SSH_TUNNEL_USER
require_var SSH_TUNNEL_POSTGRES_REMOTE_HOST
require_var SSH_TUNNEL_REDIS_REMOTE_HOST

: "${SSH_TUNNEL_PORT:=22}"
: "${SSH_TUNNEL_POSTGRES_REMOTE_PORT:=5432}"
: "${SSH_TUNNEL_POSTGRES_LOCAL_PORT:=15432}"
: "${SSH_TUNNEL_REDIS_REMOTE_PORT:=6379}"
: "${SSH_TUNNEL_REDIS_LOCAL_PORT:=16379}"

ssh_args=(
  -N
  -T
  -o BatchMode=yes
  -o ExitOnForwardFailure=yes
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
  -p "${SSH_TUNNEL_PORT}"
  -L "127.0.0.1:${SSH_TUNNEL_POSTGRES_LOCAL_PORT}:${SSH_TUNNEL_POSTGRES_REMOTE_HOST}:${SSH_TUNNEL_POSTGRES_REMOTE_PORT}"
  -L "127.0.0.1:${SSH_TUNNEL_REDIS_LOCAL_PORT}:${SSH_TUNNEL_REDIS_REMOTE_HOST}:${SSH_TUNNEL_REDIS_REMOTE_PORT}"
)

if [[ -n "${SSH_TUNNEL_SSH_CONFIG_FILE:-}" ]]; then
  ssh_args+=(-F "${SSH_TUNNEL_SSH_CONFIG_FILE}")
fi

if [[ -n "${SSH_TUNNEL_IDENTITY_FILE:-}" ]]; then
  identity_file="${SSH_TUNNEL_IDENTITY_FILE/#\~/${HOME}}"
  if [[ ! -f "${identity_file}" ]]; then
    printf 'SSH identity file not found: %s\n' "${identity_file}" >&2
    exit 1
  fi
  ssh_args+=(-i "${identity_file}")
fi

printf 'Forwarding local 127.0.0.1:%s to remote Postgres %s:%s\n' \
  "${SSH_TUNNEL_POSTGRES_LOCAL_PORT}" \
  "${SSH_TUNNEL_POSTGRES_REMOTE_HOST}" \
  "${SSH_TUNNEL_POSTGRES_REMOTE_PORT}"
printf 'Forwarding local 127.0.0.1:%s to remote Redis %s:%s\n' \
  "${SSH_TUNNEL_REDIS_LOCAL_PORT}" \
  "${SSH_TUNNEL_REDIS_REMOTE_HOST}" \
  "${SSH_TUNNEL_REDIS_REMOTE_PORT}"
printf 'Tunnel stays open while this command is running.\n'

exec ssh "${ssh_args[@]}" "${SSH_TUNNEL_USER}@${SSH_TUNNEL_HOST}"
