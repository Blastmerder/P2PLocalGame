# T010: Implement CLI Config Builder

**ID**: T010
**Goal**: Implement a module to merge command-line arguments and JSON configuration into a unified configuration object.

**Expected Result**: A `cli.config_builder` module that produces a validated `VPNConfig` object.

**Dependencies**: T002

**Assumed Files/Components**:
- `p2pvpn/cli/`
- `p2pvpn/cli/config_builder.py`
- `p2pvpn/core/models/vpn_config.py`

**Acceptance Criteria**:
- Correctly merges CLI flags, arguments, and JSON configuration.
- CLI flags override JSON configuration.
- Validates the final configuration (e.g., IP address format, port ranges).
- Produces a single, immutable `VPNConfig` object used by the `Engine`.

**Unit Tests/Verifications**:
- Unit tests in `tests/cli/` to verify:
    - Merging logic (CLI vs JSON).
    - Validation of different input types (IP, port, prefix).
    - Handling of missing or invalid configuration.

**Out of Scope**:
- The actual CLI argument parsing (handled in T011).
- The actual execution of the VPN.

**Status**: `NOT STARTED`
