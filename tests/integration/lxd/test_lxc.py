import pathlib
import subprocess

import pytest


def test_project_default_cfg(lxc, project):
    default_cfg = lxc.profile_show(profile="default", project="default")
    expected_cfg = default_cfg.copy()
    expected_cfg["used_by"] = []
    lxc.profile_edit(profile="default", project=project, config=default_cfg)
    updated_cfg = lxc.profile_show(profile="default", project=project)
    assert updated_cfg == expected_cfg


def test_exec(instance, lxc, project):
    proc = lxc.exec(
        instance=instance,
        command=["echo", "this is a test"],
        project=project,
        capture_output=True,
    )

    assert proc.stdout == b"this is a test\n"


def test_delete(instance, lxc, project):
    with pytest.raises(subprocess.CalledProcessError):
        lxc.delete(instance=instance, force=False, project=project)

    lxc.stop(instance=instance, project=project)
    lxc.delete(instance=instance, force=False, project=project)

    instances = lxc.list(project=project)
    assert instances == []


def test_delete_force(instance, lxc, project):
    lxc.delete(instance=instance, force=True, project=project)

    instances = lxc.list(project=project)
    assert instances == []


def test_image_copy(lxc, project):
    lxc.image_copy(
        image="16.04",
        image_remote="ubuntu",
        alias="test-1604",
        project=project,
    )

    images = lxc.image_list(project=project)
    assert len(images) == 1


def test_image_delete(lxc, project):
    lxc.image_copy(
        image="16.04",
        image_remote="ubuntu",
        alias="test-1604",
        project=project,
    )

    lxc.image_delete(image="test-1604", project=project)

    images = lxc.image_list(project=project)
    assert images == []


def test_file_push(instance, lxc, project, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    lxc.file_push(
        instance=instance,
        project=project,
        source=test_file,
        destination=pathlib.Path("/tmp/foo"),
    )

    proc = lxc.exec(
        command=["cat", "/tmp/foo"],
        instance=instance,
        project=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    assert proc.stdout == b"this is a test"


def test_file_pull(instance, lxc, project, tmp_path):
    out_path = tmp_path / "out.txt"
    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    lxc.file_push(
        instance=instance,
        project=project,
        source=test_file,
        destination=pathlib.Path("/tmp/foo"),
    )

    lxc.file_pull(
        instance=instance,
        project=project,
        source=pathlib.Path("/tmp/foo"),
        destination=out_path,
    )

    assert out_path.read_text() == "this is a test"
