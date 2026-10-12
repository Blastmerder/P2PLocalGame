# P2P L2 VPN Specification Update

This directory contains the target architecture, testing strategy, CLI specification, and migration plan for the refactoring of the P2P L2 VPN project.

## Purpose
The goal of this refactoring is to improve the maintainability, testability, and extensibility of the project by applying SOLID principles and separating concerns, while preserving its core functionality.

## Documents

### 1. [Architecture](architecture.md)
Defines the target package structure, module responsibilities, and dependency flow. It focuses on decoupling the core VPN logic from transport (UDP) and hardware (TAP) layers.

### 2. [Testing Strategy](testing.md)
Describes the approach to unit testing, focusing on behavioral isolation, mocking of network and hardware interfaces, and ensuring high coverage of the core domain logic.

### 3. [CLI Specification](cli.md)
Specifies the requirements for a robust, user-friendly command-line interface, replacing the current monolithic `main.py` with a clean entry point and dedicated command handlers.

### 4. [Migration Plan](migration-plan.md)
Outlines a phased, safe transition from the current codebase to the target architecture, ensuring each step is verifiable via unit tests.

## Reading Order
For a full understanding of the plan, it is recommended to read the documents in the order listed above.
