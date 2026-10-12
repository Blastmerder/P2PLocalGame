# Migration Plan Specification

## 1. Overview
This plan outlines a phased, safe transition from the current monolithic structure to the new decoupled, SOLID-based architecture. Each phase is designed to be independently verifiable via unit tests, ensuring that the core functionality remains intact throughout the process.

## 2. Phased Approach

### Phase 1: Interface Definition & Core Models
**Goal**: Establish the new architectural foundation without changing existing implementations.

- **Tasks**:
    - Define `core.interfaces` (e.g., `ITransport`, `INetworkInterface`).
    - Define `core.models` (e.g., `Peer`, `PacketType`, `VPNConfig`).
    - Establish the new directory structure.
- **Expected Result**: A set of abstract classes and data models that the rest of the system will eventually implement.
- **Verification**: Ensure the new models and interfaces can be imported without errors and that they accurately reflect the current system's needs.

### Phase 2: Extraction of Domain Logic (The "Brain")
**Goal**: Move the core VPN business logic from `VPNNode` into the new `core.engine`.

- **Tasks**:
    - Create `core.engine.Engine`.
    - Refactor the current `VPNNode` logic into the `Engine`, but keep `VPNNode` as a "compatibility shim" that implements the new `ITransport` and `INetworkInterface` interfaces.
    - Move peer management logic from `VPNNode` to `core.models.peer_manager`.
- **Expected Result**: The core logic is now testable in isolation using mocks for transport and interface.
- **Verification**: 
    - Write unit tests for the new `Engine` using mocks.
    - Run existing functionality to ensure the "shim" still works.

### Phase 3: Component Decoupling (Transport & Interface)
**Goal**: Replace the compatibility shims with concrete, decoupled implementations.

- **Tasks**:
    - Implement `transport/udp/` (moving logic from `UDPProtocol` and `stun_client.py` into a dedicated transport class).
    - Implement `interface/tap/` (moving logic from `tap.py` into the new interface package).
    - Update `main.py` to instantiate the new components and wire them together through the `Engine`.
- **Expected Result**: The system is fully decoupled. The `Engine` no longer knows about `UDP` or `TAP` specifics.
- **Verification**: 
    - Comprehensive unit testing of the new `UDPTransport` and `TAPInterface` implementations.
    - Full system execution (manual or integration testing) to confirm connectivity.

### Phase 4: CLI Modernization & Cleanup
**Goal**: Finalize the project structure and provide a professional CLI.

- **Tasks**:
    - Implement the new `cli/` package.
    - Replace the monolithic `main.py` with the new CLI entry point.
    - Remove all deprecated files and "shim" code.
- **Expected Result**: A clean, maintainable, and professional codebase with a robust CLI.
- **Verification**: 
    - CLI argument parsing tests.
    - Final full-system verification.

## 3. Risk Mitigation

- **Incremental Steps**: Each phase is small and focused. If a phase introduces issues, it can be rolled back easily since the previous phase was fully verified.
- **Continuous Testing**: Extensive unit testing is required at the end of *every* phase before moving to the next.
- **Documentation First**: No code changes should be made until the corresponding phase's architecture and testing requirements are clearly understood and documented.

## 4. Definition of Done (Per Phase)
1. All tasks for the phase are completed.
2. High unit test coverage (as defined in the Testing Strategy) is achieved for all new/refactored components.
3. Existing core functionality is confirmed to be unchanged (or improved).
4. The codebase is clean and follows the defined package structure.
