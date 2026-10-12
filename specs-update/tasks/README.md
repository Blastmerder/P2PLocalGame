# Implementation Plan for P2P L2 VPN Refactoring

This document outlines the phased approach to refactoring the current P2P L2 VPN project into a SOLID, decoupled architecture.

## Phases and Tasks

### Phase 1: Foundation
Establish the new package structure and core abstractions.
- [T001] [Setup Directory Structure](T001-setup-structure.md)
- [T002] [Implement Core Models](T002-core-models.md)
- [T003] [Implement Core Interfaces](T003-core-interfaces.md)

### Phase 2: Core Logic & Shim
Develop the "brain" of the system and maintain backward compatibility.
- [T004] [Implement Peer Manager](T004-peer-manager.md)
- [T005] [Implement Core Engine](T005-core-engine.md)
- [T006] [Implement VPNNode Shim](T006-vpn-node-shim.md)

### Phase 3: Component Realization
Implement concrete transport and interface layers.
- [T007] [Implement UDP Transport](T007-udp-transport.md)
- [T008] [Implement TAP Interface](T008-tap-interface.md)
- [T009] [System Integration](T009-integration.md)

### Phase 4: CLI & Cleanup
Modernize the user interface and clean up the legacy codebase.
- [T010] [Implement CLI Config Builder](T010-cli-builder.md)
- [T011] [Implement CLI Entry Point](T011-cli-entrypoint.md)
- [T012] [Final Cleanup](T012-cleanup.md)

## Dependencies Summary
- Core models and interfaces are the foundation for all subsequent work.
- The `Engine` depends on the interfaces and `PeerManager`.
- The `VPNNode Shim` allows us to verify the `Engine` before fully decoupling the transport and interface layers.
- The `Integration` phase wires the concrete implementations together.
- `CLI` can be developed in parallel with the logic but requires the models.
