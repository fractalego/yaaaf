import os

_path = os.path.dirname(os.path.abspath(__file__))


def run_frontend(port: int):
    server_path = os.path.join(_path, "standalone/apps/www", "server.js")
    os.system(f"node {server_path} --port {str(port)}")
