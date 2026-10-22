#!/bin/sh
# keepalived state-change notifier.
# $1 = MASTER | BACKUP | FAULT
# Posts the transition to the monitoring stack so the topology in Grafana
# reflects which node currently holds the virtual IP.
set -e

STATE="$1"
HOSTNAME_S="$(hostname)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Replace with the real endpoint and credentials before use.
MONITOR_URL="${MONITOR_URL:-http://127.0.0.1:9090/metrics}"

printf 'edge_vrrp_state{node="%s",state="%s"} 1\n' "$HOSTNAME_S" "$STATE" >> /var/lib/node_exporter/textfile/edge.prom
logger -t keepalived "edge vrrp state=$STATE host=$HOSTNAME_S time=$TIMESTAMP"
