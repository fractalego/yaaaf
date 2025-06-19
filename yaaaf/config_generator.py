#!/usr/bin/env python3
"""
YAAAF Configuration Generator

This module provides an interactive command-line interface for creating a local config.json file
for the YAAAF (Yet Another Autonomous Agents Framework) system.
"""

import json
import os
import sys


class ConfigGenerator:
    """Interactive configuration generator for YAAAF."""

    def __init__(self):
        self.config = {
            "client": {"model": "qwen2.5:32b", "temperature": 0.7, "max_tokens": 1024},
            "agents": [],
            "sources": [],
        }

        # Available agents with descriptions
        self.available_agents = {
            "reflection": "Step-by-step reasoning and thinking about tasks",
            "visualization": "Creates charts and visualizations from data",
            "sql": "Executes SQL queries against databases (requires SQLite sources)",
            "rag": "Retrieval-Augmented Generation using text sources",
            "reviewer": "Analyzes artifacts and validates results",
            "websearch": "Performs web searches using DuckDuckGo",
            "url": "Analyzes content from URLs based on instructions",
            "url_reviewer": "Extracts information from web search results",
            "user_input": "Interacts with users to gather additional information and clarification",
        }

    def print_welcome(self):
        """Print welcome message and instructions."""
        print("=" * 70)
        print("🤖 YAAAF Configuration Generator")
        print("=" * 70)
        print()
        print("This tool will help you create a local config.json file for YAAAF.")
        print("You'll be asked about:")
        print("  • LLM model selection")
        print("  • Which agents to enable")
        print("  • Database sources (SQLite files)")
        print("  • Text sources (files/folders for RAG)")
        print()
        print("Press Ctrl+C at any time to exit.")
        print("-" * 70)
        print()

    def get_input(self, prompt: str, default: str = None, validate_func=None) -> str:
        """Get user input with optional default and validation."""
        while True:
            if default:
                full_prompt = f"{prompt} [{default}]: "
            else:
                full_prompt = f"{prompt}: "

            try:
                response = input(full_prompt).strip()
                if not response and default:
                    response = default

                if validate_func and not validate_func(response):
                    print("❌ Invalid input. Please try again.")
                    continue

                return response
            except KeyboardInterrupt:
                print("\n\n👋 Configuration cancelled by user.")
                sys.exit(0)

    def get_yes_no(self, prompt: str, default: bool = None) -> bool:
        """Get yes/no input from user."""
        default_str = "y" if default else "n" if default is False else None
        while True:
            response = self.get_input(f"{prompt} (y/n)", default_str).lower()
            if response in ["y", "yes", "true", "1"]:
                return True
            elif response in ["n", "no", "false", "0"]:
                return False
            else:
                print("❌ Please enter 'y' for yes or 'n' for no.")

    def configure_client(self):
        """Configure the LLM client settings."""
        print("🔧 LLM Client Configuration")
        print("-" * 30)

        # Model selection
        model_name = self.get_input(
            "Enter Ollama model name (e.g., qwen2.5:32b, llama3.1:8b)", "qwen2.5:32b"
        )
        self.config["client"]["model"] = model_name

        # Temperature
        while True:
            try:
                temp_str = self.get_input(
                    "Temperature (0.0-2.0, higher = more creative)", "0.7"
                )
                temp = float(temp_str)
                if 0.0 <= temp <= 2.0:
                    self.config["client"]["temperature"] = temp
                    break
                else:
                    print("❌ Temperature must be between 0.0 and 2.0.")
            except ValueError:
                print("❌ Please enter a valid number.")

        # Max tokens
        while True:
            try:
                tokens_str = self.get_input("Max tokens per response", "1024")
                tokens = int(tokens_str)
                if tokens > 0:
                    self.config["client"]["max_tokens"] = tokens
                    break
                else:
                    print("❌ Max tokens must be positive.")
            except ValueError:
                print("❌ Please enter a valid number.")

    def configure_agents(self):
        """Configure which agents to enable."""
        print("\n🤖 Agent Configuration")
        print("-" * 25)
        print("\nAvailable agents:")

        for agent, description in self.available_agents.items():
            print(f"\n📦 {agent}")
            print(f"   {description}")

            if self.get_yes_no(f"Enable {agent}?", default=False):
                self.config["agents"].append(agent)

        if not self.config["agents"]:
            print(
                "\n⚠️  Warning: No agents selected. Adding 'reflection' agent as minimum."
            )
            self.config["agents"].append("reflection")

    def add_sqlite_sources(self):
        """Add SQLite database sources."""
        print("\n🗃️  SQLite Database Sources")
        print("-" * 30)

        if "sql" not in self.config["agents"]:
            print("ℹ️  SQL agent not enabled. Skipping SQLite sources.")
            return

        print("Add SQLite database files for the SQL agent to query.")

        while True:
            if not self.get_yes_no(
                "\nAdd a SQLite database?", default=len(self.config["sources"]) == 0
            ):
                break

            # Get database path
            while True:
                db_path = self.get_input("Path to SQLite database file")
                if os.path.isfile(db_path):
                    break
                elif os.path.isfile(os.path.abspath(db_path)):
                    db_path = os.path.abspath(db_path)
                    break
                else:
                    print(f"❌ File not found: {db_path}")
                    if not self.get_yes_no("Try again?", default=True):
                        return

            # Get source name
            default_name = os.path.splitext(os.path.basename(db_path))[0]
            source_name = self.get_input("Source name", default_name)

            source = {"name": source_name, "type": "sqlite", "path": db_path}

            self.config["sources"].append(source)
            print(f"✅ Added SQLite source: {source_name}")

    def add_text_sources(self):
        """Add text sources for RAG."""
        print("\n📚 Text Sources (for RAG)")
        print("-" * 30)

        if "rag" not in self.config["agents"]:
            print("ℹ️  RAG agent not enabled. Skipping text sources.")
            return

        print("Add text files or folders for the RAG agent to use.")
        print("Supported formats: .txt, .md, .html, .htm")

        while True:
            if not self.get_yes_no(
                "\nAdd text source?",
                default=len(
                    [s for s in self.config["sources"] if s.get("type") == "text"]
                )
                == 0,
            ):
                break

            # Get source path
            while True:
                source_path = self.get_input("Path to text file or folder")
                abs_path = os.path.abspath(source_path)

                if os.path.exists(abs_path):
                    source_path = abs_path
                    break
                else:
                    print(f"❌ Path not found: {source_path}")
                    if not self.get_yes_no("Try again?", default=True):
                        return

            # Get source name and description
            if os.path.isfile(source_path):
                default_name = os.path.splitext(os.path.basename(source_path))[0]
            else:
                default_name = os.path.basename(source_path.rstrip("/"))

            source_name = self.get_input("Source name", default_name)
            description = self.get_input("Description (optional)", source_name)

            source = {
                "name": source_name,
                "type": "text",
                "path": source_path,
                "description": description,
            }

            self.config["sources"].append(source)

            # Show what files will be included
            if os.path.isfile(source_path):
                print(f"✅ Added text file: {source_name}")
            else:
                text_files = []
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        if file.lower().endswith((".txt", ".md", ".html", ".htm")):
                            text_files.append(os.path.join(root, file))

                print(f"✅ Added text folder: {source_name} ({len(text_files)} files)")
                if text_files and len(text_files) <= 5:
                    print(
                        "   Files:", ", ".join(os.path.basename(f) for f in text_files)
                    )
                elif text_files:
                    print(
                        f"   Files: {os.path.basename(text_files[0])}, {os.path.basename(text_files[1])}, ... (+{len(text_files) - 2} more)"
                    )

    def save_config(self):
        """Save the configuration to config.json."""
        print("\n💾 Save Configuration")
        print("-" * 25)

        config_path = self.get_input("Config file path", "config.json")

        if os.path.exists(config_path):
            if not self.get_yes_no(
                f"File {config_path} exists. Overwrite?", default=False
            ):
                config_path = self.get_input("Enter new path")

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            print(f"✅ Configuration saved to: {os.path.abspath(config_path)}")
            return config_path
        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return None

    def show_usage_instructions(self, config_path: str):
        """Show instructions on how to use the config file."""
        print("\n" + "=" * 70)
        print("🎉 Configuration Complete!")
        print("=" * 70)

        print("\n📋 Configuration Summary:")
        print(f"   • Model: {self.config['client']['model']}")
        print(f"   • Temperature: {self.config['client']['temperature']}")
        print(f"   • Max tokens: {self.config['client']['max_tokens']}")
        print(f"   • Agents: {', '.join(self.config['agents'])}")
        print(f"   • Sources: {len(self.config['sources'])} configured")

        print("\n🚀 How to use your config:")
        print("   1. Set environment variable:")
        print(f"      export YAAAF_CONFIG={os.path.abspath(config_path)}")
        print("   ")
        print("   2. Start YAAAF backend:")
        print("      python -m yaaaf backend")
        print("   ")
        print("   3. Start YAAAF frontend (in another terminal):")
        print("      python -m yaaaf frontend")
        print("   ")
        print("   4. Open browser to: http://localhost:3000")

        print("\n📝 Alternative usage:")
        print(
            f"   • Copy {config_path} to yaaaf/server/default_config.json to make it the default"
        )
        print(f"   • Edit {config_path} manually to fine-tune settings")

        print("\n🔧 Configuration file location:")
        print(f"   {os.path.abspath(config_path)}")

        print("\n" + "=" * 70)

    def generate(self):
        """Run the interactive configuration generator."""
        try:
            self.print_welcome()
            self.configure_client()
            self.configure_agents()
            self.add_sqlite_sources()
            self.add_text_sources()

            # Show preview
            print("\n🔍 Configuration Preview:")
            print("-" * 30)
            print(json.dumps(self.config, indent=2))
            print()

            if self.get_yes_no("Save this configuration?", default=True):
                config_path = self.save_config()
                if config_path:
                    self.show_usage_instructions(config_path)
                    return True
            else:
                print("👋 Configuration not saved.")
                return False

        except KeyboardInterrupt:
            print("\n\n👋 Configuration cancelled by user.")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False


def main():
    """Main entry point for the config generator."""
    generator = ConfigGenerator()
    generator.generate()


if __name__ == "__main__":
    main()
