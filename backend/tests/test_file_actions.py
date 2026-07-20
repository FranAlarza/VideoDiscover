from pathlib import Path

import pytest

from app.system.file_actions import DownloadFileActionError, DownloadFileActionService


def test_file_actions_open_and_reveal_a_contained_file(tmp_path: Path) -> None:
    output_root = tmp_path / "downloads"
    output_root.mkdir()
    output_file = output_root / "Example.mp4"
    output_file.write_bytes(b"video")
    calls: list[list[str]] = []
    service = DownloadFileActionService(
        output_root, launcher=calls.append, platform="darwin"
    )

    service.open(output_file.name)
    service.reveal(output_file.name)

    assert calls == [
        ["/usr/bin/open", "--", str(output_file)],
        ["/usr/bin/open", "-R", "--", str(output_file)],
    ]


def test_file_actions_use_the_result_original_directory(tmp_path: Path) -> None:
    current_root = tmp_path / "current"
    historical_root = tmp_path / "historical"
    current_root.mkdir()
    historical_root.mkdir()
    output_file = historical_root / "Example.mp4"
    output_file.write_bytes(b"video")
    calls: list[list[str]] = []
    service = DownloadFileActionService(
        current_root, launcher=calls.append, platform="darwin"
    )

    service.open(output_file.name, str(historical_root))

    assert calls == [["/usr/bin/open", "--", str(output_file)]]


def test_file_actions_reject_a_missing_file(tmp_path: Path) -> None:
    service = DownloadFileActionService(
        tmp_path, launcher=lambda _: None, platform="darwin"
    )

    with pytest.raises(DownloadFileActionError) as raised:
        service.open("missing.mp4")

    assert raised.value.code == "download_file_missing"
    assert raised.value.status_code == 404


def test_file_actions_reject_paths_outside_the_output_root(tmp_path: Path) -> None:
    output_root = tmp_path / "downloads"
    output_root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"video")
    service = DownloadFileActionService(
        output_root, launcher=lambda _: None, platform="darwin"
    )

    with pytest.raises(DownloadFileActionError) as raised:
        service.open("../outside.mp4")

    assert raised.value.code == "unsafe_output_path"
    assert raised.value.status_code == 409


def test_file_actions_reject_a_symlink_escaping_the_output_root(tmp_path: Path) -> None:
    output_root = tmp_path / "downloads"
    output_root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"video")
    (output_root / "linked.mp4").symlink_to(outside)
    service = DownloadFileActionService(
        output_root, launcher=lambda _: None, platform="darwin"
    )

    with pytest.raises(DownloadFileActionError) as raised:
        service.reveal("linked.mp4")

    assert raised.value.code == "unsafe_output_path"
