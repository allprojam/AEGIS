#!/usr/bin/env bash
# Aegis MCP firewall rules. Run as root. Idempotent: safe to re-run.
#
# THE ONE DANGEROUS PART. ufw is currently INACTIVE. `ufw enable` on a live server can drop an
# SSH session mid-command and leave the box unreachable if the SSH rule is not already in place.
# So this script ALLOWS SSH FIRST and only then enables. Never reorder these.
#
# WHAT IS EXPOSED: 8051 (the MCP endpoint), and nothing else new.
#
# WHY 8051 IS OPENED AT ALL. The service binds loopback only. Reaching it from the internet
# needs either (a) the unit bound to 0.0.0.0, or (b) a proxy on the box forwarding loopback.
# This script does (b)'s prerequisite only: it opens the port, it does NOT change the unit.
# Until a proxy exists, 8051 open on a loopback-bound service is harmless — the kernel refuses
# the connection regardless of what ufw allows.
#
# NOT DONE HERE: installing a proxy. There is no nginx/caddy/traefik on this box. If you add
# one, it must set TRUST_PROXY=1 for the service AND bind loopback, so X-Forwarded-For can
# only be supplied by that proxy. Otherwise per-IP limiting is worthless: any caller can lie.

set -euo pipefail

MCP_PORT="${MCP_PORT:-8051}"

if [[ $EUID -ne 0 ]]; then
  echo "must run as root" >&2; exit 1
fi

echo "== current state =="
ufw status verbose || true

echo "== 1. allow SSH FIRST (the step that prevents lockout) =="
ufw allow 22/tcp comment 'ssh — do not remove'
ufw limit 22/tcp comment 'ssh rate limit'

echo "== 2. allow the MCP port =="
ufw allow "${MCP_PORT}/tcp" comment 'aegis-mcp (behind proxy or direct)'

echo "== 3. default deny inbound, allow outbound =="
ufw default deny incoming
ufw default allow outgoing

echo "== 4. enable (only after SSH is allowed) =="
ufw --force enable

echo "== 5. result =="
ufw status numbered

echo
echo "NOTE: tailscale0 traffic is allowed by ufw by default when Tailscale is running."
echo "      Admin access over the tailnet keeps working without an extra rule."
