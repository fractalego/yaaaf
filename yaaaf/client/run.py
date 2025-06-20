import os

_path = os.path.dirname(os.path.abspath(__file__))


def run_frontend(
    port: int, use_https: bool = False, cert_path: str = None, key_path: str = None
):
    server_path = os.path.join(_path, "standalone/apps/www", "server.js")

    # Pass through the YAAAF_ACTIVATE_POPUP environment variable to the frontend
    env_vars = os.environ.copy()
    if "YAAAF_ACTIVATE_POPUP" in env_vars:
        popup_setting = env_vars["YAAAF_ACTIVATE_POPUP"]
        print(f"GDPR popup setting: {popup_setting}")
    else:
        # Default to enabled if not set
        env_vars["YAAAF_ACTIVATE_POPUP"] = "true"
        print("GDPR popup setting: true (default)")

    # Set HTTPS environment variable if needed
    if use_https:
        env_vars["YAAAF_USE_HTTPS"] = "true"

        # Set custom certificate paths if provided
        if cert_path:
            if not os.path.isfile(cert_path):
                print(f"Error: Certificate file not found at {cert_path}")
                return
            env_vars["YAAAF_CERT_PATH"] = cert_path
            print(f"Using custom certificate: {cert_path}")

        if key_path:
            if not os.path.isfile(key_path):
                print(f"Error: Private key file not found at {key_path}")
                return
            env_vars["YAAAF_KEY_PATH"] = key_path
            print(f"Using custom private key: {key_path}")

        if cert_path and key_path:
            print(
                f"Starting frontend with HTTPS on port {port} using custom certificates"
            )
        else:
            print(f"Starting frontend with HTTPS on port {port}")
            print("Note: Using self-signed certificates for development")
    else:
        print(f"Starting frontend with HTTP on port {port}")

    # Use subprocess for better environment variable handling
    import subprocess

    subprocess.run(["node", server_path, "--port", str(port)], env=env_vars)
