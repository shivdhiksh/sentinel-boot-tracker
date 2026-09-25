"""
Unit and Real E2E tests for sentinel.file_actions.
Labels: REAL E2E / UNIT
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sentinel.file_actions import (
    get_approved_roots,
    _resolve_safe_path,
    execute_find,
    execute_list,
    execute_fileinfo,
    execute_open
)

def test_approved_roots():
    """[UNIT] Verifies approved roots mapping contains project root and exists."""
    roots = get_approved_roots()
    assert "project" in roots
    assert roots["project"].exists()
    assert roots["project"].is_dir()

def test_path_traversal_prevention_unit():
    """[UNIT] Verifies strict rejection of directory traversal and outside access."""
    # Direct traversal tokens
    valid, _, err = _resolve_safe_path("../../Windows")
    assert valid is False
    assert "traversal" in err.lower()

    valid, _, err = _resolve_safe_path("..")
    assert valid is False

    valid, _, err = _resolve_safe_path("project/../../../Windows/System32")
    assert valid is False

    # Absolute path outside approved roots
    valid, _, err = _resolve_safe_path(r"C:\Windows\System32\cmd.exe")
    assert valid is False
    assert "outside approved roots" in err

def test_find_real_e2e():
    """[REAL E2E] Verifies /find locates a known file within approved roots."""
    res = execute_find("README.md")
    assert "FIND RESULTS FOR:" in res
    assert "[project] README.md" in res

def test_find_empty_or_invalid_unit():
    """[UNIT] Verifies argument validation for /find."""
    empty_out = execute_find("")
    assert "Usage:" in empty_out

    slash_out = execute_find("folder/file.txt")
    assert "Invalid search query" in slash_out

    traversal_out = execute_find("../secret.txt")
    assert "Invalid search query" in traversal_out

def test_find_bounded_time_unit():
    """[UNIT] Verifies /find search terminates cleanly when search time bound is reached."""
    # Force monotonic time to jump forward simulating search timeout
    with patch("sentinel.file_actions.time.monotonic", side_effect=[0.0, 10.0, 10.0, 10.0, 10.0]):
        res = execute_find("test")
        assert "FIND RESULTS FOR:" in res

def test_list_approved_folder_real_e2e():
    """[REAL E2E] Verifies /list enumerates approved folder contents."""
    res = execute_list("project")
    assert "DIRECTORY LISTING:" in res
    assert "README.md" in res

def test_list_empty_query_shows_approved_folders_unit():
    """[UNIT] Verifies /list without arguments outputs approved roots reference."""
    res = execute_list("")
    assert "APPROVED FOLDERS" in res
    assert "project" in res

def test_list_unapproved_or_traversal_unit():
    """[UNIT] Verifies /list blocks traversal and unapproved folders."""
    res = execute_list("../../Windows")
    assert "❌" in res

    res2 = execute_list("C:/Windows")
    assert "❌ Access denied" in res2

def test_fileinfo_real_e2e():
    """[REAL E2E] Verifies /fileinfo returns safe metadata without exposing contents."""
    res = execute_fileinfo("project/README.md")
    assert "FILE METADATA REPORT" in res
    assert "Name:" in res
    assert "README.md" in res
    assert "Parent:" in res
    assert "Size:" in res
    assert "Created:" in res
    assert "Modified:" in res
    assert "Metadata only" in res

def test_fileinfo_nonexistent_file_unit():
    """[UNIT] Verifies /fileinfo handles non-existent file gracefully."""
    res = execute_fileinfo("project/nonexistent_file_xyz123.txt")
    assert "❌ Path not found" in res

def test_open_interactive_session_gate_unit():
    """[UNIT] Verifies /open rejects when interactive console session is unavailable."""
    with patch("sentinel.file_actions.verify_interactive_session", return_value=(False, "Session 0 restricted")):
        res = execute_open("project")
        assert "❌ Cannot open folder: Session 0 restricted" in res

def test_open_approved_folder_unit():
    """[UNIT] Verifies /open invokes os.startfile on approved folder in interactive session."""
    with patch("sentinel.file_actions.verify_interactive_session", return_value=(True, "")), \
         patch("sentinel.file_actions.os.startfile") as mock_startfile:
        res = execute_open("project")
        assert "📂 Opened approved folder in Explorer" in res
        assert mock_startfile.called

def test_open_regular_file_rejected_unit():
    """[UNIT] Verifies /open rejects regular files or executables (folders only)."""
    with patch("sentinel.file_actions.verify_interactive_session", return_value=(True, "")):
        res = execute_open("project/README.md")
        assert "❌ Path is not a directory" in res
