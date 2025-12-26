"""
Manages repository cloning, checkout, and Python environment setup for SWE-bench evaluation.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)


class RepoManager:
    """Manages git repositories and Python environments for SWE-bench instances."""

    def __init__(self, workspace_dir: str = "./swe_bench_workspace"):
        """Initialize the repo manager.

        Args:
            workspace_dir: Directory to store cloned repos and environments
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.repos_dir = self.workspace_dir / "repos"
        self.envs_dir = self.workspace_dir / "envs"

        # Create workspace directories
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.envs_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, repo: str) -> Path:
        """Get the local path for a repository.

        Args:
            repo: Repository name (e.g., "django/django")

        Returns:
            Path to the local repository
        """
        # Replace / with __ for filesystem safety
        safe_name = repo.replace("/", "__")
        return self.repos_dir / safe_name

    def get_env_path(self, repo: str) -> Path:
        """Get the virtual environment path for a repository.

        Args:
            repo: Repository name

        Returns:
            Path to the virtual environment
        """
        safe_name = repo.replace("/", "__")
        return self.envs_dir / safe_name

    def clone_repo(self, repo: str, force: bool = False) -> Path:
        """Clone a repository if not already present.

        Args:
            repo: Repository name (e.g., "django/django")
            force: If True, remove existing repo and re-clone

        Returns:
            Path to the cloned repository
        """
        repo_path = self.get_repo_path(repo)

        if repo_path.exists():
            if force:
                _logger.info(f"Removing existing repo: {repo_path}")
                shutil.rmtree(repo_path)
            else:
                _logger.info(f"Repo already exists: {repo_path}")
                return repo_path

        github_url = f"https://github.com/{repo}.git"
        _logger.info(f"Cloning {github_url} to {repo_path}")

        try:
            subprocess.run(
                ["git", "clone", "--depth", "100", github_url, str(repo_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            # Fetch more history for checkout to work
            subprocess.run(
                ["git", "fetch", "--unshallow"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            _logger.error(f"Failed to clone {repo}: {e.stderr}")
            raise

        return repo_path

    def checkout_commit(self, repo: str, commit: str) -> None:
        """Checkout a specific commit in a repository.

        Args:
            repo: Repository name
            commit: Commit hash to checkout
        """
        repo_path = self.get_repo_path(repo)

        if not repo_path.exists():
            raise ValueError(f"Repository not cloned: {repo}")

        _logger.info(f"Checking out {commit} in {repo}")

        try:
            # Fetch the specific commit if not available
            subprocess.run(
                ["git", "fetch", "origin", commit],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            # Commit might already be available locally
            pass

        try:
            # Reset any changes and checkout
            subprocess.run(
                ["git", "reset", "--hard"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "checkout", commit],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            _logger.error(f"Failed to checkout {commit}: {e.stderr}")
            raise

    def setup_environment(
        self,
        repo: str,
        python_version: str = "python3",
        force: bool = False
    ) -> Path:
        """Create a virtual environment for a repository.

        Args:
            repo: Repository name
            python_version: Python interpreter to use
            force: If True, recreate the environment

        Returns:
            Path to the virtual environment
        """
        env_path = self.get_env_path(repo)
        repo_path = self.get_repo_path(repo)

        if env_path.exists():
            if force:
                _logger.info(f"Removing existing environment: {env_path}")
                shutil.rmtree(env_path)
            else:
                _logger.info(f"Environment already exists: {env_path}")
                return env_path

        _logger.info(f"Creating virtual environment: {env_path}")

        try:
            subprocess.run(
                [python_version, "-m", "venv", str(env_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            _logger.error(f"Failed to create venv: {e.stderr}")
            raise

        # Install the repo in development mode if possible
        pip_path = env_path / "bin" / "pip"

        # Upgrade pip and install pytest
        _logger.info("Upgrading pip...")
        subprocess.run(
            [str(pip_path), "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
        )
        _logger.info("Installing pytest and common test dependencies...")
        result = subprocess.run(
            [str(pip_path), "install", "pytest", "hypothesis", "pytest-astropy", "pytest-xdist"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            _logger.info("Test dependencies installed successfully")
        else:
            _logger.warning(f"Test dependencies installation may have failed: {result.stderr}")

        # Try to install requirements if they exist
        requirements_files = [
            repo_path / "requirements.txt",
            repo_path / "requirements-dev.txt",
            repo_path / "requirements_dev.txt",
        ]

        for req_file in requirements_files:
            if req_file.exists():
                _logger.info(f"Installing requirements from {req_file}")
                try:
                    subprocess.run(
                        [str(pip_path), "install", "-r", str(req_file)],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    _logger.warning(f"Failed to install {req_file}: {e}")

        # Try to install the package itself
        if (repo_path / "setup.py").exists() or (repo_path / "pyproject.toml").exists():
            _logger.info(f"Installing package in development mode from {repo_path}")
            try:
                result = subprocess.run(
                    [str(pip_path), "install", "-e", str(repo_path)],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minutes for complex packages
                )
                if result.returncode != 0:
                    _logger.error(f"Failed to install package (exit code {result.returncode})")
                    _logger.error(f"stdout: {result.stdout[-2000:] if result.stdout else 'none'}")
                    _logger.error(f"stderr: {result.stderr[-2000:] if result.stderr else 'none'}")
                else:
                    _logger.info("Package installed successfully in development mode")
            except subprocess.TimeoutExpired as e:
                _logger.warning(f"Package installation timed out after 600s: {e}")
            except Exception as e:
                _logger.warning(f"Failed to install package: {e}")

        return env_path

    def run_in_env(
        self,
        repo: str,
        command: list[str],
        cwd: Optional[Path] = None,
        timeout: int = 300
    ) -> subprocess.CompletedProcess:
        """Run a command in the repository's virtual environment.

        Args:
            repo: Repository name
            command: Command to run (first element should be the executable)
            cwd: Working directory (defaults to repo path)
            timeout: Timeout in seconds

        Returns:
            CompletedProcess result
        """
        env_path = self.get_env_path(repo)
        repo_path = self.get_repo_path(repo)

        if not env_path.exists():
            raise ValueError(f"Environment not set up for {repo}")

        # Modify PATH to use the venv
        env = os.environ.copy()
        env["PATH"] = f"{env_path}/bin:{env['PATH']}"
        env["VIRTUAL_ENV"] = str(env_path)

        work_dir = cwd or repo_path

        return subprocess.run(
            command,
            cwd=work_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def run_tests(
        self,
        repo: str,
        test_list: list[str],
        timeout: int = 600
    ) -> dict:
        """Run specific tests in the repository.

        Args:
            repo: Repository name
            test_list: List of test identifiers (e.g., ["test/test_foo.py::test_bar"])
            timeout: Timeout in seconds

        Returns:
            Dict with 'passed', 'failed', 'errors' counts and 'output'
        """
        repo_path = self.get_repo_path(repo)

        # Build pytest command
        command = ["python", "-m", "pytest", "-xvs"] + test_list

        _logger.info(f"Running pytest with {len(test_list)} test(s) in {repo_path}")

        try:
            result = self.run_in_env(repo, command, cwd=repo_path, timeout=timeout)

            # Parse pytest output
            output = result.stdout + result.stderr
            passed = output.count(" PASSED")
            failed = output.count(" FAILED")
            errors = output.count(" ERROR")

            # Check for common setup errors
            if "No module named pytest" in output:
                _logger.error("pytest is not installed in the virtual environment")
            elif "No module named" in output:
                _logger.warning(f"Missing module detected in test output")

            _logger.info(f"Test run completed: returncode={result.returncode}, "
                        f"passed={passed}, failed={failed}, errors={errors}")

            return {
                "success": result.returncode == 0,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "returncode": result.returncode,
                "output": output,
            }

        except subprocess.TimeoutExpired:
            _logger.error(f"Test execution timed out after {timeout}s")
            return {
                "success": False,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "returncode": -1,
                "output": "Test execution timed out",
            }

    def apply_patch(self, repo: str, patch: str) -> bool:
        """Apply a patch to the repository.

        Args:
            repo: Repository name
            patch: Patch content (unified diff format)

        Returns:
            True if patch applied successfully
        """
        repo_path = self.get_repo_path(repo)

        # Write patch to temp file
        patch_file = repo_path / ".tmp_patch.diff"
        patch_file.write_text(patch)

        try:
            result = subprocess.run(
                ["git", "apply", str(patch_file)],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            success = result.returncode == 0
            if not success:
                _logger.warning(f"Patch failed: {result.stderr}")
            return success
        finally:
            patch_file.unlink(missing_ok=True)

    def reset_repo(self, repo: str) -> None:
        """Reset repository to clean state (discard all changes).

        Args:
            repo: Repository name
        """
        repo_path = self.get_repo_path(repo)

        subprocess.run(
            ["git", "reset", "--hard"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "clean", "-fd"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
