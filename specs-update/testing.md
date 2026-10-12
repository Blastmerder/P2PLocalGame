# Unit Testing Strategy Specification

## 1. Overview
The testing strategy focuses exclusively on **unit tests**. The goal is to verify the correctness of individual components in isolation, ensuring that the core domain logic is robust and decoupled from the underlying operating system and network hardware.

## 2. General Principles

- **Behavior over Implementation**: Tests should verify that a component behaves correctly according to its specification (e.g., "when a packet arrives, the peer state is updated") rather than testing its internal private state.
- **Isolation**: Each test must run in isolation. No component should depend on a real network socket, a real TAP device, or a real filesystem.
- **No Integration Tests**: This specification intentionally excludes integration tests (e.g., running two real nodes) and tests involving real databases or external services.
- **Fast Feedback**: Unit tests must be extremely fast, enabling them to be run frequently during development.

## 3. Testing Approach by Layer

### 3.1. Core Domain Layer (`core/`)
**Goal**: Verify the "brain" of the VPN system.

- **Mocking Strategy**: 
    - Use `unittest.mock` (or `pytest-mock`) to provide mock implementations of `ITransport` and `INetworkInterface`.
    - The `Engine` should be tested by injecting these mocks and asserting that the correct methods are called in response to simulated events.
- **Key Scenarios to Test**:
    - **Packet Routing**: Given a packet from `ITransport`, verify the `Engine` calls `INetworkInterface.write()`.
    - **Peer Lifecycle**: Verify that a peer transitions from `pending` $\to$ `alive` $\to$ `dead` based on simulated timestamps and packet arrival events.
    - **Hole Punching Logic**: Verify that the `Engine` triggers the correct sequence of `send` commands to the `ITransport` during the hole-punching phase.
    - **Error Resilience**: Verify how the `Engine` reacts when the `Transport` or `Interface` raises an exception (e.g., `ConnectionError`).

### 3.2. Transport Layer (`transport/`)
**Goal**: Verify packet encapsulation and protocol-specific logic.

- **Mocking Strategy**: 
    - Since real sockets are prohibited, the low-level `asyncio.DatagramTransport` will be mocked.
- **Key Scenarios to Test**:
    - **Encapsulation**: Verify that a raw Ethernet frame is correctly wrapped with the `MAGIC` and `TYPE_DATA` headers before being passed to the transport.
    - **Decapsulation (Decoding)**: Verify that a raw UDP datagram with valid/invalid headers is correctly parsed into a payload and type.
    - **STUN Logic**: Test the STUN packet parsing logic (`_parse_response`) using pre-constructed byte arrays representing valid and malformed STUN responses.
    - **Hole Punching (Protocol level)**: Verify the correct construction of `HELLO` packets.

### 3.3. Interface Layer (`interface/`)
**Goal**: Verify the logic of platform-specific configuration and I/O management.

- **Mocking Strategy**: 
    - Mock the underlying OS calls (e.g., `os.open`, `os.write`, `subprocess.run`, `win32file.CreateFile`).
    - **Note**: Since we are testing the *logic* of how the interface is managed, we mock the *tools* used to manage it.
- **Key Scenarios to Test**:
    - **Configuration Generation**: Verify that the correct `ip`, `mtu`, and `mask` are passed to the underlying OS configuration commands.
    - **Linux/Windows Specifics**: Verify that the correct platform-specific commands (e.g., `ip link` vs `netsh`) are prepared.

## 4. Test Coverage Criteria

- **High Coverage of Branching Logic**: Every `if/else` in the domain and protocol layers must be exercised.
- **Boundary Conditions**: Test with minimum/maximum MTU sizes, empty payloads, and malformed/truncated packets.
- **Error States**: Explicitly test how the system handles:
    - Incorrectly formatted packets.
    - Timeouts.
    - Permission denied errors during setup.
    - Disconnected/aborted transports.

## 5. Tools and Environment
- **Framework**: `pytest` (highly recommended for its fixture system and powerful mocking capabilities).
- **Mocking**: `unittest.mock`.
- **Assertions**: Standard `assert` statements within `pytest`.
