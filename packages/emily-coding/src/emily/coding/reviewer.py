"""Automated code review & refactoring suggestions engine."""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CodeReviewIssue:
    file_path: str
    line_no: int
    severity: str  # error, warning, info
    code: str
    message: str


@dataclass
class ReviewReport:
    health_score: float
    total_issues: int
    issues: list[CodeReviewIssue]


class CodeReviewEngine:
    """Performs static linting and automated code review checks."""

    def review_workspace(self, root_dir: Path | str = ".") -> ReviewReport:
        """Review workspace python files and compute workspace health score."""
        import os
        p = Path(root_dir)
        all_issues: list[CodeReviewIssue] = []
        if p.exists():
            for root, _, files in os.walk(p):
                for f in files:
                    if f.endswith(".py"):
                        fp = Path(root) / f
                        try:
                            code = fp.read_text(encoding="utf-8", errors="ignore")
                            rel_p = str(fp.relative_to(p)).replace("\\", "/")
                            all_issues.extend(self.analyze_python_code(code, file_path=rel_p))
                        except Exception:
                            pass
        score = max(0.0, 100.0 - len(all_issues) * 2)
        return ReviewReport(health_score=score, total_issues=len(all_issues), issues=all_issues)

    def analyze_python_code(self, code: str, file_path: str = "snippet.py") -> list[CodeReviewIssue]:
        """Analyze code for syntax errors, long functions, and missing docstrings."""
        issues: list[CodeReviewIssue] = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not ast.get_docstring(node):
                        issues.append(
                            CodeReviewIssue(
                                file_path=file_path,
                                line_no=node.lineno,
                                severity="info",
                                code="DOC001",
                                message=f"Function '{node.name}' is missing a docstring.",
                            )
                        )
                    body_len = len(node.body)
                    if body_len > 50:
                        issues.append(
                            CodeReviewIssue(
                                file_path=file_path,
                                line_no=node.lineno,
                                severity="warning",
                                code="CPLX001",
                                message=f"Function '{node.name}' has high statement count ({body_len} statements). Consider refactoring.",
                            )
                        )
        except SyntaxError as e:
            issues.append(
                CodeReviewIssue(
                    file_path=file_path,
                    line_no=e.lineno or 1,
                    severity="error",
                    code="SYNTAX_ERR",
                    message=f"Syntax Error: {e.msg}",
                )
            )
        return issues
