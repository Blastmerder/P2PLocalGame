#!/usr/bin/env bash
set -uo pipefail

# Настройки должны строго совпадать с оригинальным скриптом
NS="appns"
VETH_HOST="veth0"
SUBNET="10.200.1.0/24"
TABLE_ID=200
TABLE_NAME="novpn"
EXT_IF=${1:-"eth0"} # передайте ваш внешний интерфейс первым аргументом

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
  echo "Запустите скрипт от root"
  exit 1
fi

echo "Начало отката конфигурации..."

# 1. Удаление правил iptables (NAT и FORWARD)
echo "Удаление правил iptables..."
iptables -t nat -D POSTROUTING -s "$SUBNET" -o "$EXT_IF" -j MASQUERADE 2>/dev/null || true
iptables -D FORWARD -s "$SUBNET" -o "$EXT_IF" -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -d "$SUBNET" -i "$EXT_IF" -j ACCEPT 2>/dev/null || true

# 2. Удаление правила маршрутизации ip rule
echo "Удаление правил маршрутизации..."
while ip rule show | grep -q "from $SUBNET lookup $TABLE_ID"; do
  ip rule del from "$SUBNET" lookup "$TABLE_ID" priority 100 2>/dev/null || break
done
ip route flush cache

# 3. Очистка таблицы маршрутизации /etc/iproute2/rt_tables
RT_FILE="/etc/iproute2/rt_tables"
if [ -f "$RT_FILE" ] && grep -q -E "^${TABLE_ID}[[:space:]]" "$RT_FILE"; then
  echo "Удаление записи таблицы из $RT_FILE..."
  # Создаем резервную копию и удаляем строку
  sed -i.bak "/^${TABLE_ID}[[:space:]]${TABLE_NAME}/d" "$RT_FILE"
fi

# 4. Удаление сетевого интерфейса veth
# При удалении veth_host на хосте, veth_ns внутри namespace удалится автоматически
if ip link show "$VETH_HOST" >/dev/null 2>&1; then
  echo "Удаление интерфейса $VETH_HOST..."
  ip link del "$VETH_HOST"
fi

# 5. Удаление сетевого пространства имен (namespace)
if ip netns list | grep -q "$NS"; then
  echo "Удаление namespace $NS..."
  ip netns del "$NS"
fi

# Примечание: sysctl net.ipv4.ip_forward обычно оставляют включенным (1), 
# так как его отключение может сломать другие контейнеры (Docker/LXC) или VPN.

sudo ip rule del from 10.200.1.0/24 2>/dev/null || true

echo "Откат успешно завершен!"

