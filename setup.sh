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
EXT_IF="wlan0"                # внешний интерфейс (не VPN)
EXT_GW="192.168.1.1"          # шлюз внешнего интерфейса
GAME_CMD="/path/to/game"      # путь к исполняемому файлу игры/программы
# ------------------------------------------------

ID=1000
XRD="${XDG_RUNTIME_DIR:-/run/user/$ID}"

# Требуем root
if [ "$EUID" -ne 0 ]; then
  echo "Запустите скрипт от root"
  exit 1
fi

# 1) Создаём namespace и veth (если ещё нет)
ip netns add "$NS" 2>/dev/null || true
ip link add "$VETH_HOST" type veth peer name "$VETH_NS" 2>/dev/null || true
ip link set "$VETH_NS" netns "$NS" || true

# 2) Настроить адреса и поднять интерфейсы
ip addr add "${HOST_IP%/*}"/${SUBNET#*/} dev "$VETH_HOST" 2>/dev/null || true
ip link set "$VETH_HOST" up
ip netns exec "$NS" ip addr add "$NS_IP"/${SUBNET#*/} dev "$VETH_NS" 2>/dev/null || true
ip netns exec "$NS" ip link set lo up
ip netns exec "$NS" ip link set "$VETH_NS" up
ip netns exec "$NS" ip route replace default via "$HOST_IP"

# 3) Включить форвардинг на хосте
sysctl -w net.ipv4.ip_forward=1 >/dev/null

# 4) Настроить таблицу маршрутов (используем числовой ID и добавим /etc/iproute2/rt_tables)
mkdir -p /etc/iproute2
RT_FILE="/etc/iproute2/rt_tables"
if ! grep -q -E "^${TABLE_ID}[[:space:]]+${TABLE_NAME}\$" "$RT_FILE" 2>/dev/null; then
  echo "${TABLE_ID} ${TABLE_NAME}" >> "$RT_FILE"
fi
ip route add default via "$EXT_GW" dev "$EXT_IF" table "$TABLE_ID" 2>/dev/null || true
ip rule add from "${SUBNET%/*}" lookup "$TABLE_ID" priority 100 2>/dev/null || true
ip route flush cache

# 5) NAT: MASQUERADE для подсети через внешний IF (удаляем старые похожие правила)
iptables -t nat -C POSTROUTING -s "$SUBNET" -o "$EXT_IF" -j MASQUERADE 2>/dev/null || \
  iptables -t nat -A POSTROUTING -s "$SUBNET" -o "$EXT_IF" -j MASQUERADE

# 6) FORWARD разрешения между veth и внешним IF
iptables -C FORWARD -i "$VETH_HOST" -o "$EXT_IF" -j ACCEPT 2>/dev/null || \
  iptables -A FORWARD -i "$VETH_HOST" -o "$EXT_IF" -j ACCEPT
iptables -C FORWARD -i "$EXT_IF" -o "$VETH_HOST" -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
  iptables -A FORWARD -i "$EXT_IF" -o "$VETH_HOST" -m state --state ESTABLISHED,RELATED -j ACCEPT

# 7) Подготовка Pulse/pipewire сокетов и /dev/snd биндов (для звука)
if [ ! -S "$XRD/pulse/native" ] && [ ! -S "$XRD/pipewire-0" ]; then
  echo "Не найден пул сокетов в $XRD (pulse/native или pipewire-0). Проверьте XDG_RUNTIME_DIR."
fi

mkdir -p /var/tmp/nsbind/$ID
mount --bind "$XRD/pulse/native" /var/tmp/nsbind/$ID/pulse-native 2>/dev/null || true
mount --bind /dev/snd /var/tmp/nsbind/$ID/dev-snd 2>/dev/null || true
# (если у вас pipewire, пробиндуйте соответствующие файлы аналогично)

# 8) Запуск приложения внутри namespace с пробросом окружения и монтами
ip netns exec "$NS" bash -c "
  export XDG_RUNTIME_DIR='$XRD'
  mkdir -p \"\$XDG_RUNTIME_DIR\"/pulse
  mount --bind /var/tmp/nsbind/$ID/pulse-native \"\$XDG_RUNTIME_DIR\"/pulse/native 2>/dev/null || true
  mkdir -p /dev/snd
  mount --bind /var/tmp/nsbind/$ID/dev-snd /dev/snd 2>/dev/null || true
  export PULSE_SERVER=unix:\$XDG_RUNTIME_DIR/pulse/native
  export DISPLAY=$DISPLAY
  export XAUTHORITY=${XAUTHORITY:-/home/$(logname)/.Xauthority}
"
# ip netns exec "$NS" bash -c "exec $GAME_CMD"

# 9) Очистка временных биндов (по желанию)
# umount /var/tmp/nsbind/$UID/pulse-native || true
# umount /var/tmp/nsbind/$UID/dev-snd || true
