# Security Policy

## Supported Versions

Only the latest version of the IIAE SDK is supported for security updates. 

## Hardening Features Included
- **Input Sanitization**: Basic stripping of null bytes to prevent string termination vulnerabilities in backend processing.
- **Prompt Injection Defense**: The deterministic measurement evaluates the final output against context axioms; if prompt injection modifies the output semantically, $D_s$ will spike and block the transaction.
- **Cryptographic Immutability**: The CTM ledger issues SHA-256 receipts bound to exact timestamps and configurations.

## Reporting a Vulnerability
If you discover a security vulnerability within IIAE, please send an e-mail to security@iiae-project.com. All security vulnerabilities will be promptly addressed.
