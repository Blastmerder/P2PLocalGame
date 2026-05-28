#!/usr/bin/env bash
set -euo pipefail

# ---------- Настройте эти переменные ----------
NS="appns"
VETH_HOST="veth0"
VETH_NS="veth1"
SUBNET="10.200.1.0/24"
HOST_IP="10.200.1.1"
NS_IP="10.200.1.2"
TABLE_ID=200
TABLE_NAME="novpn"
EXT_IF="wlan0"                # внешний интерфейс
EXT_GW="192.168.1.1"          # шлюз
GAME_CMD="/path/to/game"      # путь к игре
# ------------------------------------------------

# Требуем root
if [ "$EUID" -ne 0 ]; then
  echo "Запустите скрипт от root"
  exit 1
fi

# 1) Создаём namespace и veth (проверяем существование аккуратно)
if ! ip netns list | grep -q "$NS"; then
  ip netns add "$NS"
fi

if ! ip link show "$VETH_HOST" >/dev/null 2>&1; then
  ip link add "$VETH_HOST" type veth peer name "$VETH_NS"
  ip link set "$VETH_NS" netns "$NS"
fi

# 2) Настроить адреса и поднять интерфейсы
# Получаем чистую маску (например, 24)
MASK="${SUBNET#*/}"
ip addr replace "$HOST_IP/$MASK" dev "$VETH_HOST"
ip link set "$VETH_HOST" up

ip netns exec "$NS" ip addr replace "$NS_IP/$MASK" dev "$VETH_NS"
ip netns exec "$NS" ip link set lo up
ip netns exec "$NS" ip link set "$VETH_NS" up
ip netns exec "$NS" ip route replace default via "$HOST_IP"

# 3) Включить форвардинг на хосте
sysctl -w net.ipv4.ip_forward=1 >/dev/null

# 4) Настроить таблицу маршрутов
RT_FILE="/etc/iproute2/rt_tables"
if [ -f "$RT_FILE" ] && ! grep -q -E "^${TABLE_ID}[[:space:]]" "$RT_FILE"; then
  echo "${TABLE_ID} ${TABLE_NAME}" >> "$RT_FILE"
fi

# Накатываем маршруты и правила (replace вместо add, чтобы не было ошибок)
ip route replace default via "$EXT_GW" dev "$EXT_IF" table "$TABLE_ID"

if ! ip rule show | grep -q "from $SUBNET lookup $TABLE_ID"; then
  ip rule add from "$SUBNET" lookup "$TABLE_ID" priority 100
fi
ip route flush cache

# 5) NAT: MASQUERADE (используем проверку -C)
iptables -t nat -C POSTROUTING -s "$SUBNET" -o "$EXT_IF" -j MASQUERADE >/dev/null 2>&1 || \
  iptables -t nat -A POSTROUTING -s "$SUBNET" -o "$EXT_IF" -j MASQUERADE

# 6) FORWARD разрешения
iptables -C FORWARD -i "$VETH_HOST" -o "$EXT_IF" -j ACCEPT >/dev/null 2>&1 || \
  iptables -A FORWARD -i "$VETH_HOST" -o "$EXT_IF" -j ACCEPT

iptables -C FORWARD -i "$EXT_IF" -o "$VETH_HOST" -m state --state ESTABLISHED,RELATED -j ACCEPT >/dev/null 2>&1 || \
  iptables -A FORWARD -i "$EXT_IF" -o "$VETH_HOST" -m state --state ESTABLISHED,RELATED -j ACCEPT

echo "Сеть настроена. Для запуска игры используйте:"
echo "sudo ip netns exec $NS sudo -u имя_вашего_пользователя $GAME_CMD"

