import subprocess

import pytest

from app.system.directory_chooser import DirectoryChooserError, MacOSDirectoryChooser


def test_macos_chooser_returns_the_selected_posix_path() -> None:
    calls = []

    def runner(arguments, **options):
        calls.append((arguments, options))
        return subprocess.CompletedProcess(arguments, 0, "/Users/demo/Downloads/\n", "")

    selected = MacOSDirectoryChooser(platform="darwin", runner=runner).choose()

    assert str(selected) == "/Users/demo/Downloads"
    assert calls[0][0][0:2] == ["/usr/bin/osascript", "-e"]
    assert calls[0][1] == {
        "capture_output": True,
        "text": True,
        "check": False,
    }


def test_macos_chooser_maps_user_cancellation() -> None:
    def runner(arguments, **options):
        return subprocess.CompletedProcess(arguments, 1, "", "User canceled. (-128)")

    with pytest.raises(DirectoryChooserError) as raised:
        MacOSDirectoryChooser(platform="darwin", runner=runner).choose()

    assert raised.value.code == "directory_selection_cancelled"
    assert raised.value.status_code == 409


def test_directory_chooser_rejects_unsupported_platforms() -> None:
    with pytest.raises(DirectoryChooserError) as raised:
        MacOSDirectoryChooser(platform="linux").choose()

    assert raised.value.code == "directory_chooser_unavailable"
    assert raised.value.status_code == 501
