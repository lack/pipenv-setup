import contextlib
import os
import shutil
from os.path import dirname
from pathlib import Path
from typing import Optional, List

import pytest

from pipenv_setup import setup_parser, msg_formatter, main
from pipenv_setup.main import cmd

data_path = Path(dirname(__file__)) / "data"


@contextlib.contextmanager
def working_directory(path):
    prev_cwd = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(prev_cwd)


def copy_pipfiles(src_dir: Path, target_dir: Path):
    for f in src_dir.glob("Pipfile*"):
        shutil.copy(str(f), str(target_dir))


def copy_files(src_dir: Path, target_dir: Path):
    for f in src_dir.glob("*"):
        shutil.copy(str(f), str(target_dir))


def copy_file(file: Path, target_dir: Path, new_name: Optional[str] = None):
    new_file = target_dir / file.name
    if new_name is not None:
        new_file = target_dir / new_name
    shutil.copy(str(file), str(new_file))


def compare_list_of_string_kw_arg(
    setup_text_a: str, setup_text_b: str, kw_name: str, ordering_matters: bool = True
) -> bool:
    """
    :return: whether these two setup files has the same keyword argument of type list of strings (element order can not be different)
    :raise ValueError TypeError: if failed to get a list of strings
    """
    args_a = setup_parser.get_kw_list_of_string_arg(setup_text_a, kw_name)
    args_b = setup_parser.get_kw_list_of_string_arg(setup_text_b, kw_name)
    if ordering_matters:
        return args_a == args_b
    else:
        return set(args_a) == set(args_b)


@pytest.mark.parametrize(("source_pipfile_dirname",), [("nasty_0",)])
def test_generation(tmp_path, shared_datadir, source_pipfile_dirname: str):
    """
    test boilerplate
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    copy_pipfiles(pipfile_dir, tmp_path)
    with working_directory(tmp_path):
        cmd(argv=["", "sync"])
    generated_setup = tmp_path / "setup.py"
    assert generated_setup.exists()
    generated_setup_text = generated_setup.read_text()
    expected_setup_text = (pipfile_dir / "setup.py").read_text()
    for kw_arg_names in ("install_requires", "dependency_links"):

        assert compare_list_of_string_kw_arg(
            generated_setup_text,
            expected_setup_text,
            kw_arg_names,
            ordering_matters=False,
        )


@pytest.mark.parametrize(
    ("source_pipfile_dirname", "update_count"),
    [("nasty_0", 23), ("no_original_kws_0", 23)],
)
def test_update(
    capsys, tmp_path, shared_datadir, source_pipfile_dirname: str, update_count
):
    """
    test updating setup.py (when it already exists)
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ("Pipfile", "Pipfile.lock", "setup.py"):
        copy_file(pipfile_dir / filename, tmp_path)
    with working_directory(tmp_path):
        cmd(argv=[..., "sync"])
    generated_setup = tmp_path / "setup.py"
    assert generated_setup.exists()
    generated_setup_text = generated_setup.read_text()
    expected_setup_text = (shared_datadir / "setup.py").read_text()
    for kw_arg_names in ("install_requires", "dependency_links"):

        assert compare_list_of_string_kw_arg(
            generated_setup_text,
            expected_setup_text,
            kw_arg_names,
            ordering_matters=False,
        )
    captured = capsys.readouterr()
    assert msg_formatter.update_success(update_count) in captured.out


@pytest.mark.parametrize(("source_pipfile_dirname",), [("nasty_0",)])
@pytest.mark.parametrize(
    ("missing_filenames",),
    [
        [["Pipfile"]],
        [["Pipfile", "Pipfile.lock"]],
        [["Pipfile.lock", "setup.py"]],
        [["Pipfile", "setup.py"]],
    ],
)
def test_sync_file_missing_exit_code(
    capfd,
    tmp_path,
    shared_datadir,
    source_pipfile_dirname: str,
    missing_filenames: List[str],
):
    """
    when Pipfile.lock is missing, return code should be one
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ["Pipfile", "Pipfile.lock", "setup.py"]:
        file = pipfile_dir / filename
        if filename not in missing_filenames:
            copy_file(file, tmp_path)
    # copy_file(shared_datadir / "minimal_empty_setup.py", tmp_path, "setup.py")
    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=[..., "sync"])
        assert e.value.code == 1


# fixme: capfd can not capture stderr on windows or ubuntu. How?? stderr is always empty for me
@pytest.mark.xfail
@pytest.mark.parametrize(("source_pipfile_dirname",), [("nasty_0",)])
def test_sync_lock_file_missing_messages(
    capfd, tmp_path, shared_datadir, source_pipfile_dirname: str
):
    """
    when pipfile is missing, there should be error msgs
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    copy_file(pipfile_dir / "Pipfile", tmp_path)
    # copy_file(shared_datadir / "minimal_empty_setup.py", tmp_path, "setup.py")
    with working_directory(tmp_path):
        with pytest.raises(SystemExit):
            cmd(argv=[..., "sync"])
    captured = capfd.readouterr()
    assert msg_formatter.no_sync_performed() in captured.err
    assert msg_formatter.missing_file(Path("Pipfile.lock")) in captured.err


def test_help_text(capsys):
    cmd(argv=[...])
    captured = capsys.readouterr()
    assert "Commands:" in captured.out
    assert "sync" in captured.out
    assert "check" in captured.out
    assert captured.err == ""


@pytest.mark.parametrize(("source_pipfile_dirname",), [("nasty_0",)])
@pytest.mark.parametrize(
    ("missing_filenames",),
    [
        [["Pipfile"]],
        [["Pipfile", "Pipfile.lock"]],
        [["Pipfile.lock", "setup.py"]],
        [["Pipfile", "setup.py"]],
        [["Pipfile", "setup.py", "Pipfile.Lock"]],
        [["setup.py"]],
    ],
)
def test_check_file_missing_exit_code(
    capfd,
    tmp_path,
    shared_datadir,
    source_pipfile_dirname: str,
    missing_filenames: List[str],
):
    """
    when Pipfile.lock is missing, return code should be one
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ["Pipfile", "Pipfile.lock", "setup.py"]:
        file = pipfile_dir / filename
        if filename not in missing_filenames:
            copy_file(file, tmp_path)
    # copy_file(shared_datadir / "minimal_empty_setup.py", tmp_path, "setup.py")
    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=[..., "check"])
        assert e.value.code == 1


@pytest.mark.parametrize(("source_pipfile_dirname",), [("nasty_0",)])
def test_check_file_ignore_local(
    capsys, tmp_path, shared_datadir, source_pipfile_dirname: str
):
    """
    when Pipfile.lock is missing, return code should be one
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ("Pipfile", "Pipfile.lock", "setup.py"):
        copy_file(pipfile_dir / filename, tmp_path)
    # copy_file(shared_datadir / "minimal_empty_setup.py", tmp_path, "setup.py")
    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=[..., "check"])
        assert e.value.code == 1

        cmd(argv=[..., "check", "--ignore-local"])
        captured = capsys.readouterr()
        assert msg_formatter.checked_no_problem() in captured.out


@pytest.mark.parametrize(("source_pipfile_dirname",), [("loose_pass_strict_fail_0",)])
def test_check_file_strict(
    capsys, tmp_path, shared_datadir, source_pipfile_dirname: str
):
    """
    when --strict flag is passed. compatible but not identical versioning should fail
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ("Pipfile", "Pipfile.lock", "setup.py"):
        copy_file(pipfile_dir / filename, tmp_path)
    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=[..., "check", "--strict"])
        assert e.value.code == 1

        cmd(argv=[..., "check"])
        captured = capsys.readouterr()
        assert msg_formatter.checked_no_problem() in captured.out


@pytest.mark.parametrize(("source_pipfile_dirname",), [("many_conflicts_0",)])
def test_check_file_many_conflicts(
    capsys, tmp_path, shared_datadir, source_pipfile_dirname: str
):
    """
    many conflicts, return code should be one
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ("Pipfile", "Pipfile.lock", "setup.py"):
        copy_file(pipfile_dir / filename, tmp_path)

    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=[..., "check"])
        assert e.value.code == 1


@pytest.mark.parametrize(("source_pipfile_dirname",), [("broken_0",), ("broken_1",)])
def test_check_file_broken_setup(
    capsys, tmp_path, shared_datadir, source_pipfile_dirname: str
):
    """
    when Pipfile.lock is missing, return code should be one
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ("Pipfile", "Pipfile.lock", "setup.py"):
        copy_file(pipfile_dir / filename, tmp_path)
    # copy_file(shared_datadir / "minimal_empty_setup.py", tmp_path, "setup.py")
    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=["", "check", "--ignore-local"])
        assert e.value.code == 1


@pytest.mark.parametrize(("source_pipfile_dirname",), [("install_requires_missing_0",)])
def test_check_file_install_requires_missing(
    capsys, tmp_path, shared_datadir, source_pipfile_dirname: str
):
    """
    when Pipfile.lock is missing, return code should be one
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ("Pipfile", "Pipfile.lock", "setup.py"):
        copy_file(pipfile_dir / filename, tmp_path)
    # copy_file(shared_datadir / "minimal_empty_setup.py", tmp_path, "setup.py")
    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=[..., "check"])
        assert e.value.code == 1


@pytest.mark.parametrize(("source_pipfile_dirname",), [("lock_package_broken_0",)])
def test_sync_lock_file_package_broken(
    tmp_path, shared_datadir, source_pipfile_dirname: str
):
    """
    when Pipfile.lock is missing, return code should be one
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ("Pipfile", "Pipfile.lock", "setup.py"):
        copy_file(pipfile_dir / filename, tmp_path)

    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=[..., "sync"])
        assert e.value.code == 1


@pytest.mark.parametrize(("source_pipfile_dirname",), [("broken_no_setup_call_0",)])
def test_sync_no_setup_call(tmp_path, shared_datadir, source_pipfile_dirname: str):
    """
    when setup call is not found, return code should be one
    """
    pipfile_dir = shared_datadir / source_pipfile_dirname
    for filename in ("Pipfile", "Pipfile.lock", "setup.py"):
        copy_file(pipfile_dir / filename, tmp_path)
    with working_directory(tmp_path):
        with pytest.raises(SystemExit) as e:
            cmd(argv=["", "sync"])
        assert e.value.code == 1


def test_wrong_use_of_congratulate():
    with pytest.raises(TypeError):
        # noinspection PyTypeChecker
        main.congratulate(123)  # type: ignore


def test_wrong_use_of_fatal_error():
    with pytest.raises(TypeError):
        # noinspection PyTypeChecker
        main.fatal_error(123)  # type: ignore
