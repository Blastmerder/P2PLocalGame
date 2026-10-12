# T012: Final Cleanup

**ID**: T012
**Goal**: Remove all legacy, deprecated, and shim code from the project.

**Expected Result**: A clean codebase containing only the new `p2pvpn` package and necessary setup/helper scripts.

**Dependencies**: T009, T011

**Assumed Files/Components**:
- `vpn_node.py` (legacy)
- `UDP_Protocol.py` (legacy)
- `stun_client.py` (legacy)
- `tap.py` (legacy)
- `main.py` (legacy)
- `p2pvpn/` (new)
- `specs-update/` (documentation)

**Acceptance Criteria**:
- All legacy files listed above are removed from the repository.
- The project runs correctly using only the new `p2pvpn/` package.
- The entry point is the new CLI.
- Documentation is updated to reflect the new structure.

**Unit Tests/Verifications**:
- Final system verification (manual or automated).
- Verify that no imports from legacy files exist in the new codebase.

**Out of Scope**:
- Any further feature development.

**Status**: `NOT STARTED`
