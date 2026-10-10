#!/usr/bin/env bash
# One-time setup on the Pi: installs the systemd timer that runs deploy.sh.
# Usage (from your normal user): sudo ./deploy/install.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ] || [ -z "${SUDO_USER:-}" ]; then
  echo "run this via sudo from your normal user: sudo ./deploy/install.sh" >&2
  exit 1
fi

deploy_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
repo_dir="${REPO_DIR:-$deploy_home/due-brew}"

sed -e "s|__USER__|$SUDO_USER|g" -e "s|__REPO_DIR__|$repo_dir|g" \
  "$repo_dir/deploy/due-brew-deploy.service" >/etc/systemd/system/due-brew-deploy.service
install -m 644 "$repo_dir/deploy/due-brew-deploy.timer" /etc/systemd/system/due-brew-deploy.timer

systemctl daemon-reload
systemctl enable --now due-brew-deploy.timer
echo "installed. next run: systemctl list-timers due-brew-deploy.timer"
echo "logs:               journalctl -u due-brew-deploy -n 50"
