# T003: Implement Core Interfaces

**ID**: T003
**Goal**: Define the abstract base classes for Transport and Network Interfaces.

**Expected Result**: Abstract base classes in `p2pvpn/core/interfaces/` that decouple the engine from implementation details.

**Dependencies**: T001, T002

**Assumed Files/Components**:
- `p2pvpn/core/interfaces/transport.py` (defining `ITransport`)
- `p2pvpn/core/interfaces/network_interface.py` (defining `INetworkInterface`)

**Acceptance Criteria**:
- `ITransport` defines methods for `send` and event hooks for `packet_received`.
- `INetworkInterface` defines methods for `write` and event hooks for `frame_received`.
- Interfaces are defined using `abc.ABC`.
- Interfaces use type hints from `core.models`.

**Unit Tests/Verifications**:
- Tests to ensure classes can be instantiated as ABCs (abstract classes) and cannot be instantiated directly.
- Verify that implementation of these interfaces can be easily mocked.

**Out of Scope**:
- Concrete implementations (UDP, TAP).

**Status**: `NOT STARTED`
