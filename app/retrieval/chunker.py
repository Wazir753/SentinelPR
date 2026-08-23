"""AST-based Python chunking at function and class boundaries."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CodeChunk:
    file_path: str
    chunk_type: str
    name: str
    start_line: int
    end_line: int
    source: str


def _extract_node_source(source_lines: list[str], node: ast.AST) -> str:
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    return "\n".join(source_lines[start:end])


def chunk_python_file(file_path: Path, repo_root: Path) -> list[CodeChunk]:
    relative = file_path.relative_to(repo_root).as_posix()
    source_text = file_path.read_text(encoding="utf-8")
    source_lines = source_text.splitlines()
    tree = ast.parse(source_text, filename=str(file_path))

    chunks: list[CodeChunk] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chunks.append(
                CodeChunk(
                    file_path=relative,
                    chunk_type="class" if isinstance(node, ast.ClassDef) else "function",
                    name=node.name,
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    source=_extract_node_source(source_lines, node),
                )
            )
    return chunks


def chunk_repository(repo_root: Path) -> list[CodeChunk]:
    repo_root = repo_root.resolve()
    all_chunks: list[CodeChunk] = []
    for py_file in sorted(repo_root.rglob("*.py")):
        if any(part.startswith(".") for part in py_file.relative_to(repo_root).parts):
            continue
        if py_file.name.startswith("test_") or py_file.name == "conftest.py":
            continue
        try:
            all_chunks.extend(chunk_python_file(py_file, repo_root))
        except SyntaxError as exc:
            logger.warning("Skipping unparseable file %s: %s", py_file, exc)
    return all_chunks
