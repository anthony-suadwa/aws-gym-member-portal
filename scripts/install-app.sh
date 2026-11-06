#!/usr/bin/env bash
# Installs the Northside Gym app on one web server (Amazon Linux 2023).
# Run from the cloned repo, on EACH web server:
#   sudo bash scripts/install-app.sh
# Safe to run again: it updates the code and keeps your /etc/gym-app.env.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/install-app.sh" >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR=/opt/gym-app
ENV_FILE=/etc/gym-app.env

echo "==> Installing packages"
dnf install -y -q httpd python3 python3-pip postgresql16

echo "==> Copying the app to $APP_DIR"
mkdir -p "$APP_DIR"
cp -r "$REPO_DIR/app/." "$APP_DIR/"
chown -R ec2-user:ec2-user "$APP_DIR"

echo "==> Creating the Python virtual environment"
sudo -u ec2-user python3 -m venv "$APP_DIR/venv"
sudo -u ec2-user "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> Installing the systemd service and Apache proxy"
cp "$APP_DIR/deploy/gym-app.service" /etc/systemd/system/gym-app.service
cp "$APP_DIR/deploy/gym-proxy.conf" /etc/httpd/conf.d/gym-proxy.conf
systemctl daemon-reload
systemctl enable --now httpd
systemctl enable gym-app

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$APP_DIR/deploy/gym-app.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo
  echo "==> Created $ENV_FILE from the template. Next:"
  echo "    1. sudo nano $ENV_FILE   (fill in DB_HOST, DB_PASSWORD, SECRET_KEY)"
  echo "    2. sudo systemctl restart gym-app"
  echo "    3. curl -s localhost/health   (should print: ok)"
else
  echo "==> Keeping existing $ENV_FILE; restarting the app"
  systemctl restart gym-app
  sleep 2
  curl -s localhost/health && echo "  <- health check"
fi
