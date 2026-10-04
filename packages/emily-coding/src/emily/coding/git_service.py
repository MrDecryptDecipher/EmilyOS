"""Git status, commit, and diff service for Emily Coding Workbench."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GitStatus:
    branch: str
    clean: bool
    modified_files: list[str]
    untracked_files: list[str]


class GitService:
    """Wrapper for local Git interactions."""

    def __init__(self, repo_path: Path | str) -> None:
        self.repo_path = Path(repo_path)

    def get_status(self) -> GitStatus:
        """Inspect repository status."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            lines = res.stdout.splitlines()
            branch = "main"
            modified: list[str] = []
            untracked: list[str] = []

            for line in lines:
                if line.startswith("##"):
                    branch = line[3:].split("...")[0].strip()
                elif line.startswith(" M") or line.startswith("M "):
                    modified.append(line[3:].strip())
                elif line.startswith("??"):
                    untracked.append(line[3:].strip())

            return GitStatus(
                branch=branch,
                clean=(len(modified) == 0 and len(untracked) == 0),
                modified_files=modified,
                untracked_files=untracked,
            )
        except Exception:
            return GitStatus(branch="unknown", clean=True, modified_files=[], untracked_files=[])

    def get_diff(self, file_path: str | None = None) -> str:
        """Fetch current git diff."""
        cmd = ["git", "diff"]
        if file_path:
            cmd.append(file_path)
        try:
            res = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, timeout=5)
            return res.stdout
        except Exception as e:
            return f"Error fetching diff: {e}"
