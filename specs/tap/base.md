# TAP Interface Abstraction (`_TAPBase`)
Defines the unified interface for cross-platform TAP device operations.

## Core Responsibilities
- **Parameter Initialization**: Stores `name`, `ip`, `prefix`, and `mtu`.
- **Lifecycle Hooks**:
    - `setup()`: Abstract method to initialize hardware/driver.
    - `teardown()`: Abstract method to clean up resources.
- **Data Flow**:
    - `write(frame: bytes)`: Abstract method to send raw Ethernet frames.
    - `start_reading(loop, on_frame)`: Abstract method to start asynchronous frame reception.
