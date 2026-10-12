# T009: System Integration

**ID**: T009
**Goal**: Wire all components together to form a complete, working VPN system.

**Expected Result**: A fully functional VPN node where the `Engine` is connected to the concrete `UDPTransport` and `TAPInterface`, and controlled by the `CLI`.

**Dependencies**: T006, T007, T008

**Assumed Files/Components**:
- `p2pvpn/core/engine.py`
- `p2pvpn/transport/udp/udp_transport.py`
- `p2pvpn/interface/tap/tap_interface.py`
- `p2pvpn/cli/`

**Acceptance Criteria**:
- The system starts successfully via the CLI.
- Data packets are correctly routed from the TAP interface through the Engine to the UDP transport.
- Data packets are correctly routed from the UDP transport through the Engine to the TAP interface.
- The hole-punching sequence completes, establishing a connection between peers.
- The system shuts down cleanly on `SIGINT` or `SIGTERM`.

**Unit Tests/Verifications**:
- (Note: This is primarily an integration/system test).
- Manual or scripted verification of connectivity between two nodes.
- Verify that all components are instantiated and wired according to the `architecture.md`.

**Out of Scope**:
- Developing new features.

**Status**: `NOT STARTED`
