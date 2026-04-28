import ast
import json
import os
import re
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
        focus_path: Optional[str] = None,
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

        # Normalise focus_path to a forward-slash relative path prefix
        if focus_path:
            fp = Path(focus_path)
            # If absolute and inside repo, make relative; otherwise use as-is
            try:
                fp = fp.relative_to(self.repo_path)
            except ValueError:
                pass
            self.focus_prefix: Optional[str] = fp.as_posix().rstrip("/") + "/"
        else:
            self.focus_prefix = None

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

    # ------------------------------------------------------------------ #
    # Entry-chain ranked file selection                                    #
    # ------------------------------------------------------------------ #

    _ENTRY_NAME_STEMS = {
        "main", "index", "app", "server", "cli", "cmd",
        "entry", "start", "run", "manage", "wsgi", "asgi",
    }
    _ENTRY_CONTENT_PATTERNS = [
        re.compile(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]'),  # Python
        re.compile(r'\.listen\s*\('),                              # Node HTTP server
        re.compile(r'app\.run\s*\('),                              # Flask / Express
    ]

    def get_files_ranked(self, max_files: int = 50) -> list[dict]:
        """Return files sorted by entry-chain importance.

        When focus_path is set, files inside that subtree are ranked first
        (using their own entry-chain), then global files fill remaining slots.

        Priority order:
          1. Entry point files (focus subtree first, then global)
          2. Files directly imported by entry points (depth 1)
          3. Files imported at depth 2
          4. Files imported at depth 3
          5. Remaining files sorted by import frequency (most-imported first)
        """
        all_files = self.get_files()
        if len(all_files) <= max_files:
            return all_files

        file_by_path: dict[str, dict] = {f["path"]: f for f in all_files}
        all_paths: set[str] = set(file_by_path.keys())

        if self.focus_prefix:
            focus_files = [f for f in all_files if f["path"].startswith(self.focus_prefix)]
            other_files = [f for f in all_files if not f["path"].startswith(self.focus_prefix)]
            focus_budget = max(int(max_files * 0.7), min(max_files, len(focus_files)))
            other_budget = max_files - focus_budget
            focus_ranked = self._rank_by_entry_chain(focus_files, file_by_path, all_paths, focus_budget)
            other_ranked = self._rank_by_entry_chain(other_files, file_by_path, all_paths, other_budget)
            return focus_ranked + other_ranked

        return self._rank_by_entry_chain(all_files, file_by_path, all_paths, max_files)

    def _rank_by_entry_chain(
        self,
        candidate_files: list[dict],
        file_by_path: dict[str, dict],
        all_paths: set[str],
        max_files: int,
    ) -> list[dict]:
        """Core BFS ranking: entry points → import chain → import frequency."""
        if not candidate_files:
            return []

        candidate_paths = {f["path"] for f in candidate_files}

        import_graph: dict[str, set[str]] = {}
        import_frequency: dict[str, int] = {}
        for f in candidate_files:
            deps = self._extract_imports(f["path"], f.get("content") or "", all_paths)
            local_deps = deps & candidate_paths
            import_graph[f["path"]] = local_deps
            for dep in local_deps:
                import_frequency[dep] = import_frequency.get(dep, 0) + 1

        entry_paths = self._find_entry_points(candidate_files, candidate_paths)

        ranked: list[dict] = []
        visited: set[str] = set()

        current_level = [p for p in entry_paths if p in file_by_path]
        for path in current_level:
            if path not in visited:
                ranked.append(file_by_path[path])
                visited.add(path)

        for _ in range(3):
            if len(ranked) >= max_files:
                break
            next_level: list[str] = []
            for path in current_level:
                for dep in import_graph.get(path, set()):
                    if dep not in visited and dep in file_by_path:
                        ranked.append(file_by_path[dep])
                        visited.add(dep)
                        next_level.append(dep)
            current_level = next_level

        remaining = sorted(
            [f for f in candidate_files if f["path"] not in visited],
            key=lambda f: import_frequency.get(f["path"], 0),
            reverse=True,
        )
        ranked.extend(remaining)

        return ranked[:max_files]

    def _find_entry_points(self, files: list[dict], all_paths: set[str]) -> list[str]:
        """Identify likely entry point files."""
        entries: list[str] = []
        seen: set[str] = set()

        # 1. Files whose stem matches entry name patterns
        for f in files:
            stem = Path(f["path"]).stem.lower()
            if stem in self._ENTRY_NAME_STEMS:
                if f["path"] not in seen:
                    entries.append(f["path"])
                    seen.add(f["path"])

        # 2. Files containing entry-point content patterns
        for f in files:
            if f["path"] in seen:
                continue
            content = f.get("content") or ""
            for pat in self._ENTRY_CONTENT_PATTERNS:
                if pat.search(content):
                    entries.append(f["path"])
                    seen.add(f["path"])
                    break

        # 3. package.json bin/main fields
        for f in files:
            if not f["path"].endswith("package.json"):
                continue
            try:
                pkg = json.loads(f.get("content") or "{}")
                for field in ("main", "module"):
                    target = pkg.get(field)
                    if isinstance(target, str):
                        resolved = self._resolve_js_path(target, f["path"], all_paths)
                        if resolved and resolved not in seen:
                            entries.append(resolved)
                            seen.add(resolved)
                bin_field = pkg.get("bin")
                if isinstance(bin_field, str):
                    resolved = self._resolve_js_path(bin_field, f["path"], all_paths)
                    if resolved and resolved not in seen:
                        entries.append(resolved)
                        seen.add(resolved)
                elif isinstance(bin_field, dict):
                    for target in bin_field.values():
                        resolved = self._resolve_js_path(target, f["path"], all_paths)
                        if resolved and resolved not in seen:
                            entries.append(resolved)
                            seen.add(resolved)
            except (json.JSONDecodeError, Exception):
                pass

        return entries

    def _extract_imports(self, filepath: str, content: str, all_paths: set[str]) -> set[str]:
        """Extract local file dependencies from a source file."""
        ext = Path(filepath).suffix.lower()
        if ext == ".py":
            return self._extract_python_imports(filepath, content, all_paths)
        if ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            return self._extract_js_imports(filepath, content, all_paths)
        return set()

    def _extract_python_imports(self, filepath: str, content: str, all_paths: set[str]) -> set[str]:
        result: set[str] = set()
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return result

        pkg_dir = str(Path(filepath).parent)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_python_module(alias.name, None, filepath, all_paths)
                    if resolved:
                        result.add(resolved)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    resolved = self._resolve_python_module(
                        node.module, node.level, filepath, all_paths
                    )
                    if resolved:
                        result.add(resolved)

        return result

    def _resolve_python_module(
        self,
        module: str,
        level: Optional[int],
        current_file: str,
        all_paths: set[str],
    ) -> Optional[str]:
        """Resolve a Python module name to a file path within the repo."""
        parts = module.split(".")

        if level:
            # Relative import: go up `level` directories from current file
            base = Path(current_file).parent
            for _ in range(level - 1):
                base = base.parent
            candidate_parts = list(base.parts) + parts
        else:
            candidate_parts = parts

        # Try as package (dir/__init__.py) then as module (.py)
        as_module = "/".join(candidate_parts) + ".py"
        as_init = "/".join(candidate_parts) + "/__init__.py"

        # Strip repo root prefix if present
        for candidate in (as_module, as_init):
            # Try relative to repo root
            if candidate in all_paths:
                return candidate
            # Try stripping common prefixes (src/, lib/)
            for prefix in ("src/", "lib/"):
                stripped = candidate[len(prefix):] if candidate.startswith(prefix) else None
                if stripped and stripped in all_paths:
                    return stripped

        return None

    _JS_IMPORT_RE = re.compile(
        r'(?:import|export).*?from\s+[\'"]([^\'"\s]+)[\'"]'
        r'|require\s*\(\s*[\'"]([^\'"\s]+)[\'"]\s*\)'
        r'|import\s*\(\s*[\'"]([^\'"\s]+)[\'"]\s*\)',
        re.MULTILINE,
    )

    def _extract_js_imports(self, filepath: str, content: str, all_paths: set[str]) -> set[str]:
        result: set[str] = set()
        for match in self._JS_IMPORT_RE.finditer(content):
            target = match.group(1) or match.group(2) or match.group(3)
            if not target or not target.startswith("."):
                continue  # skip node_modules imports
            resolved = self._resolve_js_path(target, filepath, all_paths)
            if resolved:
                result.add(resolved)
        return result

    def _resolve_js_path(self, target: str, current_file: str, all_paths: set[str]) -> Optional[str]:
        """Resolve a JS/TS relative import to a repo file path."""
        base = Path(current_file).parent
        candidate = (base / target).resolve()
        # Make relative to repo root
        try:
            rel = candidate.relative_to(self.repo_path)
        except ValueError:
            return None

        rel_str = str(rel)

        # Try exact path first
        if rel_str in all_paths:
            return rel_str

        # Try with common extensions
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
            with_ext = rel_str + ext
            if with_ext in all_paths:
                return with_ext
            # Try index file
            index = rel_str + "/index" + ext
            if index in all_paths:
                return index

        return None
