# T008: Implement TAP Interface

**ID**: T008
**Goal**: Implement the concrete TAP/TUN network interface layer.

**Expected Result**: A `TAPInterface` class in `p2pvpn/interface/tap/` that manages the lifecycle and I/O of a TAP/TUN device, implementing `INetworkInterface`.

**Dependencies**: T003

**Assumed Files/Components**:
- `p2pvpn/interface/tap/`
- `p2pvpn/interface/tap/tap_interface.py`
- `p2pvpn/interface/interfaces/network_interface.py`

**Acceptance Criteria**:
- Implements `INetworkInterface`.
- Manages the lifecycle of the TAP/TUN device (creation, configuration, destruction).
- Handles I/O (reading frames from the device, writing frames to it).
- Notifies the `Engine` (via the interface) when frames arrive.
- Correctly configures the interface (IP, mask, MTU) using platform-specific commands.

**Unit Tests/Verifications**:
- Unit tests in `tests/interface/tap/` using mocks for OS calls (e.g., `subprocess.run`, `os.open`).
- Verify:
    - Correct command generation for platform-specific interface configuration (Linux vs Windows).
    - Correct handling of frame I/O.
    - Error handling for permission denied or device missing.

**Out of Scope**:
- Using real TAP/TUN devices (use mocks).

**Status**: `NOT STARTED`
