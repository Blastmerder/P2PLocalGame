# T001: Setup Directory Structure

**ID**: T001
**Goal**: Create the new package structure as defined in `specs-update/architecture.md`.

**Expected Result**: A set of empty `__init__.py` files and directories mirroring the target architecture.

**Dependencies**: None

**Assumed Files/Components**:
- `p2pvpn/` (root package)
- `p2pvpn/cli/`
- `p2pvpn/core/`
- `p2pvpn/core/models/`
- `p2pvpn/core/interfaces/`
- `p2pvpn/transport/`
- `p2pvpn/transport/udp/`
- `p2pvpn/transport/interfaces/`
- `p2pvpn/interface/`
- `p2pvpn/interface/tap/`
- `p2pvpn/interface/interfaces/`
- `p2pvpn/utils/`

**Acceptance Criteria**:
- All specified directories exist.
- Each directory contains an `__init__.py` file.
- The directory structure matches `architecture.md`.

**Unit Tests/Verifications**:
- Verify directory existence using `ls` or `pytest` filesystem checks.

**Out of Scope**:
- Implementing any logic.
- Moving existing files.

**Status**: `NOT STARTED`
