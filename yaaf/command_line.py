import os
import sys

from yaaf.client.run import run_frontend
from yaaf.server.run import run_server
from yaaf.variables import get_variables


def print_help():
    print("\n")
    print("These are the available commands:")
    print("> yaaf backend port: start the backend server listening on port 4000")
    print("> yaaf frontend port: start the frontend server listening on port 3000")
    print()


def add_cwd_to_syspath():
    sys.path.append(os.getcwd())


def print_incipit():
    print()
    print(f"Running WAFL version {get_variables()['version']}.")
    print()


def process_cli():
    add_cwd_to_syspath()
    print_incipit()

    arguments = sys.argv
    if len(arguments) > 2:
        command = arguments[1]
        port = int(arguments[2])

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
        print("YAAF ended due to the exception above.")