#!/bin/sh
# keepalived health check: returns 0 when the local dataplane is serving.
# Used as a vrrp_script with a negative weight, so a broken dataplane keeps
# this node from taking the virtual IP.
set -e

# TCP connect to the local Nginx health listener.
if ! (exec 3<>/dev/tcp/127.0.0.1/8443) 2>/dev/null; then
    exit 1
fi

# Require a valid HTTP response.
printf 'GET /healthz HTTP/1.0\r\n\r\n' >&3
response=$(head -n 1 <&3)
exec 3>&-

case "$response" in
    *200*) exit 0 ;;
    *)     exit 1 ;;
esac
