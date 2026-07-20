from pathlib import Path
from uuid import uuid4

import pytest

from app.downloader.executor import DownloadExecutionError
from app.downloader.paths import (
    DownloadPathPolicy,
    choose_available_path,
    cleanup_orphaned_workspaces,
    cleanup_workspace,
    publish_file,
    sanitize_filename_stem,
)


def test_prepare_creates_task_scoped_staging_inside_authorized_root(
    tmp_path: Path,
) -> None:
    policy = DownloadPathPolicy(
        output_root=tmp_path / "downloads", temporary_root=tmp_path / "temporary"
    )

    workspace = policy.prepare(uuid4())

    assert workspace.staging_directory.is_dir()
    assert workspace.staging_directory.is_relative_to(policy.temporary_root)
    assert workspace.output_root == policy.output_root
    assert workspace.output_template.endswith("/media.%(ext)s")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("../secret/video", "secret video"),
        (" hello\x00:world.mp4 ", "hello world.mp4"),
        ("..", "video"),
        ("Título válido", "Título válido"),
    ],
)
def test_sanitize_filename_stem_removes_path_semantics(
    title: str, expected: str
) -> None:
    assert sanitize_filename_stem(title) == expected


def test_choose_available_path_never_overwrites(tmp_path: Path) -> None:
    (tmp_path / "Example.mp4").write_bytes(b"existing")
    (tmp_path / "Example (1).mp4").write_bytes(b"existing")

    selected = choose_available_path(tmp_path, "Example", "mp4")

    assert selected == tmp_path / "Example (2).mp4"
    assert not selected.exists()


def test_choose_available_path_rejects_extension_injection(tmp_path: Path) -> None:
    with pytest.raises(DownloadExecutionError):
        choose_available_path(tmp_path, "Example", "mp4/../../escape")


def test_publish_file_preserves_existing_output_and_cleans_workspace(
    tmp_path: Path,
) -> None:
    policy = DownloadPathPolicy(
        output_root=tmp_path / "downloads", temporary_root=tmp_path / "temporary"
    )
    workspace = policy.prepare(uuid4())
    (workspace.output_root / "Example.mp4").write_bytes(b"existing")
    source = workspace.staging_directory / "media.mp4"
    source.write_bytes(b"new")

    published = publish_file(source, workspace.output_root, "Example", "mp4")
    cleanup_workspace(workspace)

    assert (workspace.output_root / "Example.mp4").read_bytes() == b"existing"
    assert published.name == "Example (1).mp4"
    assert published.read_bytes() == b"new"
    assert not workspace.staging_directory.exists()


def test_startup_cleanup_removes_only_application_workspaces(tmp_path: Path) -> None:
    temporary_root = tmp_path / "temporary"
    temporary_root.mkdir()
    orphan = temporary_root / "efad5770-4246-4ffd-a8e7-26d286b63a5c-rw6gut1s"
    orphan.mkdir()
    (orphan / "media.mp4.part").write_bytes(b"partial")
    unrelated_directory = temporary_root / "keep-me"
    unrelated_directory.mkdir()
    unrelated_file = temporary_root / "notes.txt"
    unrelated_file.write_text("keep")
    external = tmp_path / "external"
    external.mkdir()
    symlink = temporary_root / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa-aaaaaaaa"
    symlink.symlink_to(external)

    removed = cleanup_orphaned_workspaces(temporary_root)

    assert removed == 1
    assert not orphan.exists()
    assert unrelated_directory.is_dir()
    assert unrelated_file.read_text() == "keep"
    assert symlink.is_symlink()
