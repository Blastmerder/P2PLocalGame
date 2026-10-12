# T005: Implement Core Engine

**ID**: T005
**Goal**: Implement the central orchestrator that manages the VPN logic.

**Expected Result**: A `Engine` class in `p2pvpn/core/engine.py` that coordinates between `ITransport` and `INetworkInterface`.

**Dependencies**: T002, T003, T004

**Assumed Files/Components**:
- `p2pvpn/core/engine.py`
- `p2pvpn/core/interfaces/transport.py`
- `p2pvpn/core/interfaces/network_interface.py`
- `p2pvpn/core/models/peer.py`
- `p2pvpn/core/peer_manager.py`

**Acceptance Criteria**:
- Correctly routes incoming packets from `ITransport` to `INetworkInterface`.
- Correctly routes incoming frames from `INetworkInterface` to `ITransport`.
- Orchestrates the hole-punching sequence via `ITransport`.
- Updates peer states via `PeerManager` upon receiving packets.
- Responds to errors from transport or interface layers.

**Unit Tests/Verifications**:
- Extensive unit tests in `tests/core/` using mocks for `ITransport` and `INetworkInterface`.
- Verify:
    - Packet $\to$ Frame routing.
    - Frame $\to$ Packet routing.
    - Hole-punching workflow (sending `HELLO` packets).
    - Handling of packet/frame arrival events.
    - Handling of transport/interface errors.

**Out of Scope**:
- Concrete UDP or TAP implementations.
- Actual network connectivity.

**Status**: `NOT STARTED`
