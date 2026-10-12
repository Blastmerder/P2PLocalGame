# T011: Implement CLI Entry Point

**ID**: T011
**Goal**: Implement the main entry point for the CLI using `argparse`.

**Expected Result**: A clean, user-friendly command-line interface in `p2pvpn/cli/` that parses user input and delegates execution to the `Engine`.

**Dependencies**: T002, T010

**Assumed Files/Components**:
- `p2pvpn/cli/`
- `p2pvpn/cli/main.py`
- `p2pvpn/cli/config_builder.py`
- `p2pvpn/core/engine.py`

**Acceptance Criteria**:
- Implements the command-line options specified in `specs-update/cli.md`.
- Parses arguments using `argparse`.
- Uses the `ConfigBuilder` to create a `VPNConfig`.
- Instantiates the `Engine` with the provided configuration.
- Handles `SIGINT` and `SIGTERM` for graceful shutdown.
- Provides clear `--help` messages.
- Performs a pre-flight check for root/admin privileges.

**Unit Tests/Verifications**:
- Unit tests in `tests/cli/` using mocks for:
    - `argparse` parsing (verifying mapping to config).
    - `Engine` execution (verifying engine is called with correct config).
    - Privilege checks.
    - Signal handling.

**Out of Scope**:
- The actual logic of the VPN (handled in `core/`).

**Status**: `NOT STARTED`
