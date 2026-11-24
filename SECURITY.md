# Security

The integration only reads the data stream on the boiler's port 23 and never sends
anything to the boiler. Port 23 itself has no password and no encryption, so keep it
inside your local network and never forward it to the internet (see the README).

## Reporting a vulnerability

Please do not open a public issue. Use *Security → Report a vulnerability* on the
GitHub page of this repository to report it privately.
