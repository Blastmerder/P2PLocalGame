# T004: Implement Peer Manager

**ID**: T004
**Goal**: Create a component to manage the lifecycle and state of remote peers.

**Expected Result**: A `PeerManager` class in `p2pvpn/core/models/` (or a separate `p2pvpn/core/peer_manager.py` if preferred by architecture) that handles peer registration, state updates, and timeouts.

**Dependencies**: T002

**Assumed Files/Components**:
- `p2pvpn/core/models/peer.py`
- `p2pvpn/core/peer_manager.py`

**Acceptance Criteria**:
- Can add, remove, and update peers.
- Correctly handles peer state transitions (e.g., `pending` -> `alive` -> `dead`).
- Provides a way to query active peers.
- Handles timeouts for inactive peers (when triggered by the Engine).

**Unit Tests/Verifications**:
- Unit tests in `tests/core/` to verify:
    - Peer addition and removal.
    - State transitions based on simulated activity.
    - Peer expiration/timeout logic.

**Out of Scope**:
- Network communication (handled by `ITransport`).
- Hard connection/disconnection logic (handled by `Engine`).

**Status**: `NOT STARTED`
