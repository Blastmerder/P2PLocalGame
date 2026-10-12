# Orchestration and Reporting Logic

## Purpose
Coordinates the diagnostic workflow and formats the results for human consumption.

## Components
- `DiagnosticService`:
    - `run_diagnostics()`: The main entry point that triggers both `NATAnalyzer` and `VPNDetector` to produce a complete `DiagnosticReport`.
- `ReportFormatter`:
    - `format_report()`: Transforms the `DiagnosticReport` data into a structured, visually appealing ASCII-based report.
    - `_format_vpn_indicators()`: Generates detailed descriptions and confidence bars for each VPN indicator.
    - `_get_vpn_status_icon()` / `_get_nat_icon()`: Provides visual icons for different statuses.
- `RecommendationEngine`:
    - `get_recommendations()`: Analyzes the `DiagnosticReport` and generates actionable advice based on NAT types, VPN detection status, and potential security issues (like DNS leaks).
- `DiagnosticServiceFactory`:
    - `create_service()`: Implements the Factory pattern to instantiate the complete dependency graph (`LocalIPProvider` -> `SimplSTUNClient` -> `NATAnalyzerImpl` & `AdvancedVPNDetector` -> `DiagnosticService`).

## Dependencies
- `typing`
- `time`
