import os
from pathlib import Path
from typing import Optional

DEFAULT_IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "vendor",
    "Pods",
    ".gradle",
    ".dart_tool",
}

DEFAULT_IGNORE_FILES = {
    ".DS_Store",
    ".gitignore",
    ".env",
    ".env.local",
    ".env.production",
}

DEFAULT_MAX_FILE_SIZE = 100 * 1024  # 100KB

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".7z",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
    ".pyo",
    ".class",
    ".jar",
    ".wasm",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".sqlite",
    ".db",
}


class RepoLoader:
    def __init__(
        self,
        repo_path: str,
        ignore_dirs: Optional[set] = None,
        ignore_files: Optional[set] = None,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    ):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Repo path not found: {self.repo_path}")
        if not self.repo_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.repo_path}")

        self.ignore_dirs = (
            ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
        )
        self.ignore_files = (
            ignore_files if ignore_files is not None else DEFAULT_IGNORE_FILES
        )
        self.max_file_size = max_file_size

    def _should_ignore_dir(self, name: str) -> bool:
        return name in self.ignore_dirs or name.startswith(".")

    def _should_ignore_file(self, name: str) -> bool:
        return name in self.ignore_files

    def _is_binary(self, filepath: Path) -> bool:
        return filepath.suffix.lower() in BINARY_EXTENSIONS

    def _read_file_content(self, filepath: Path) -> Optional[str]:
        if self._is_binary(filepath):
            return None
        if filepath.stat().st_size > self.max_file_size:
            return None
        try:
            return filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

    def get_tree(self) -> dict:
        result = {"name": self.repo_path.name, "type": "dir", "children": []}
        self._build_tree(self.repo_path, result)
        return result

    def _build_tree(self, current_path: Path, node: dict):
        try:
            entries = sorted(
                current_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            return

        for entry in entries:
            if entry.is_dir():
                if self._should_ignore_dir(entry.name):
                    continue
                child = {"name": entry.name, "type": "dir", "children": []}
                node["children"].append(child)
                self._build_tree(entry, child)
            elif entry.is_file():
                if self._should_ignore_file(entry.name):
                    continue
                node["children"].append(
                    {
                        "name": entry.name,
                        "type": "file",
                        "size": entry.stat().st_size,
                    }
                )

    def get_files(self) -> list[dict]:
        files = []
        self._collect_files(self.repo_path, files)
        return files

    def _collect_files(self, current_path: Path, files: list[dict]):
        try:
            entries = sorted(
                current_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            return

        for entry in entries:
            if entry.is_dir():
                if self._should_ignore_dir(entry.name):
                    continue
                self._collect_files(entry, files)
            elif entry.is_file():
                if self._should_ignore_file(entry.name):
                    continue
                content = self._read_file_content(entry)
                if content is not None:
                    relative_path = str(entry.relative_to(self.repo_path))
                    files.append(
                        {
                            "path": relative_path,
                            "content": content,
                            "size": entry.stat().st_size,
                            "extension": entry.suffix,
                        }
                    )

    def get_file_count(self) -> int:
        return len(self.get_files())

    def get_summary(self) -> dict:
        files = self.get_files()
        extensions = {}
        for f in files:
            ext = f["extension"] or "(no ext)"
            extensions[ext] = extensions.get(ext, 0) + 1

        return {
            "repo_name": self.repo_path.name,
            "repo_path": str(self.repo_path),
            "total_files": len(files),
            "extensions": extensions,
        }
