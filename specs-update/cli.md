# CLI Specification

## 1. Overview
The goal is to transform the current monolithic `main.py` into a clean, extensible, and user-friendly Command-Line Interface (CLI). The CLI should act as a thin entry point that parses user input, builds a configuration, and delegates the actual execution to the `core.engine`.

## 2. Requirements

### 2.1. User Experience (UX)
- **Purpose-driven Help**: Clear, concise help messages using `--help`.
- **Visual Feedback**: Informative banners and status updates during initialization (e.g., STUN discovery, TAP setup).
- **Error Handling**: Graceful error messages for invalid arguments, missing privileges, or configuration errors, with appropriate exit codes.
- **Verbosity Control**: A `--debug` flag to enable detailed logging.

### 2.2. Command Structure
The CLI will follow a single-command pattern for now, with future support for subcommands (e.g., `p2pvpn run`, `p2pvpn status`).

**Primary Command**: `run` (implicit as the default action)

**Arguments & Options**:
| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--config` | FILE | None | Path to a JSON configuration file. Overrides all other flags. |
| `--ip` | STRING | `10.0.0.1` | Virtual IP address for this node. |
| `--port` | INT | `5555` | UDP listen port. |
| `--tap` | STRING | `tap0` | Name of the TAP/TUN interface. |
| `--prefix` | INT | `24` | Network prefix length. |
| `--peer` | STRING | None | Peer public address in `HOST:PORT` format. Can be repeated. |
| `--no-stun` | Flag | False | Skip STUN discovery. |
| `--stun-server`| STRING | None | Custom STUN server in `HOST:PORT` format. Can be repeated. |
| `--stun-timeout`| FLOAT | `3.0` | Timeout for STUN discovery in seconds. |
| `--debug` | Flag | False | Enable debug-level logging. |

### 2.3. Implementation Details

- **Library Choice**: `argparse` (Standard Library) is selected for the initial implementation due to its zero-dependency nature and sufficient capabilities for this scope. If complexity grows (e.g., complex subcommands), migration to `click` or `typer` will be considered.
- **Configuration Building**: A dedicated `cli.config_builder` module will be responsible for merging command-line arguments and JSON configuration into a unified object (e.g., a `dataclass` or a validated dictionary).
- **Privilege Check**: The CLI will perform a pre-flight check for administrative/root privileges before any initialization begins.
- **Graceful Shutdown**: The CLI will register signal handlers (`SIGINT`, `SIGTERM`) to ensure the `core.engine` and all associated resources (TAP, sockets) are shut down cleanly.

## 3. Testability

To ensure the CLI is well-tested without launching a real VPN node:

- **Argument Parsing Tests**: Unit tests for the configuration builder that verify different combinations of CLI flags and JSON files produce the correct configuration object.
- **Command Handlers**: Test the mapping of CLI arguments to the initialization parameters of the `core.engine`.
- **Mocking the Engine**: Use mocks to simulate the engine's execution and verify that the CLI correctly handles both successful starts and engine-level exceptions.
- **Mocking System Calls**: Test privilege checks and OS-specific signal handling by mocking `sys.platform` and `os.geteuid`.
