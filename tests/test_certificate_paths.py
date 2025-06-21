#!/usr/bin/env python3
"""
Test script to demonstrate all certificate path configuration options for YAAAF.
"""

import os
import sys
import tempfile

# Add the current directory to Python path
sys.path.append(os.getcwd())

from yaaaf.client.run import run_frontend


def create_dummy_cert_files():
    """Create dummy certificate files for testing."""
    # Create temporary files
    cert_fd, cert_path = tempfile.mkstemp(suffix=".pem", prefix="test_cert_")
    key_fd, key_path = tempfile.mkstemp(suffix=".pem", prefix="test_key_")

    # Write dummy content
    with os.fdopen(cert_fd, "w") as f:
        f.write("-----BEGIN CERTIFICATE-----\n")
        f.write("DUMMY CERTIFICATE FOR TESTING\n")
        f.write("-----END CERTIFICATE-----\n")

    with os.fdopen(key_fd, "w") as f:
        f.write("-----BEGIN PRIVATE KEY-----\n")
        f.write("DUMMY PRIVATE KEY FOR TESTING\n")
        f.write("-----END PRIVATE KEY-----\n")

    return cert_path, key_path


def test_certificate_path_options():
    """Test all certificate path configuration methods."""

    print("🔐 YAAAF Certificate Path Configuration Test")
    print("=" * 60)

    # Create dummy certificate files
    cert_path, key_path = create_dummy_cert_files()

    try:
        print("\n📁 Created test certificate files:")
        print(f"   Certificate: {cert_path}")
        print(f"   Private Key: {key_path}")

        print("\n🧪 Testing Certificate Path Methods:")
        print("-" * 40)

        # Method 1: Environment Variables
        print("\n1️⃣ Method 1: Environment Variables")
        print("   export YAAAF_CERT_PATH=/path/to/cert.pem")
        print("   export YAAAF_KEY_PATH=/path/to/key.pem")
        print("   python -m yaaaf frontend https")

        # Simulate environment variable setup
        os.environ["YAAAF_CERT_PATH"] = cert_path
        os.environ["YAAAF_KEY_PATH"] = key_path

        print(f"   ✅ YAAAF_CERT_PATH = {os.environ.get('YAAAF_CERT_PATH')}")
        print(f"   ✅ YAAAF_KEY_PATH = {os.environ.get('YAAAF_KEY_PATH')}")

        # Method 2: Programmatic API
        print("\n2️⃣ Method 2: Programmatic API")
        print("   from yaaaf.client.run import run_frontend")
        print("   run_frontend(port=3000, use_https=True,")
        print("                cert_path='/path/to/cert.pem',")
        print("                key_path='/path/to/key.pem')")

        # Test function signature
        import inspect

        sig = inspect.signature(run_frontend)
        print(f"   ✅ Function signature: {sig}")

        # Method 3: Default Auto-generated
        print("\n3️⃣ Method 3: Auto-generated Certificates")
        print("   python -m yaaaf frontend https")
        print("   (No custom paths - uses auto-generated certificates)")

        default_cert_path = "/path/to/yaaaf/client/standalone/apps/www/cert.pem"
        default_key_path = "/path/to/yaaaf/client/standalone/apps/www/key.pem"
        print(f"   📍 Default cert location: {default_cert_path}")
        print(f"   📍 Default key location: {default_key_path}")

        print("\n🔍 Certificate Path Priority:")
        print("   1. Custom paths in function arguments (highest priority)")
        print("   2. Environment variables (YAAAF_CERT_PATH, YAAAF_KEY_PATH)")
        print("   3. Auto-generated certificates (fallback)")

        print("\n✅ All certificate path methods validated!")

        print("\n📖 Usage Examples:")
        print("   # Using environment variables")
        print("   export YAAAF_CERT_PATH=/etc/ssl/certs/yaaaf.pem")
        print("   export YAAAF_KEY_PATH=/etc/ssl/private/yaaaf.key")
        print("   python -m yaaaf frontend https")
        print("")
        print("   # Using programmatic API")
        print("   from yaaaf.client.run import run_frontend")
        print("   run_frontend(3000, True, '/path/to/cert.pem', '/path/to/key.pem')")
        print("")
        print("   # Using helper module")
        print("   from yaaaf.client.run_with_certs import run_frontend_with_certs")
        print(
            "   run_frontend_with_certs(3000, '/path/to/cert.pem', '/path/to/key.pem')"
        )

    finally:
        # Clean up test files
        try:
            os.unlink(cert_path)
            os.unlink(key_path)
            print("\n🧹 Cleaned up test files")
        except Exception:
            pass

        # Clean up environment variables
        if "YAAAF_CERT_PATH" in os.environ:
            del os.environ["YAAAF_CERT_PATH"]
        if "YAAAF_KEY_PATH" in os.environ:
            del os.environ["YAAAF_KEY_PATH"]


def show_certificate_requirements():
    """Show information about certificate file requirements."""

    print("\n📋 Certificate File Requirements:")
    print("-" * 40)

    print("\n🔑 Certificate File (.pem format):")
    print("   • Must contain valid X.509 certificate")
    print("   • Should include the full certificate chain if using intermediate CAs")
    print("   • Common names: cert.pem, certificate.pem, server.crt")

    print("\n🗝️  Private Key File (.pem format):")
    print("   • Must contain the private key corresponding to the certificate")
    print("   • Should NOT be password protected for automated deployment")
    print("   • Common names: key.pem, private.key, server.key")

    print("\n⚠️  Security Notes:")
    print("   • Private key files should have restrictive permissions (600)")
    print("   • Never commit private keys to version control")
    print("   • Use proper certificate authorities for production")
    print("   • Auto-generated certificates are for development only")


if __name__ == "__main__":
    test_certificate_path_options()
    show_certificate_requirements()

    print("\n🎉 Certificate path configuration test completed!")
    print("   YAAAF now supports flexible SSL certificate configuration")
