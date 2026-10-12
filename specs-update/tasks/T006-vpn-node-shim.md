# T006: Implement VPNNode Shim

**ID**: T006
**Goal**: Create a compatibility layer that allows the old `VPNNode` logic to run using the new `Engine` and interfaces.

**Expected Result**: The existing `vpn_node.py` (or similar) is refactored to act as a shim that implements the new `ITransport` and `INetworkInterface` interfaces and delegates its core logic to the `Engine`.

**Dependencies**: T003, T005

**Assumed Files/Components**:
- `vpn_node.py` (existing)
- `p2pvpn/core/engine.py`
- `p2pvpn/core/interfaces/transport.py`
- `p2pvpn/core/interfaces/network_interface.py`

**Acceptance Criteria**:
- The `VPNNode` class implements the new `ITransport` and `INetworkInterface` interfaces.
- The core logic of `VPNNode` is moved into `Engine`.
- `VPNNode` instantiates and uses the `Engine`.
- The system can still be started using the "old" way (as long as the shim is in place).

**Unit Tests/Verifications**:
- Verify that `VPNNode` correctly translates interface-specific calls into `Engine` commands.
- Run existing integration tests (if any) to ensure the shim maintains core functionality.

**Out of Scope**:
- Complete removal of legacy code (this is Phase 4).

**Status**: `NOT STARTED`
