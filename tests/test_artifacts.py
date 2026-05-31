from sophia.adapters.artifacts import artifacts_from_tool_uses


def test_extracts_write_and_edit():
    tus = [
        {"name": "Write", "input": {"file_path": "/a/new.txt", "content": "x"}},
        {"name": "Edit", "input": {"file_path": "/a/old.txt"}},
    ]
    arts = artifacts_from_tool_uses(tus)
    by = {a["path"]: a for a in arts}
    assert by["/a/new.txt"]["status"] == "created"
    assert by["/a/old.txt"]["status"] == "modified"


def test_ignores_read_only_tools():
    tus = [
        {"name": "Read", "input": {"file_path": "/a/x.txt"}},
        {"name": "Grep", "input": {"pattern": "foo"}},
        {"name": "Bash", "input": {"command": "ls"}},
    ]
    assert artifacts_from_tool_uses(tus) == []


def test_dedupes_by_path_created_wins():
    # 같은 파일을 Write 후 Edit → 'created' 유지(생성이 핵심 사실)
    tus = [
        {"name": "Write", "input": {"file_path": "/a/f.txt"}},
        {"name": "Edit", "input": {"file_path": "/a/f.txt"}},
    ]
    arts = artifacts_from_tool_uses(tus)
    assert len(arts) == 1
    assert arts[0]["status"] == "created"


def test_edit_then_edit_stays_modified():
    tus = [
        {"name": "Edit", "input": {"file_path": "/a/f.txt"}},
        {"name": "MultiEdit", "input": {"file_path": "/a/f.txt"}},
    ]
    arts = artifacts_from_tool_uses(tus)
    assert len(arts) == 1 and arts[0]["status"] == "modified"


def test_notebook_path_key():
    tus = [{"name": "NotebookEdit", "input": {"notebook_path": "/a/n.ipynb"}}]
    arts = artifacts_from_tool_uses(tus)
    assert arts[0]["path"] == "/a/n.ipynb"


def test_missing_path_is_skipped():
    tus = [{"name": "Write", "input": {"content": "no path here"}}]
    assert artifacts_from_tool_uses(tus) == []
