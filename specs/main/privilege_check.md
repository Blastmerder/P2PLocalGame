# Logic: Privilege Check
## Description
Verifies if the current process has sufficient administrative privileges to create and manage a TAP network interface.

## Requirements
- Must detect if running on Windows or Linux/Unix.
- On Windows, requires Administrator rights.
- On Linux/Unix, requires root privileges.
- If privileges are insufficient, the application should exit with an error message.
