#!/usr/bin/env python3
"""
Alternative frontend runner that supports custom certificate paths.
This module provides a convenient way to run the frontend with custom SSL certificates.
"""

import os
from yaaaf.client.run import run_frontend


def run_frontend_with_certs(
    port: int = 3000, cert_path: str = None, key_path: str = None
):
    """
    Run the frontend server with custom SSL certificates.

    Args:
        port: Port number to run the server on (default: 3000)
        cert_path: Path to SSL certificate file (.pem)
        key_path: Path to SSL private key file (.pem)
    """
    if cert_path or key_path:
        if not cert_path or not key_path:
            raise ValueError("Both cert_path and key_path must be provided together")

        if not os.path.isfile(cert_path):
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")

        if not os.path.isfile(key_path):
            raise FileNotFoundError(f"Private key file not found: {key_path}")

        run_frontend(port=port, use_https=True, cert_path=cert_path, key_path=key_path)
    else:
        run_frontend(port=port, use_https=False)


def run_frontend_with_env_certs(port: int = 3000):
    """
    Run the frontend server using certificate paths from environment variables.

    Environment variables:
        YAAAF_CERT_PATH: Path to SSL certificate file
        YAAAF_KEY_PATH: Path to SSL private key file

    Args:
        port: Port number to run the server on (default: 3000)
    """
    cert_path = os.environ.get("YAAAF_CERT_PATH")
    key_path = os.environ.get("YAAAF_KEY_PATH")

    if cert_path and key_path:
        run_frontend_with_certs(port=port, cert_path=cert_path, key_path=key_path)
    elif cert_path or key_path:
        print("Warning: Both YAAAF_CERT_PATH and YAAAF_KEY_PATH must be set")
        print("Falling back to auto-generated certificates")
        run_frontend(port=port, use_https=True)
    else:
        run_frontend(port=port, use_https=True)


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) >= 3:
        cert_file = sys.argv[1]
        key_file = sys.argv[2]
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 3000

        print("Starting frontend with custom certificates:")
        print(f"  Certificate: {cert_file}")
        print(f"  Private Key: {key_file}")
        print(f"  Port: {port}")

        run_frontend_with_certs(port=port, cert_path=cert_file, key_path=key_file)
    else:
        print("Usage: python run_with_certs.py <cert_path> <key_path> [port]")
        print(
            "Example: python run_with_certs.py /path/to/cert.pem /path/to/key.pem 3000"
        )
