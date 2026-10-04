"""Unit tests for Coding Workbench & Indexer."""

import pytest
from emily.coding.git_service import GitService
from emily.coding.indexer import RepositoryIndexer
from emily.coding.reviewer import CodeReviewEngine
from emily.coding.subsystem import CodingSubsystem


def test_repository_indexer(tmp_path):
    f_path = tmp_path / "sample.py"
    f_path.write_text("def hello():\n    print('world')\n", encoding="utf-8")

    indexer = RepositoryIndexer(tmp_path)
    files = indexer.index_workspace()
    assert len(files) == 1
    assert files[0].rel_path == "sample.py"
    assert len(files[0].symbols) == 1
    assert files[0].symbols[0].name == "hello"


def test_code_reviewer():
    reviewer = CodeReviewEngine()
    code_snippet = "def fn_no_doc():\n    pass\n"
    issues = reviewer.analyze_python_code(code_snippet)
    assert len(issues) == 1
    assert issues[0].code == "DOC001"


def test_git_service(tmp_path):
    git_srv = GitService(tmp_path)
    status = git_srv.get_status()
    assert status is not None


@pytest.mark.asyncio
async def test_coding_subsystem_lifecycle():
    subsystem = CodingSubsystem()

    class DummyCtx:
        pass

    await subsystem.start(DummyCtx())
    assert subsystem.indexer is not None
    await subsystem.stop(DummyCtx())
