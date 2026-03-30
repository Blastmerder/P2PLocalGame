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

## Файрвол (firewalld / iptables)

```bash
# iptables
sudo iptables -I INPUT -p udp --dport 5555 -j ACCEPT

# firewalld
sudo firewall-cmd --add-port=5555/udp --permanent
sudo firewall-cmd --reload
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
| Нет NAT-traversal | Добавить UDP hole punching через bootstrap-сервер |
# P2PLocalGame
