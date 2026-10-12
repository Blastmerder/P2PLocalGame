# T002: Implement Core Models

**ID**: T002
**Goal**: Implement the data classes and models required for the core VPN logic.

**Expected Result**: A set of Python `dataclasses` in `p2pvpn/core/models/` representing the domain entities.

**Dependencies**: T001

**Assumed Files/Components**:
- `p2pvpn/core/models/peer.py`
- `p2pvpn/core/models/packet_type.py`
- `p2pvpn/core/models/vpn_config.py`

**Acceptance Criteria**:
- `Peer` class supports state and lifecycle tracking.
- `PacketType` enum correctly defines all protocol packet types.
- `VPNConfig` class can be instantiated from a dictionary or configuration object.
- Models use type hinting appropriately.

**Unit Tests/Verifications**:
- Unit tests in `tests/core/models/` to verify:
    - Peer state transitions.
    - Packet type definitions.
    - Configuration object creation.

**Out of Scope**:
- Model persistence (DB).
- Logic for managing peers (moved to `PeerManager`).

**Status**: `NOT STARTED`
