# Logic: UDP Error Handling

## Description
Handles errors occurring within the UDP transport.

## Input
- `exc`: The exception object representing the error.

## Process
1. Receive the exception via `error_received`.
2. Log a warning message containing the exception details.

## Output
- Warning log message.
