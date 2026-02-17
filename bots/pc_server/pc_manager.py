"""PC Manager - Core functionality for PC sidecar operations."""

import logging
import subprocess  # nosec B404
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PCManager:
    """Manager for PC sidecar operations."""

    def __init__(self, root_dir: str = "/pc"):
        """Initialize PC manager with root directory.

        Args:
            root_dir: Root directory for PC operations
        """
        self.root = Path(root_dir)
        self.files_dir = self.root / "files"
        self.log_dir = self.root / "logs"

        for directory in [self.files_dir, self.log_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def exists(self, path: str) -> bool:
        """Check if a path exists.

        Args:
            path: Path to check (can be absolute or relative to root)

        Returns:
            True if path exists, False otherwise
        """
        try:
            p = Path(path)
            if not p.is_absolute():
                p = self.root / path
            return p.exists()
        except Exception:
            return False

    def list_files(self, directory: str = "") -> List[Dict[str, Any]]:
        """List files in a directory.

        Args:
            directory: Subdirectory path relative to files_dir

        Returns:
            List of file info dictionaries
        """
        target_dir = self.files_dir / directory
        if not target_dir.exists():
            return []

        files = []
        try:
            for item in target_dir.iterdir():
                files.append(
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else 0,
                        "modified": item.stat().st_mtime,
                    }
                )
        except Exception as e:
            logger.error(f"Failed to list files: {e}")

        return files

    def read_file(self, path: str) -> Optional[str]:
        """Read a file's content.

        Args:
            path: File path relative to files_dir

        Returns:
            File content as string, or None if file not found
        """
        file_path = self.files_dir / path
        try:
            if file_path.exists() and file_path.is_file():
                with open(file_path, "r") as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
        return None

    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file.

        Args:
            path: File path relative to files_dir
            content: Content to write

        Returns:
            True if write succeeded, False otherwise
        """
        file_path = self.files_dir / path
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            return False

    def delete_file(self, path: str) -> bool:
        """Delete a file.

        Args:
            path: File or directory path relative to files_dir

        Returns:
            True if deletion succeeded, False otherwise
        """
        file_path = self.files_dir / path
        try:
            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                else:
                    import shutil

                    shutil.rmtree(file_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
        return False

    def execute_command(
        self, command: str, timeout: int = 30, cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a shell command.

        Args:
            command: Shell command to execute
            timeout: Maximum execution time in seconds
            cwd: Working directory for command execution

        Returns:
            Dict with success status, return_code, stdout, stderr, and command

        Raises:
            ValueError: If command contains dangerous patterns
            TimeoutError: If command execution times out
            RuntimeError: If command execution fails
        """
        if cwd is None:
            cwd = str(self.files_dir)

        dangerous_patterns = [
            "rm -rf /",
            "mkfs",
            "dd if=",
            ":(){ :|:& };:",
            "chmod 777 /",
        ]
        for pattern in dangerous_patterns:
            if pattern in command:
                raise ValueError(f"Dangerous command blocked: {pattern}")

        logger.info(f"Executing command: {command} in {cwd}")

        try:
            process = subprocess.run(
                command,
                shell=True,  # nosec B602
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "command": command,
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"Command timed out: {command}")
            raise TimeoutError(f"Command timed out: {command}")
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise RuntimeError(f"Command execution failed: {e}")
