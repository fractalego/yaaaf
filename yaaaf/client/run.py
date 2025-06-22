import os

_path = os.path.dirname(os.path.abspath(__file__))


def run_frontend(
    port: int, use_https: bool = False, cert_path: str = None, key_path: str = None
):
    server_path = os.path.join(_path, "standalone/apps/www", "server.js")

    # Check if Node.js is available
    import subprocess
    import shutil

    # Try different node command variations
    node_cmd = None
    for cmd in ["node", "nodejs", "/usr/bin/node", "/usr/bin/nodejs"]:
        if shutil.which(cmd):
            node_cmd = cmd
            break

    if not node_cmd:
        print("❌ Error: Node.js is not installed or not available in PATH.")
        print("Please install Node.js (version 18+) to run the frontend:")
        print("- On Ubuntu/Debian: sudo apt-get install nodejs npm")
        print("- On macOS: brew install node")
        print("- On Windows: Download from https://nodejs.org/")
        print("Searched for: node, nodejs, /usr/bin/node, /usr/bin/nodejs")
        return

    # Test Node.js version
    try:
        version_result = subprocess.run(
            [node_cmd, "--version"], capture_output=True, text=True
        )
        if version_result.returncode == 0:
            print(f"✅ Found Node.js: {node_cmd} {version_result.stdout.strip()}")
        else:
            print(f"⚠️  Node.js found but version check failed: {version_result.stderr}")
    except Exception as e:
        print(f"⚠️  Could not verify Node.js version: {e}")

    # Check if server.js exists
    if not os.path.exists(server_path):
        print(f"Error: Frontend server not found at {server_path}")
        print("The standalone frontend may not be properly installed.")
        return

    # Pass through the YAAAF_ACTIVATE_POPUP environment variable to the frontend
    env_vars = os.environ.copy()
    if "YAAAF_ACTIVATE_POPUP" in env_vars:
        popup_setting = env_vars["YAAAF_ACTIVATE_POPUP"]
        print(f"GDPR popup setting: {popup_setting}")
    else:
        # Default to enabled if not set
        env_vars["YAAAF_ACTIVATE_POPUP"] = "true"
        print("GDPR popup setting: true (default)")

    # Set port environment variable for Next.js
    env_vars["PORT"] = str(port)

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

    # Handle HTTPS by creating a simple wrapper if needed
    if use_https:
        print("⚠️  HTTPS mode requested but not yet fully supported in standalone mode.")
        print("    The server will start in HTTP mode.")
        print("    For HTTPS, consider using a reverse proxy like nginx or running:")
        print("    python -m yaaaf frontend <port>  # and configure nginx with SSL")
        use_https = False  # Fall back to HTTP for now

    # Change to the server directory before running
    original_cwd = os.getcwd()
    server_dir = os.path.dirname(server_path)

    try:
        os.chdir(server_dir)
        print(f"Starting Next.js server from: {server_dir}")

        # Run the Node.js server with proper environment
        cmd = [node_cmd, "server.js"]
        print(f"Executing: {' '.join(cmd)}")

        # Use Popen for better control and to avoid the "performance" error
        process = subprocess.Popen(
            cmd,
            env=env_vars,
            cwd=server_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        # Stream output in real-time
        try:
            for line in process.stdout:
                print(line.rstrip())
        except KeyboardInterrupt:
            print("\n🛑 Received interrupt signal...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("⚠️  Process didn't terminate gracefully, forcing...")
                process.kill()
            return 0

        return_code = process.wait()
        return return_code

    except FileNotFoundError as e:
        print(f"❌ Server file not found: {e}")
        print(f"   Looked for: {server_path}")
        return 1
    except Exception as e:
        print(f"❌ Error starting frontend server: {e}")
        return 1
    finally:
        os.chdir(original_cwd)
