import os
import sys

from yaaaf.client.run import run_frontend
from yaaaf.server.run import run_server
from yaaaf.variables import get_variables


def print_help():
    print("\n")
    print("These are the available commands:")
    print("> yaaaf backend [port]: start the backend server (default port: 4000)")
    print("> yaaaf frontend [port]: start the frontend server (default port: 3000)")
    print()


def add_cwd_to_syspath():
    sys.path.append(os.getcwd())


def print_incipit():
    print()
    print(f"Running YAAAF version {get_variables()['version']}.")
    print()


def process_cli():
    add_cwd_to_syspath()
    print_incipit()

    arguments = sys.argv
    if len(arguments) >= 2:
        command = arguments[1]
        
        # Use default ports or parse provided port
        if len(arguments) >= 3:
            try:
                port = int(arguments[2])
            except ValueError:
                print("Invalid port number. Must be an integer.\n")
                print_help()
                return
        else:
            # Default ports
            port = 4000 if command == "backend" else 3000

        match command:
            case "backend":
                run_server(host="0.0.0.0", port=port)

            case "frontend":
                run_frontend(port=port)

            case _:
                print("Unknown argument.\n")
                print_help()

    else:
        print("Not enough arguments.\n")
        print_help()


def main():
    try:
        process_cli()

    except RuntimeError as e:
        print(e)
        print()
        print("YAAAF ended due to the exception above.")
