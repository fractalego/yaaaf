import os

_path = os.path.dirname(os.path.abspath(__file__))


def run_frontend(port: int):
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

    # Use subprocess for better environment variable handling
    import subprocess

    subprocess.run(["node", server_path, "--port", str(port)], env=env_vars)
