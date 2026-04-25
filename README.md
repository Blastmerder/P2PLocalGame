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

- **Linux** (нужен `/dev/net/tun`) или **Windows 10/11** (TAP-Windows6)
- Python 3.10+
- Root / Administrator (для создания TAP-интерфейса)
- Открытый UDP-порт (по умолчанию 5555) на файрволе

## Установка на ArchLinux

```bash
# Всё что нужно — уже в base (python, iproute2, iptables/nftables).
# Дополнительно для тестирования broadcast / проверки связи:
sudo pacman -S --needed python iproute2 iptables ethtool nmap

# Модуль tun обычно уже загружен, на всякий случай:
sudo modprobe tun
ls /dev/net/tun   # должен существовать

# Клонируем и запускаем (root нужен для TAP + iptables):
git clone <repo> p2pvpn && cd p2pvpn
sudo python3 main.py --ip 10.0.0.1 --port 5555 --peer <peer_ip>:5555
```

Если используется firewalld вместо iptables — см. раздел «Файрвол» ниже.
`nmap` даёт команду `ncat`, используемую в примерах проверки broadcast.

## Установка на Windows

Все шаги (драйвер-проверка, создание TAP-адаптера, pywin32, firewall,
запуск) автоматизированы в `windows-run.bat`.

**Одноразово**: поставить драйвер TAP-Windows6 — он идёт с
[OpenVPN Community](https://openvpn.net/community-downloads/) или
[WireGuard for Windows](https://www.wireguard.com/install/),
любой из двух подойдёт. Python 3.10+ должен быть в `PATH`.

**Запуск** (двойной клик / cmd / PowerShell):

```bat
windows-run.bat --ip 10.0.0.1 --port 5555 --peer 94.180.149.23:5555
```

Что делает скрипт:

1. Перезапускается от Администратора (UAC-промпт).
2. `pip install pywin32` — если ещё не стоит.
3. Ищет `tapctl.exe` в `%ProgramFiles%\OpenVPN\bin` / `\WireGuard`.
4. Создаёт TAP-адаптер `tap0` через `tapctl create --hwid tap0901`,
   если его ещё нет.
5. Добавляет правило брандмауэра «P2P L2 VPN» — UDP 5555 inbound
   (идемпотентно, не дублирует).
6. Запускает `python main.py` с теми аргументами, что ты передал bat-у.

Все шаги после первого запуска кешируются — дальше bat просто стартует
VPN.

### Если всё-таки хочется руками

```powershell
# PowerShell от имени Администратора:
& "C:\Program Files\OpenVPN\bin\tapctl.exe" create --name tap0 --hwid tap0901
python -m pip install pywin32
New-NetFirewallRule -DisplayName "P2P L2 VPN" -Direction Inbound `
    -Protocol UDP -LocalPort 5555 -Action Allow
python main.py --ip 10.0.0.1 --port 5555 --peer <peer_pub_ip>:5555 --tap tap0
```

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
├── main.py            — CLI и точка входа
├── vpn_node.py        — логика VPN (UDP, peer table, hole punching)
├── tap.py             — кросс-платформенный TAP: Linux (/dev/net/tun)
│                        и Windows (TAP-Windows6 через pywin32)
├── stun_client.py     — STUN-клиент для определения публичного адреса
├── windows-run.bat    — установка и запуск на Windows одной командой
├── node_a.json        — пример конфига для участника A
└── node_b.json        — пример конфига для участника B
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

# Проверить что segmentation offload реально выключен:
ethtool -k tap0 | grep -E 'tcp-seg|gen-seg|gen-rec|large-rec'
# всё должно быть: off [fixed] или off

# Проверить что MSS-правила висят:
sudo iptables -t mangle -L OUTPUT -v -n | grep tap0
sudo iptables -t mangle -L INPUT  -v -n | grep tap0

# Статистика пиров — смотри лог процесса main.py,
# каждые 5 секунд печатается таблица alive/pending/dead.
```

### «Ping проходит, а всё остальное падает» — что проверить

Почти всегда это MTU/offload. Код должен это отключать автоматически,
но если нет ethtool или iptables, фикс не применится. Проверь вручную:

```bash
# 1) Отключить offload на TAP:
sudo ethtool -K tap0 tso off gso off gro off lro off tx off sg off

# 2) Зажать MSS (MTU tap0 - 40):
sudo iptables -t mangle -A OUTPUT -o tap0 -p tcp --tcp-flags SYN,RST SYN \
     -j TCPMSS --set-mss 1380
sudo iptables -t mangle -A INPUT  -i tap0 -p tcp --tcp-flags SYN,RST SYN \
     -j TCPMSS --set-mss 1380

# 3) Проверить реальный рабочий размер через ping с DF-битом:
ping -M do -s 1392 10.0.0.2   # должен пройти (1392+8 ICMP+20 IP = 1420 MTU)
ping -M do -s 1393 10.0.0.2   # должен "Message too long" — ок, это предел
```
# P2PLocalGame
