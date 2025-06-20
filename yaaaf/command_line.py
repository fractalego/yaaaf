import os
import sys

from yaaaf.client.run import run_frontend
from yaaaf.server.run import run_server
from yaaaf.config_generator import ConfigGenerator
from yaaaf.variables import get_variables


def print_help():
    print("\n")
    print("These are the available commands:")
    print("> yaaaf backend [port]: start the backend server (default port: 4000)")
    print(
        "> yaaaf frontend [port] [https]: start the frontend server (default port: 3000)"
    )
    print("    - Use 'https' as second or third argument to enable HTTPS")
    print("    - Examples: 'yaaaf frontend https', 'yaaaf frontend 3001 https'")
    print("> yaaaf config: create a local config.json file interactively")
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

        match command:
            case "backend":
                # Use default port or parse provided port
                if len(arguments) >= 3:
                    try:
                        port = int(arguments[2])
                    except ValueError:
                        print("Invalid port number. Must be an integer.\n")
                        print_help()
                        return
                else:
                    port = 4000
                run_server(host="0.0.0.0", port=port)

            case "frontend":
                # Parse port and https arguments
                port = 3000
                use_https = False

                # Check arguments for port and https
                for i in range(2, len(arguments)):
                    arg = arguments[i]
                    if arg.lower() == "https":
                        use_https = True
                    else:
                        try:
                            port = int(arg)
                        except ValueError:
                            print(
                                f"Invalid argument '{arg}'. Expected port number or 'https'.\n"
                            )
                            print_help()
                            return

                run_frontend(port=port, use_https=use_https)

            case "config":
                generator = ConfigGenerator()
                generator.generate()

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
