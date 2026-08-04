#!/bin/sh
# Issue #189: runs automatically before nginx starts (nginx:alpine's own
# /docker-entrypoint.d/ mechanism executes every *.sh script here, in
# order, before the main process - no Dockerfile CMD/ENTRYPOINT override
# needed).
#
# nginx's HTTPS server block (nginx.conf, with __DOMAIN__ already
# substituted at build time - see the Dockerfile) always references
# /etc/nginx/ssl/live/$DOMAIN/{fullchain,privkey}.pem - it has no way to
# know whether a real Let's Encrypt certificate has been issued yet. On a
# fresh `docker compose up` (local development, CI, or a brand new EC2
# instance before certbot has ever run), that path is empty, and nginx
# would otherwise fail to start at all ("cannot load certificate").
#
# This generates a short-lived, self-signed placeholder certificate at
# that same path - but only if nothing is there yet. Once the real
# certificate volume is populated (see infra/docker-compose.yml's
# `certbot` service and docs/deployment.md's HTTPS section), this script
# finds real files already present and does nothing, every time the
# container starts afterward. $DOMAIN comes from the Dockerfile's own
# ENV (set from the DOMAIN build arg), so this always agrees with the
# path nginx.conf was built to expect.
set -e

CERT_DIR="/etc/nginx/ssl/live/$DOMAIN"

if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
  exit 0
fi

echo "ensure-dummy-cert.sh: no certificate found at $CERT_DIR - generating a self-signed placeholder"

mkdir -p "$CERT_DIR"

# 1 day validity: this is never meant to be trusted or long-lived, only
# to let nginx bind to 443 and serve traffic (with a browser warning)
# until the real certificate volume is mounted in. Regenerated on every
# container start until then, so an expired placeholder is never an
# actual problem in practice.
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/CN=localhost" >/dev/null 2>&1
