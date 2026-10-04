"""AST and File Structure Indexer for Emily OS Coding Workbench."""

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CodeSymbol:
    name: str
    symbol_type: str  # class, function, method, variable
    line_no: int
    docstring: str | None = None


@dataclass
class IndexedFile:
    rel_path: str
    file_type: str
    line_count: int
    symbols: list[CodeSymbol] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rel_path": self.rel_path,
            "file_type": self.file_type,
            "line_count": self.line_count,
            "symbol_count": len(self.symbols),
            "symbols": [{"name": s.name, "type": s.symbol_type, "line": s.line_no} for s in self.symbols],
        }


class RepositoryIndexer:
    """Indexes source code files, line counts, and Python AST symbols."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir)

    def index_workspace(self) -> list[IndexedFile]:
        """Scan workspace and parse Python AST symbols."""
        results: list[IndexedFile] = []
        if not self.root_dir.exists():
            return results

        for root, dirs, files in os.walk(self.root_dir):
            # Skip hidden and cache dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"venv", ".venv", "__pycache__"}]
            for f in files:
                if f.endswith((".py", ".ts", ".tsx", ".js", ".json", ".toml", ".md")):
                    full_p = Path(root) / f
                    rel_p = str(full_p.relative_to(self.root_dir)).replace("\\", "/")
                    file_info = self.index_file(full_p, rel_p)
                    results.append(file_info)
        return results

    def index_file(self, full_path: Path, rel_path: str) -> IndexedFile:
        """Index a single file and parse AST if Python."""
        ext = full_path.suffix.lstrip(".")
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            symbols: list[CodeSymbol] = []

            if ext == "py":
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            symbols.append(
                                CodeSymbol(
                                    name=node.name,
                                    symbol_type="class",
                                    line_no=node.lineno,
                                    docstring=ast.get_docstring(node),
                                )
                            )
                        elif isinstance(node, ast.FunctionDef):
                            symbols.append(
                                CodeSymbol(
                                    name=node.name,
                                    symbol_type="function",
                                    line_no=node.lineno,
                                    docstring=ast.get_docstring(node),
                                )
                            )
                except SyntaxError:
                    pass

            return IndexedFile(
                rel_path=rel_path,
                file_type=ext,
                line_count=len(lines),
                symbols=symbols,
            )
        except Exception:
            return IndexedFile(rel_path=rel_path, file_type=ext, line_count=0, symbols=[])
