#!/usr/bin/env bash
# Однократная подготовка сервера Oracle Cloud (Ubuntu или Oracle Linux): Docker + открытые порты 80/443.
# Запуск на сервере: sudo bash setup-server.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Запустите через sudo" >&2
  exit 1
fi

# 1. Docker (официальный установщик docker.com; ставит и compose-плагин)
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker
TARGET_USER="${SUDO_USER:-}"
if [ -n "$TARGET_USER" ]; then
  usermod -aG docker "$TARGET_USER"
fi

# 2. Файрвол внутри ОС. Образы Oracle по умолчанию закрывают всё, кроме SSH.
if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
  # Oracle Linux
  firewall-cmd --permanent --add-service=http
  firewall-cmd --permanent --add-service=https
  firewall-cmd --reload
else
  # Ubuntu: правила iptables с REJECT в конце цепочки — вставляем свои перед ним
  for port in 80 443; do
    iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null \
      || iptables -I INPUT 6 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  done
  if command -v netfilter-persistent >/dev/null 2>&1; then
    netfilter-persistent save
  fi
fi

mkdir -p /opt/zherkoz
[ -n "$TARGET_USER" ] && chown "$TARGET_USER":"$TARGET_USER" /opt/zherkoz

echo
echo "Готово. Docker: $(docker --version)"
echo "Не забудьте открыть порты 80 и 443 в Oracle Cloud: VCN → Security List → Ingress Rules."
echo "Перелогиньтесь, чтобы docker работал без sudo."
