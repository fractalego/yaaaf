"""
Manages repository cloning, checkout, and Python environment setup for SWE-bench evaluation.
"""

import glob
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)


def convert_unittest_to_pytest(test_id: str, repo_path: Path) -> str:
    """Convert unittest-style test ID to pytest format.

    SWE-bench uses unittest-style test IDs like:
        test_custom_test_name (backends.sqlite.test_creation.TestDbSignatureTests)

    pytest expects:
        tests/backends/sqlite/test_creation.py::TestDbSignatureTests::test_custom_test_name

    Args:
        test_id: Unittest-style test identifier
        repo_path: Path to the repository (to find actual test files)

    Returns:
        pytest-compatible test identifier
    """
    import re

    # Check if already in pytest format (contains :: or ends with .py)
    if "::" in test_id or test_id.endswith(".py"):
        return test_id

    # Parse unittest format: "test_method (module.path.ClassName)"
    # or "test_method (module.path.ClassName.submethod)"
    match = re.match(r'^(\w+)\s+\(([^)]+)\)$', test_id.strip())
    if not match:
        # Doesn't match expected format, return as-is
        _logger.warning(f"Test ID doesn't match unittest format: {test_id}")
        return test_id

    test_method = match.group(1)
    full_path = match.group(2)

    # Split the path - last component is the class, rest is module path
    parts = full_path.split('.')

    # Find where the class name starts (classes are CamelCase or start with Test)
    class_idx = None
    for i, part in enumerate(parts):
        if part[0].isupper() or part.startswith('Test'):
            class_idx = i
            break

    if class_idx is None:
        # No obvious class name found, assume last component is class
        class_idx = len(parts) - 1

    module_parts = parts[:class_idx]
    class_name = parts[class_idx]

    # Try to find the test file
    # Common patterns:
    # 1. tests/module/path/test_file.py
    # 2. test/module/path/test_file.py
    # 3. module/path/tests/test_file.py
    # 4. module/path/test_file.py

    # For Django, tests are typically in tests/ directory
    possible_paths = []

    # Build module path with different prefixes
    module_path = '/'.join(module_parts)
    last_module = module_parts[-1] if module_parts else ''

    # Django-style: tests/backends/sqlite/test_creation.py
    if module_parts:
        possible_paths.append(f"tests/{module_path}.py")
        # Also try without 'test_' prefix in filename
        if last_module.startswith('test_'):
            alt_path = '/'.join(module_parts[:-1] + [last_module])
            possible_paths.append(f"tests/{alt_path}.py")
        else:
            # Try adding test_ prefix
            alt_parts = module_parts[:-1] + [f"test_{last_module}"]
            possible_paths.append(f"tests/{'/'.join(alt_parts)}.py")

    # Try test/ instead of tests/
    for p in list(possible_paths):
        if p.startswith("tests/"):
            possible_paths.append("test/" + p[6:])

    # Try without tests/ prefix
    possible_paths.append(f"{module_path}.py")

    # Find which file actually exists
    test_file = None
    for path in possible_paths:
        full_path_check = repo_path / path
        if full_path_check.exists():
            test_file = path
            break

    if test_file is None:
        # Try glob to find the file
        import glob as glob_module
        pattern = f"**/{module_parts[-1]}.py" if module_parts else "**/*.py"
        matches = glob_module.glob(str(repo_path / pattern), recursive=True)
        for m in matches:
            if 'test' in m.lower():
                test_file = str(Path(m).relative_to(repo_path))
                break

    if test_file is None:
        _logger.warning(f"Could not find test file for: {test_id}, tried: {possible_paths[:3]}")
        # Fall back to best guess
        test_file = f"tests/{module_path}.py"

    # Build pytest format
    pytest_id = f"{test_file}::{class_name}::{test_method}"
    _logger.debug(f"Converted '{test_id}' -> '{pytest_id}'")
    return pytest_id


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
                # Verify the environment is valid (has pip and python)
                pip_path = env_path / "bin" / "pip"
                python_path = env_path / "bin" / "python"
                if pip_path.exists() and python_path.exists():
                    _logger.info(f"Environment already exists: {env_path}")
                    return env_path
                else:
                    _logger.warning(f"Environment exists but is incomplete (missing pip or python), recreating...")
                    shutil.rmtree(env_path)

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
        try:
            subprocess.run(
                [str(pip_path), "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )
        except subprocess.CalledProcessError as e:
            _logger.warning(f"pip upgrade failed: {e.stderr}")

        _logger.info("Installing pytest and common test dependencies...")
        # Only install pytest-astropy for astropy repos (it's huge and slow)
        test_deps = ["pytest", "pytest-xdist"]
        if "astropy" in repo.lower():
            test_deps.extend(["pytest-astropy", "hypothesis"])

        try:
            result = subprocess.run(
                [str(pip_path), "install"] + test_deps,
                check=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            _logger.info("Test dependencies installed successfully")

            # Verify pytest is actually installed and executable
            pytest_path = env_path / "bin" / "pytest"
            if pytest_path.exists():
                _logger.info(f"pytest verified at: {pytest_path}")
            else:
                _logger.error(f"pytest not found at expected location: {pytest_path}")
        except subprocess.CalledProcessError as e:
            _logger.error(f"Test dependencies installation FAILED: {e.stderr}")
            # Try installing pytest alone as fallback
            try:
                _logger.info("Attempting fallback: installing pytest only...")
                subprocess.run(
                    [str(pip_path), "install", "pytest"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                _logger.info("pytest installed successfully (fallback)")
            except subprocess.CalledProcessError as e2:
                _logger.error(f"pytest installation failed completely: {e2.stderr}")

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
            repo_name = repo.split("/")[-1].lower()

            # Install repo-specific dependencies FIRST (they may pin versions like numpy<2)
            if "astropy" in repo_name:
                _logger.info("Installing astropy-specific dependencies...")
                # Install all astropy build dependencies
                # NOTE: numpy<2 is required because old astropy uses numpy C API that changed in numpy 2.0
                astropy_deps = [
                    "numpy<2",        # MUST be before build - numpy 2.0 changed C API
                    "pyerfa",
                    "setuptools<70",  # setuptools 70+ removed dep_util
                    "jinja2",         # used by astropy templates
                    "pyyaml",         # used by astropy config
                    "packaging",      # used by astropy version checks
                    "extension-helpers>=1,<2",  # astropy extension builder
                    "cython<3",       # old astropy may need cython 0.x
                ]
                result = subprocess.run(
                    [str(pip_path), "install"] + astropy_deps,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    _logger.error(f"Failed to install astropy deps: {result.stderr}")
                else:
                    _logger.info("astropy dependencies installed successfully")
            elif "scipy" in repo_name:
                _logger.info("Installing scipy-specific dependencies...")
                subprocess.run(
                    [str(pip_path), "install", "numpy<2", "pybind11", "meson-python", "pythran", "cython<3"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            elif "matplotlib" in repo_name:
                _logger.info("Installing matplotlib-specific dependencies...")
                subprocess.run(
                    [str(pip_path), "install", "meson-python", "pybind11", "certifi"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            elif "django" in repo_name:
                _logger.info("Installing Django-specific dependencies...")
                # Django needs these for testing
                # legacy-cgi provides the cgi module for Python 3.13+ (removed from stdlib)
                django_deps = ["pytz", "sqlparse", "asgiref", "legacy-cgi"]

                # Check if Django uses its native test runner (tests/runtests.py)
                # If so, DON'T install pytest-django as it causes conflicts
                django_test_runner = repo_path / "tests" / "runtests.py"
                if django_test_runner.exists():
                    _logger.info(f"Django native test runner detected at {django_test_runner}")
                    _logger.info("Will NOT install pytest-django (use Django's native test runner instead)")
                else:
                    _logger.info("Django native test runner not found, installing pytest-django")
                    django_deps.append("pytest-django")

                subprocess.run(
                    [str(pip_path), "install"] + django_deps,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

            # Install common build dependencies (skip numpy - handled by repo-specific deps above)
            _logger.info("Installing common build dependencies...")
            subprocess.run(
                [str(pip_path), "install", "cython", "extension-helpers", "setuptools-scm", "wheel"],
                capture_output=True,
                text=True,
                timeout=300,
            )

            # For packages with C extensions (like astropy), we need to build extensions.
            # Some packages need build_ext even after a "successful" pip install.
            needs_build_ext = "astropy" in repo_name or "scipy" in repo_name

            _logger.info(f"Installing package in development mode from {repo_path}")
            python_path = env_path / "bin" / "python"
            editable_success = False

            try:
                result = subprocess.run(
                    [str(pip_path), "install", "-e", str(repo_path), "--no-build-isolation"],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minutes for complex packages
                )
                if result.returncode == 0:
                    _logger.info("Editable install completed")
                    editable_success = True
                else:
                    _logger.warning(f"Editable install failed: {result.stderr[-300:] if result.stderr else 'none'}")
                    # Create marker to use PYTHONPATH fallback for ANY package where editable install failed
                    _logger.info("Creating .use_pythonpath marker for PYTHONPATH fallback")
                    (env_path / ".use_pythonpath").touch()
            except subprocess.TimeoutExpired as e:
                _logger.warning(f"Package installation timed out: {e}")
                (env_path / ".use_pythonpath").touch()
            except Exception as e:
                _logger.warning(f"Failed to install package: {e}")
                (env_path / ".use_pythonpath").touch()

            # For packages with C extensions, always run build_ext --inplace
            # This is needed even if editable install "succeeded" because pip might not build extensions
            if needs_build_ext or not editable_success:
                _logger.info(f"Building C extensions in-place for {repo_name}...")
                # Set up environment for build_ext
                build_env = os.environ.copy()
                build_env["PATH"] = f"{env_path}/bin:{build_env['PATH']}"
                build_env["VIRTUAL_ENV"] = str(env_path)
                # Disable warnings-as-errors for old packages with minor API mismatches
                build_env["CFLAGS"] = build_env.get("CFLAGS", "") + " -Wno-error=incompatible-pointer-types"
                try:
                    build_result = subprocess.run(
                        [str(python_path), "setup.py", "build_ext", "--inplace"],
                        cwd=repo_path,
                        env=build_env,
                        capture_output=True,
                        text=True,
                        timeout=600,
                    )
                    if build_result.returncode == 0:
                        _logger.info("Built extensions in-place successfully")
                        # Log some of the stdout to confirm what was built
                        if build_result.stdout:
                            # Look for lines about building extensions
                            for line in build_result.stdout.split('\n')[-20:]:
                                if 'building' in line.lower() or 'compil' in line.lower():
                                    _logger.info(f"  {line}")
                    else:
                        _logger.error(f"build_ext FAILED with return code {build_result.returncode}")
                        if build_result.stdout:
                            _logger.error(f"build_ext stdout (last 500 chars): {build_result.stdout[-500:]}")
                        if build_result.stderr:
                            _logger.error(f"build_ext stderr (last 500 chars): {build_result.stderr[-500:]}")
                except subprocess.TimeoutExpired:
                    _logger.error("build_ext timed out after 600s")
                except Exception as e:
                    _logger.error(f"build_ext exception: {e}")

                # Verify that extensions were actually built by checking for .so files
                so_files = glob.glob(str(repo_path / "**/*.so"), recursive=True)
                if so_files:
                    _logger.info(f"Found {len(so_files)} compiled extension(s)")
                    for so_file in so_files[:5]:
                        _logger.info(f"  - {so_file}")
                else:
                    _logger.warning("No .so files found - extensions may not have been built!")

                # Use PYTHONPATH for packages with C extensions
                (env_path / ".use_pythonpath").touch()

                # Verify the package can be imported
                _logger.info(f"Verifying {repo_name} can be imported...")
                import_test_env = os.environ.copy()
                import_test_env["PATH"] = f"{env_path}/bin:{import_test_env['PATH']}"
                import_test_env["VIRTUAL_ENV"] = str(env_path)
                import_test_env["PYTHONPATH"] = str(repo_path)
                import_result = subprocess.run(
                    [str(python_path), "-c", f"import {repo_name}; print({repo_name}.__version__)"],
                    cwd=repo_path,
                    env=import_test_env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if import_result.returncode == 0:
                    _logger.info(f"Import successful: {repo_name} {import_result.stdout.strip()}")
                else:
                    _logger.error(f"Import FAILED: {import_result.stderr[:300]}")

        # Final verification: ensure pytest is available
        _logger.info("Final verification: checking pytest availability...")
        pytest_check = subprocess.run(
            [str(env_path / "bin" / "python"), "-m", "pytest", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if pytest_check.returncode == 0:
            _logger.info(f"pytest is available: {pytest_check.stdout.strip()}")
        else:
            _logger.error(f"pytest verification FAILED: {pytest_check.stderr}")
            _logger.error("Tests will likely fail due to missing pytest!")

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

        # Fix astropy logging conflict with pytest warnings
        # This prevents "Cannot disable warnings logging" error
        env["PYTHONWARNINGS"] = "ignore"

        # Django-specific configuration
        if "django" in repo.lower():
            # Set Django settings module for pytest-django
            # Try to find actual test settings in the repo
            from pathlib import Path
            repo_path_obj = Path(repo_path) if isinstance(repo_path, str) else repo_path

            settings_candidates = [
                ("tests.test_sqlite", repo_path_obj / "tests" / "test_sqlite.py"),
                ("tests.settings", repo_path_obj / "tests" / "settings.py"),
                ("test_sqlite", repo_path_obj / "test_sqlite.py"),
            ]

            found_settings = None
            for module_name, file_path in settings_candidates:
                if file_path.exists():
                    found_settings = module_name
                    _logger.debug(f"Found Django test settings at: {file_path}")
                    break

            if found_settings:
                env["DJANGO_SETTINGS_MODULE"] = found_settings
                _logger.debug(f"Set DJANGO_SETTINGS_MODULE={env['DJANGO_SETTINGS_MODULE']}")
            else:
                # No settings found - use fallback but log warning
                env["DJANGO_SETTINGS_MODULE"] = "tests.test_sqlite"
                _logger.warning(f"Django test settings not found in {repo_path_obj}, using fallback: tests.test_sqlite")

        # If editable install failed, add repo to PYTHONPATH
        if (env_path / ".use_pythonpath").exists():
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{repo_path}:{existing_pythonpath}" if existing_pythonpath else str(repo_path)
            _logger.debug(f"Using PYTHONPATH for {repo}: {env['PYTHONPATH']}")

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
                       Also accepts unittest-style IDs which will be converted automatically.
            timeout: Timeout in seconds

        Returns:
            Dict with 'passed', 'failed', 'errors' counts and 'output'
        """
        repo_path = self.get_repo_path(repo)
        env_path = self.get_env_path(repo)

        # Verify environment is valid
        pip_path = env_path / "bin" / "pip"
        python_path = env_path / "bin" / "python"

        if not pip_path.exists() or not python_path.exists():
            error_msg = (
                f"Environment is broken for {repo}. "
                f"pip exists: {pip_path.exists()}, python exists: {python_path.exists()}. "
                f"Please recreate the environment by deleting: {env_path}"
            )
            _logger.error(error_msg)
            return {
                "success": False,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "returncode": -1,
                "output": error_msg,
            }

        # Verify pytest is available, install if missing
        pytest_check = subprocess.run(
            [str(python_path), "-m", "pytest", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if pytest_check.returncode != 0:
            _logger.warning("pytest not found in environment, installing it now...")
            try:
                subprocess.run(
                    [str(pip_path), "install", "pytest", "pytest-xdist"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                _logger.info("pytest installed successfully")
            except subprocess.CalledProcessError as e:
                _logger.error(f"Failed to install pytest: {e.stderr}")
                return {
                    "success": False,
                    "passed": 0,
                    "failed": 0,
                    "errors": 0,
                    "returncode": -1,
                    "output": f"pytest is not available and installation failed: {e.stderr}",
                }

        # Convert unittest-style test IDs to pytest format
        converted_tests = []
        for test_id in test_list:
            converted = convert_unittest_to_pytest(test_id, repo_path)
            converted_tests.append(converted)
            if converted != test_id:
                _logger.info(f"Converted test ID: {test_id} -> {converted}")

        # Build pytest command
        # -p no:warnings disables pytest's warnings plugin to avoid conflict with astropy's logger
        command = ["python", "-m", "pytest", "-xvs", "-p", "no:warnings"]

        # Django-specific flags
        if "django" in repo.lower():
            # Check if tests/runtests.py exists (Django's native test runner)
            django_test_runner = repo_path / "tests" / "runtests.py"
            if django_test_runner.exists():
                _logger.info(f"Django native test runner detected at {django_test_runner}")
                _logger.info("Consider using: python tests/runtests.py --settings=test_sqlite instead of pytest")
                # Disable pytest-django to avoid conflicts
                command.extend(["-p", "no:django"])
                _logger.info("Disabled pytest-django plugin (using -p no:django)")
            else:
                # Use pytest-django with Django-specific flags
                # --nomigrations: Don't run migrations (faster)
                # --reuse-db: Reuse test database between runs
                command.extend(["--nomigrations", "--reuse-db"])
                _logger.info("Added Django-specific pytest flags")

        command.extend(converted_tests)

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
