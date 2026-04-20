# P2P L2 VPN

Минималистичный peer-to-peer VPN уровня L2 (Ethernet) на чистом Python 3.
Создаёт виртуальный TAP-интерфейс и туннелирует сырые Ethernet-фреймы по UDP между участниками.

## Как это работает

```
  Игра → tap0 (виртуальная сетевая карта) → VPN-процесс → UDP → интернет → VPN-процесс → tap0 → Игра
```

- Используется **TAP** (не TUN): туннелируются Ethernet-фреймы (L2), поэтому broadcast, ARP и обнаружение по сети работают «из коробки».
- Каждый узел слушает UDP-порт и пересылает фреймы всем известным пирам (**broadcast на уровне приложения**).
- Новые участники обнаруживаются автоматически (peer discovery через HELLO-пакеты).
- Мёртвые пиры (нет пакетов > 15 сек) удаляются из таблицы.

## Требования

- Linux (нужен `/dev/net/tun`)
- Python 3.10+
- Root-права (для создания TAP-интерфейса)
- Открытый UDP-порт (по умолчанию 5555) на файрволе

## Установка на ArchLinux

```bash
# Всё что нужно — уже в base (python, iproute2, iptables/nftables).
# Дополнительно для тестирования broadcast / проверки связи:
sudo pacman -S --needed python iproute2 iptables nmap

# Модуль tun обычно уже загружен, на всякий случай:
sudo modprobe tun
ls /dev/net/tun   # должен существовать

# Клонируем и запускаем (root нужен для TAP + iptables):
git clone <repo> p2pvpn && cd p2pvpn
sudo python3 main.py --ip 10.0.0.1 --port 5555 --peer <peer_ip>:5555
```

Если используется firewalld вместо iptables — см. раздел «Файрвол» ниже.
`nmap` даёт команду `ncat`, используемую в примерах проверки broadcast.

## Быстрый старт (2 участника)

### Участник A (публичный IP: 1.2.3.4)

```bash
sudo python3 main.py --ip 10.0.0.1 --port 5555 --peer 5.6.7.8:5555
```

### Участник B (публичный IP: 5.6.7.8)

```bash
sudo python3 main.py --ip 10.0.0.2 --port 5555 --peer 1.2.3.4:5555
```

### Проверка связи

```bash
ping 10.0.0.2        # A пингует B
ping 10.0.0.1        # B пингует A
```

### Проверка broadcast через ncat

Поскольку туннель работает на уровне L2, broadcast-фреймы Ethernet
(`ff:ff:ff:ff:ff:ff`) и IPv4-broadcast (`10.0.0.255`) прозрачно доходят
до всех пиров — как в обычном LAN.

**Unicast (точка-точка)**

```bash
# на B — слушаем UDP 4444:
ncat -u -l -p 4444

# на A — подключаемся по VPN-адресу B:
ncat -u 10.0.0.2 4444
# всё что набираешь на A, появляется у B
```

**Broadcast (всем сразу)**

```bash
# на B (и на всех остальных участниках) — слушаем broadcast:
ncat -u -l -p 4444 --broadcast

# на A — отправляем на subnet-broadcast:
ncat -u --broadcast 10.0.0.255 4444
# сообщение получат все участники, которые слушают 4444/udp
```

**TCP между клиентами (для игр / ncat chat)**

```bash
# B — TCP-listener:
ncat -l -p 5000

# A — TCP-клиент по VPN:
ncat 10.0.0.2 5000
```

**ARP / обнаружение соседей**

```bash
# с любого узла:
arping -I tap0 10.0.0.2       # увидим MAC пира
ip neigh show dev tap0        # ARP-кэш VPN-интерфейса
```

## Через JSON-конфиг

Отредактируй `node_a.json` / `node_b.json`, замени `PEER_X_PUBLIC_IP` на реальные адреса:

```bash
sudo python3 main.py --config node_a.json
```

## N участников

Просто добавляй `--peer` несколько раз или список в JSON:

```bash
sudo python3 main.py --ip 10.0.0.3 --port 5555 \
  --peer 1.2.3.4:5555 \
  --peer 5.6.7.8:5555 \
  --peer 9.10.11.12:5555
```

```json
{
  "local_ip": "10.0.0.3",
  "listen_port": 5555,
  "tap_name": "tap0",
  "peers": [
    { "host": "1.2.3.4",    "port": 5555 },
    { "host": "5.6.7.8",    "port": 5555 },
    { "host": "9.10.11.12", "port": 5555 }
  ]
}
```

## Файрвол (firewalld / iptables / nftables)

```bash
# iptables (ArchLinux по умолчанию)
sudo iptables -I INPUT -p udp --dport 5555 -j ACCEPT

# nftables
sudo nft add rule inet filter input udp dport 5555 accept

# firewalld
sudo firewall-cmd --add-port=5555/udp --permanent
sudo firewall-cmd --reload
```

Для ncat-тестов broadcast (порт 4444) — открой его на обеих машинах
**на интерфейсе tap0**, а не на физическом:

```bash
sudo iptables -I INPUT -i tap0 -p udp --dport 4444 -j ACCEPT
sudo iptables -I INPUT -i tap0 -p tcp --dport 5000 -j ACCEPT
```

## Формат пакета

```
[ MAGIC (5 байт) | TYPE (1 байт) | PAYLOAD ]

TYPE = 0x01  DATA   — сырой Ethernet-фрейм
TYPE = 0x02  HELLO  — keepalive / анонс присутствия
```

## Структура кода

```
p2pvpn/
├── main.py       — CLI и точка входа
├── vpn_node.py   — вся логика VPN (TAP, UDP, peer table)
├── node_a.json   — пример конфига для участника A
└── node_b.json   — пример конфига для участника B
```

## Известные ограничения и что можно улучшить

| Что | Как расширить |
|-----|---------------|
| Нет шифрования | Добавить `cryptography` (Fernet/AES-GCM) |
| Нет аутентификации | Pre-shared key или WireGuard-подобный handshake |
| Broadcast → всем | Учитывать destination MAC для unicast/multicast |
| UDP может теряться | Для надёжности добавить ACK для критичных пакетов |
| Нет NAT-traversal | Уже работает через STUN + UDP hole punching (см. `stun_client.py`) |

## Диагностика

```bash
# Видно ли VPN-интерфейс:
ip addr show tap0

# Идёт ли трафик через TAP:
sudo tcpdump -i tap0 -n

# Идёт ли VPN-трафик по UDP наружу:
sudo tcpdump -i any -n udp port 5555

# Статистика пиров — смотри лог процесса main.py,
# каждые 5 секунд печатается таблица alive/pending/dead.
```
# P2PLocalGame
