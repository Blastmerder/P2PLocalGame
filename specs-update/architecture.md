# Target Architecture Specification

## 1. Overview
The target architecture aims to decouple the core VPN domain logic from its two primary external dependencies: the network transport layer (UDP) and the network interface layer (TAP/TUN). This decoupling is achieved through the use of abstract interfaces, enabling easier testing and potential future expansion (e.g., to QUIC or other tunnel types).

## 2. Package Structure

```text
p2pvpn/
├── cli/                # CLI entry points and command parsing
├── core/               # Domain logic (The "Brain")
│   ├── models/         # Data classes (e.g., Peer, PacketType)
│   ├── interfaces/     # Abstract Base Classes (ABCs) for Transport and Interface
│   └── engine.py       # The central orchestrator (replaces monolithic VPNNode)
├── transport/          # Network transport implementations
│   ├── udp/            # UDP-specific logic (replaces UDPProtocol and STUN logic)
│   └── interfaces/     # Transport-related ABCs
├── interface/          # Network interface implementations
│   ├── tap/            # TAP/TUN device logic (replaces tap.py)
│   └── interfaces/     # Interface-related ABCs
└── utils/              # Common helpers (e.g., encoding, logging)
```

## 3. Component Responsibilities

### 3.1. Core Engine (`core/engine.py`)
**Responsibility**: Orchestrates the high-level workflow. It receives events from the `Transport` and `Interface` and applies business rules.
- **Inputs**: Events from `ITransport` (e.g., `on_packet_received`) and `INetworkInterface` (e.g., `on_frame_received`).
- **Outputs**: Commands to `ITransport` (e.g., `send_packet`) and `INetworkInterface` (e.g., `write_frame`).
- **Dependencies**: `core.models`, `core.interfaces`.
- **SOLID Principle**: **Single Responsibility Principle (SRP)**. It only manages the *logic* of the VPN, not the *mechanics* of how bits move over the wire.

### 3.2. Transport Layer (`transport/udp/`)
**Responsibility**: Manages the low-level UDP socket, STUN discovery, hole punching, and the encoding/decoding of protocol packets.
- **Inputs**: High-level commands from the Engine (e.g., `send(peer_addr, data)`).
- **Outputs**: Notified events to the Engine (e.g., `packet_arrived(addr, data)`).
- **Dependencies**: `transport.interfaces`, `core.models`.
- **SOLID Principle**: **Dependency Inversion Principle (DIP)**. The Engine depends on the `ITransport` abstraction, not the concrete `UDPTransport`.

### 3.3. Network Interface Layer (`interface/tap/`)
**Responsibility**: Manages the lifecycle and I/O of the TAP/TUN device.
- **Inputs**: High-level commands from the Engine (e.g., `write(frame)`).
- **Outputs**: Notified events to the Engine (e.g., `frame_arrived(frame)`).
- **Dependencies**: `interface.interfaces`.
- **SOLID Principle**: **Interface Segregation Principle (ISP)**. The Engine only sees the `INetworkInterface` methods it needs.

### 3.4. Peer Management (`core/models/peer.py`)
**Responsibility**: Maintains the state and lifecycle transitions of remote nodes.
- **Dependencies**: `core.models`.

## 4. Dependency Flow
All dependencies flow **inward** towards the `core` package.
- `cli` $\to$ `core`
- `transport` $\to$ `core.interfaces`
- `interface` $\to$ `core.interfaces`
- `core` $\to$ `core.models`

**Rule**: No component in `core` should ever import from `transport`, `interface`, or `cli`.

## 5. Implementation Notes & Assumptions
- **Assumption**: The `UDPProtocol` as currently implemented is a thin wrapper. In the new architecture, it will be absorbed into a more robust `UDPTransport` class.
- **Preliminary Decision**: We will use `asyncio` as the primary concurrency model across all layers.
- **Pre-emptive Solution**: To avoid circular dependencies during the transition, we will first define all interfaces in `core.interfaces`.
