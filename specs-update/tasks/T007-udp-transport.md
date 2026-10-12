# T007: Implement UDP Transport

**ID**: T007
**Goal**: Implement the concrete UDP transport layer.

**Expected Result**: A `UDPTransport` class in `p2pvpn/transport/udp/` that manages UDP sockets, STUN discovery, and packet encoding/decoding, implementing `ITransport`.

**Dependencies**: T003

**Assumed Files/Components**:
- `p2pvpn/transport/udp/`
- `p2pvpn/transport/udp/udp_transport.py`
- `p2pvpn/transport/interfaces/transport.py`
- `p2pvpn/core/models/packet_type.py`

**Acceptance Criteria**:
- Implements `ITransport`.
- Handles UDP socket lifecycle (open, listen, close).
- Implements STUN-based hole punching logic (sending/receiving `HELLO` packets).
- Correctly encodes/decodes packets with `MAGIC` and `TYPE_DATA` headers.
- Notifies the `Engine` (via the interface) when packets arrive.

**Unit Tests/Verifications**:
- Unit tests in `tests/transport/udp/` using mocks for `asyncio.DatagramTransport`.
- Verify:
    - Packet encoding/decoding accuracy.
    - STUN packet parsing (`_parse_response`).
    - Hole-punching protocol-level logic (construction of packets).
    - Error handling for malformed/truncated packets.

**Out of Scope**:
- Using real network sockets (use mocks).

**Status**: `NOT STARTED`
