import os

_path = os.path.dirname(os.path.abspath(__file__))


def run_frontend(port: int):
    os.system(f"node {os.path.join(_path, "standalone/www/app", "server.js")} --port {str(port)}")
