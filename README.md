# P2P L2 VPN

Decentralized Layer 2 VPN that uses UDP hole punching to establish direct peer-to-peer connections and tunnels Ethernet frames.

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.10+**
- **Root/Admin privileges** (required to manage TAP/TUN interfaces)
- **Linux/Windows** (tap driver support)
- **Network Access**: UDP ports must be reachable (STUN is used for hole punching).

### 2. Environment Setup
Before running the application, ensure the current directory is in your `PYTHONPATH`:

```bash
export PYTHONPATH=$PYTHONPATH:.
```

### 3. Running the VPN Node

#### Option A: Using Command Line Arguments (Recommended for testing)
Start a node with a specific IP, port, and tap interface:

```bash
sudo python3 -m p2pvpn.cli.main \
    --ip 10.0.0.1 \
    --port 5555 \
    --tap tap0 \
    --prefix 24 \
    --peer 1.2.3.4:12345
```

#### Option B: Using a Configuration File
Create a `config.json` file:
```json
{
  "local_ip": "10.0.0.1",
  "listen_port": 5555,
  "tap_name": "tap0",
  "prefix": 24,
  "peers": [
    {"host": "1.2.3.4", "port": 12345}
  ]
}
```

Then run:
```bash
sudo python3 -m p2pvpn.cli.main --config config.json
```

---

## 🛠 CLI Reference

| Option | Type | Description |
| :--- | :--- | :--- |
| `--config` | FILE | Path to JSON configuration. Overrides other flags. |
| `--ip` | STRING | Virtual IP address for this node (e.g., `10.0.0.1`). |
| `--port` | INT | UDP listen port. |
| `--tap` | STRING | Name of the TAP/TUN interface (e.g., `tap0`). |
| `--prefix` | INT | Network prefix length (e.g., `24`). |
| `--peer` | STRING | Peer address in `HOST:PORT` format (can be repeated). |
| `--no-stun` | FLAG | Skip STUN discovery. |
| `--stun-server` | STRING | Custom STUN server `HOST:PORT`. |
| `--debug` | FLAG | Enable debug logging. |

---

## 🏗 Architecture

This project follows a decoupled, SOLID architecture:

- **`p2pvpn.core.engine`**: The central orchestrator. It doesn't know *how* packets are sent or *how* frames are read, only *when* to do it.
- **`p2pvpn.core.interfaces`**: Abstract base classes (`ITransport`, `INetworkInterface`) defining the contract between the Engine and external layers.
- **`p2pvpn.transport.udp`**: Concrete implementation of the UDP transport layer, including STUN hole punching logic.
- **`p2pvpn.interface.tap`**: Concrete implementation of the TAP/TUN interface layer.
- **`p2pvpn.cli`**: Modern command-line entry point for user interaction.

## 🧪 Testing

To run the full suite of unit and integration tests:

```bash
export PYTHONPATH=$PYTHONPATH:.
python3 -m unittest discover tests
```
