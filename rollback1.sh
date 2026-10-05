#!/usr/bin/env bash
set -euo pipefail

# ---------- Настройте эти переменные (должны совпадать с основным скриптом) ----------
NS="appns"
VETH_HOST="veth0"
VETH_NS="veth1"
SUBNET="10.200.1.0/24"
HOST_IP="10.200.1.1"
TABLE_ID=200
TABLE_NAME="novpn"
EXT_IF=$1                # внешний интерфейс (должен быть передан как аргумент)
# ------------------------------------------------

# Требуем root
if [ "$EUID" -ne 0 ]; then
  echo "Запустите скрипт от root"
  exit 1
fi

# Проверяем что интерфейс передан
if [ -z "$EXT_IF" ]; then
  echo "Ошибка: укажите внешний интерфейс как аргумент"
  echo "Использование: $0 <внешний_интерфейс>"
  exit 1
fi

echo "Откатываем настройки сети..."

# 1) Удаляем iptables правила NAT
echo "Удаляем NAT правила..."
iptables -t nat -D POSTROUTING -s "$SUBNET" -o "$EXT_IF" -j MASQUERADE >/dev/null 2>&1 || true

# 2) Удаляем FORWARD правила
echo "Удаляем FORWARD правила..."
iptables -D FORWARD -i "$VETH_HOST" -o "$EXT_IF" -j ACCEPT >/dev/null 2>&1 || true
iptables -D FORWARD -i "$EXT_IF" -o "$VETH_HOST" -m state --state ESTABLISHED,RELATED -j ACCEPT >/dev/null 2>&1 || true

# 3) Удаляем ip rule
echo "Удаляем правило маршрутизации..."
ip rule delete from "$SUBNET" lookup "$TABLE_ID" priority 100 >/dev/null 2>&1 || true

# 4) Удаляем запись из таблицы маршрутов
echo "Удаляем запись из /etc/iproute2/rt_tables..."
RT_FILE="/etc/iproute2/rt_tables"
if [ -f "$RT_FILE" ]; then
  sed -i "/^${TABLE_ID}[[:space:]]/d" "$RT_FILE"
fi

# 5) Удаляем veth интерфейс (это удалит namespace если там больше нечего)
echo "Удаляем veth интерфейс..."
if ip link show "$VETH_HOST" >/dev/null 2>&1; then
  ip link delete "$VETH_HOST"
fi

# 6) Удаляем namespace (если остался)
echo "Удаляем namespace..."
if ip netns list | grep -q "$NS"; then
  ip netns delete "$NS"
fi

# 7) Очищаем кэш маршрутов
ip route flush cache

# 8) Отключаем IP forwarding (опционально, можно оставить)
# sysctl -w net.ipv4.ip_forward=0 >/dev/null

echo "Откат завершён успешно!"
echo "Все настройки сети восстановлены в исходное состояние."

