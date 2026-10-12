# IP Provider Logic
## Description
The `IPProvider` interface and its implementation `LocalIPProvider` are responsible for retrieving the local and external IP addresses of the machine.

## Business Logic
1. **Get Internal IP**:
   - Attempts to determine the local IP address by creating a UDP socket and connecting to a public address (8.8.8.8:80).
   - Returns the socket's local address.
   - Fallback to `127.0.0.1` if an exception occurs.
   - Uses caching to avoid repeated socket operations.

2. **Get External IP**:
   - Attempts to retrieve the public IP address using the STUN protocol.
   - Iterates through a list of known Google STUN servers (`stun.l.google.com`, etc.).
   - Performs a STUN Binding Request.
   - Parses the `MAPPED-ADDRESS` attribute from the STUN response to extract the IPv4 address.
   - Uses caching to avoid repeated network requests.
   - Returns "Unknown" if all STUN queries fail.
