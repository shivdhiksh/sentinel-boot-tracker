"""
Sentinel Safe File Operations Module:
Provides restricted, allowlisted filesystem handlers:
/find <filename>, /list <approved-folder>, /fileinfo <path>, /open <approved-folder>.
Enforces approved root boundaries, strict path traversal prevention,
metadata-only inspection, and interactive console checks for explorer launches.
"""
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from .config import BASE_DIR, logger, sanitize
from .command_auth import verify_interactive_session

# Canonical approved roots dictionary
def get_approved_roots() -> Dict[str, Path]:
    """Returns canonical, resolved paths for approved filesystem roots."""
    roots: Dict[str, Path] = {
        "project": BASE_DIR.resolve()
    }
    home = Path.home().resolve()
    
    desktop = (home / "Desktop").resolve()
    if desktop.exists():
        roots["desktop"] = desktop
        
    documents = (home / "Documents").resolve()
    if documents.exists():
        roots["documents"] = documents

    downloads = (home / "Downloads").resolve()
    if downloads.exists():
        roots["downloads"] = downloads

    return roots


def _resolve_safe_path(target_input: str, must_exist: bool = True, must_be_dir: bool = False) -> Tuple[bool, Optional[Path], str]:
    """
    Validates that a requested path strictly resides within an approved root.
    Prevents path traversal, directory escape, and arbitrary filesystem access.
    
    Returns:
        (is_valid, resolved_path, error_message)
    """
    raw = target_input.strip().strip('"').strip("'")
    if not raw:
        return False, None, "No path provided."

    # Immediate rejection of traversal tokens
    if ".." in raw.replace("\\", "/").split("/"):
        return False, None, "Path traversal ('..') detected and blocked."

    approved = get_approved_roots()
    target_path: Optional[Path] = None

    # Check for direct alias or alias prefix (e.g. "project", "desktop/subfolder")
    first_part = raw.replace("\\", "/").split("/")[0].lower()
    if first_part in approved:
        sub_path = raw[len(first_part):].lstrip("/\\")
        candidate = approved[first_part] / sub_path if sub_path else approved[first_part]
        target_path = candidate.resolve()
    else:
        # Check if raw is relative to project root or is an absolute path
        p = Path(raw)
        if not p.is_absolute():
            candidate = (BASE_DIR / p).resolve()
        else:
            candidate = p.resolve()
        target_path = candidate

    # Strict containment check against all approved roots
    is_contained = False
    for root in approved.values():
        try:
            if target_path.is_relative_to(root):
                is_contained = True
                break
        except AttributeError:
            # Fallback for Python < 3.9 compatibility (though 3.13 is used)
            try:
                target_path.relative_to(root)
                is_contained = True
                break
            except ValueError:
                continue

    if not is_contained:
        approved_names = ", ".join(f"<code>{k}</code>" for k in approved.keys())
        return False, None, f"Access denied. Path is outside approved roots ({approved_names})."

    if must_exist and not target_path.exists():
        return False, None, f"Path not found: <code>{sanitize(target_path.name)}</code>"

    if must_be_dir and not target_path.is_dir():
        return False, None, f"Path is not a directory: <code>{sanitize(target_path.name)}</code>"

    return True, target_path, ""


def _format_size(size_bytes: int) -> str:
    """Formats file size into human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def execute_find(filename_query: str) -> str:
    """
    Searches only approved roots for matching filenames with bounded depth and results.
    Prevents path traversal and unrestricted filesystem scanning.
    """
    query = filename_query.strip().strip('"').strip("'")
    if not query:
        return (
            "⚠️ <b>Usage:</b> <code>/find &lt;filename&gt;</code>\n"
            "Example: <code>/find error.log</code>\n"
            "Searches only inside approved roots."
        )

    # Filename query cannot contain path separators
    if "/" in query or "\\" in query or ".." in query:
        return "❌ Invalid search query: Please specify a filename only, without path separators."

    approved = get_approved_roots()
    matches: List[str] = []
    max_results = 15
    max_depth = 3
    skip_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", "venv", ".venv"}

    lower_query = query.lower()

    start_time = time.monotonic()
    max_search_seconds = 4.0

    for root_alias, root_path in approved.items():
        if len(matches) >= max_results or (time.monotonic() - start_time) > max_search_seconds:
            break
        if not root_path.exists() or not root_path.is_dir():
            continue

        try:
            for root_dir, dirs, files in os.walk(str(root_path)):
                if (time.monotonic() - start_time) > max_search_seconds:
                    break

                # Calculate relative depth
                rel_parts = Path(root_dir).relative_to(root_path).parts
                if len(rel_parts) >= max_depth:
                    dirs.clear()  # Don't recurse deeper
                    continue

                # Filter out noisy directories in-place
                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

                for f in files:
                    if lower_query in f.lower():
                        full_f = Path(root_dir) / f
                        rel_display = full_f.relative_to(root_path)
                        matches.append(f"[{root_alias}] {rel_display}")
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results or (time.monotonic() - start_time) > max_search_seconds:
                    break
        except Exception as exc:
            logger.warning(f"Error searching root {root_alias}: {sanitize(str(exc))}")

    lines = [
        f"🔍 <b>FIND RESULTS FOR:</b> <code>{sanitize(query)}</code>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    if matches:
        for m in matches:
            lines.append(f"• <code>{sanitize(m)}</code>")
        if len(matches) >= max_results:
            lines.append(f"\n⚠️ <i>Result limit ({max_results}) reached.</i>")
    else:
        lines.append("No matching files found within approved roots.")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def execute_list(folder_query: str) -> str:
    """
    Lists directory contents strictly inside approved roots.
    """
    raw = folder_query.strip()
    approved = get_approved_roots()

    if not raw:
        roots_desc = "\n".join(f"• <code>{k}</code>" for k in approved.keys())
        return (
            "📁 <b>APPROVED FOLDERS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{roots_desc}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Usage: <code>/list &lt;approved-folder&gt;</code>\n"
            "Example: <code>/list project</code> or <code>/list desktop</code>"
        )

    valid, folder_path, err = _resolve_safe_path(raw, must_exist=True, must_be_dir=True)
    if not valid or folder_path is None:
        return f"❌ {err}"

    try:
        entries = sorted(os.scandir(str(folder_path)), key=lambda e: (not e.is_dir(), e.name.lower()))
    except Exception as exc:
        return f"❌ Error reading directory: {sanitize(str(exc))}"

    lines = [
        f"📁 <b>DIRECTORY LISTING:</b> <code>{sanitize(folder_path.name)}</code>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    count = 0
    max_items = 25
    for entry in entries:
        if count >= max_items:
            lines.append(f"\n<i>... and {len(entries) - count} more items.</i>")
            break
        try:
            if entry.is_dir():
                lines.append(f"📁 <b>{sanitize(entry.name)}/</b>")
            else:
                size_str = _format_size(entry.stat().st_size)
                lines.append(f"📄 {sanitize(entry.name)} <code>({size_str})</code>")
            count += 1
        except Exception:
            continue

    if count == 0:
        lines.append("<i>Directory is empty.</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def execute_fileinfo(file_query: str) -> str:
    """
    Returns safe file metadata: name, directory, size, type, timestamps.
    Never exposes file contents, secrets, or environment variables.
    """
    raw = file_query.strip()
    if not raw:
        return (
            "ℹ️ <b>Usage:</b> <code>/fileinfo &lt;path&gt;</code>\n"
            "Example: <code>/fileinfo project/README.md</code>\n"
            "Returns safe metadata only (no file contents)."
        )

    valid, target_path, err = _resolve_safe_path(raw, must_exist=True, must_be_dir=False)
    if not valid or target_path is None:
        return f"❌ {err}"

    try:
        stat = target_path.stat()
        is_dir = target_path.is_dir()
        size_str = "Folder" if is_dir else _format_size(stat.st_size)
        ext = "Directory" if is_dir else (target_path.suffix.lower() or "None")

        created_dt = time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(stat.st_ctime))
        modified_dt = time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(stat.st_mtime))
    except Exception as exc:
        return f"❌ Error reading file metadata: {sanitize(str(exc))}"

    lines = [
        "📄 <b>FILE METADATA REPORT</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📝 <b>Name:</b> <code>{sanitize(target_path.name)}</code>",
        f"📁 <b>Parent:</b> <code>{sanitize(target_path.parent.name)}</code>",
        f"🏷️ <b>Type:</b> <code>{ext}</code>",
        f"📦 <b>Size:</b> <code>{size_str}</code>",
        f"📅 <b>Created:</b> {created_dt}",
        f"🔄 <b>Modified:</b> {modified_dt}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🔒 <i>Metadata only. File contents and secrets are not read or exposed.</i>"
    ]
    return "\n".join(lines)


def execute_open(folder_query: str) -> str:
    """
    Opens an explicitly approved folder in Windows Explorer within the interactive user session.
    Strictly verifies interactive console session, directory existence, and approved roots.
    Zero arbitrary shell execution.
    """
    # 1. Enforce active interactive user session
    valid_session, session_reason = verify_interactive_session()
    if not valid_session:
        return f"❌ Cannot open folder: {session_reason}"

    raw = folder_query.strip()
    approved = get_approved_roots()

    if not raw:
        roots_desc = ", ".join(f"<code>{k}</code>" for k in approved.keys())
        return (
            "📂 <b>Usage:</b> <code>/open &lt;approved-folder&gt;</code>\n"
            f"Available roots: {roots_desc}\n"
            "Example: <code>/open project</code> or <code>/open downloads</code>"
        )

    # 2. Strict directory and containment check
    valid, folder_path, err = _resolve_safe_path(raw, must_exist=True, must_be_dir=True)
    if not valid or folder_path is None:
        return f"❌ {err}"

    # 3. Safe launch via os.startfile without shell or executable execution
    try:
        os.startfile(str(folder_path))
        return f"📂 Opened approved folder in Explorer: <code>{sanitize(folder_path.name)}</code>"
    except Exception as exc:
        logger.error(f"execute_open failure: {sanitize(str(exc))}")
        return f"❌ Failed to open folder in Explorer: {sanitize(str(exc))}"
