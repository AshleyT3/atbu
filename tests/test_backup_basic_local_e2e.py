# Copyright 2022 Ashley R. Thomas
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=unused-import
# pylint: disable=wrong-import-position

import os
from pathlib import Path
import logging
from pytest import (
    LogCaptureFixture,
    CaptureFixture,
    fail,
    raises,
    Pytester,
    FixtureRequest,
    Config,
    RunResult,
    ExitCode,
)
import pytest

from atbu.tools.backup.config import AtbuConfig

from .common_helpers import (
    create_test_data_directory_minimal,
    create_test_data_directory_minimal_vary,
    establish_random_seed,
    create_test_data_directory_basic,
    DirInfo,
    extract_dir_info_from_verify_log,
    validate_backup_dryrun,
    validate_backup_recovery,
    validate_backup_restore,
    validate_backup_restore_history,
    validate_cred_export_import,
    run_atbu,
    directories_match_entirely_by_path,
)

LOGGER = logging.getLogger(__name__)

ATBU_TEST_BACKUP_NAME = "AtbuTestBackup-5b497bb3-c9ef-48a9-af7b-2327fc17fb65"

# import pdb; pdb.set_trace()
# import pdb; pdb.set_trace()


def setup_module(module):  # pylint: disable=unused-argument
    pass


def teardown_module(module):  # pylint: disable=unused-argument
    pass


backup_restore_parameters = [
    pytest.param(
        "none",
        id="no_compression",
    ),
    pytest.param(
        "normal",
        id="normal_compression",
    ),
]


@pytest.mark.parametrize(
    "compression_type",
    backup_restore_parameters,
)
def test_backup_restore(
    compression_type,
    tmp_path: Path,
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    source_directory = tmp_path / "SourceDataDir"
    backup_directory = tmp_path / "BackupDestination"

    _, files_created = create_test_data_directory_basic(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)

    stdin_bytes = (
        f"{ATBU_TEST_BACKUP_NAME}{os.linesep}{os.linesep}{os.linesep}".encode()
    )

    validate_backup_restore(
        pytester=pytester,
        tmp_path=tmp_path,
        source_directory=source_directory,
        expected_total_files=total_files,
        storage_specifier=backup_directory,
        compression_type=compression_type,
        backup_timeout=60,
        restore_timeout=60,
        initial_backup_stdin=stdin_bytes,
    )
    pass  # pylint: disable=unnecessary-pass


def test_verify_digest_only(
    pytestconfig: Config,  # pylint: disable=unused-argument
    tmp_path: Path,
    capsys: CaptureFixture,  # pylint: disable=unused-argument
    caplog: LogCaptureFixture,  # pylint: disable=unused-argument
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    source_directory = tmp_path / "SourceDataDir"
    backup_directory = tmp_path / "BackupDestination"

    _, files_created = create_test_data_directory_basic(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)

    with DirInfo(source_directory) as source_dir_info:
        source_dir_info.gather_info(start_gathering_digests=True)
        assert len(source_dir_info.file_list) == total_files

        stdin_bytes = (
            f"{ATBU_TEST_BACKUP_NAME}{os.linesep}{os.linesep}{os.linesep}".encode()
        )
        rr = run_atbu(
            pytester,
            tmp_path,
            "backup",
            "--incremental-plus",
            source_directory,
            backup_directory,
            stdin=stdin_bytes,
            log_base_name="backup",
        )
        assert rr.ret == ExitCode.OK

        rr = run_atbu(
            pytester,
            tmp_path,
            "verify",
            backup_directory,
            "backup:last",
            "files:*",
            log_base_name="verify",
        )
        assert rr.ret == ExitCode.OK
        verify_dir_info = extract_dir_info_from_verify_log(output_lines=rr.outlines)
        assert directories_match_entirely_by_path(
            di1=source_dir_info, di2=verify_dir_info
        )
    pass  # pylint: disable=unnecessary-pass


def test_verify_compare_local(
    pytestconfig: Config,  # pylint: disable=unused-argument
    tmp_path: Path,
    capsys: CaptureFixture,  # pylint: disable=unused-argument
    caplog: LogCaptureFixture,  # pylint: disable=unused-argument
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    source_directory = tmp_path / "SourceDataDir"
    backup_directory = tmp_path / "BackupDestination"

    _, files_created = create_test_data_directory_basic(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)

    source_dir_info = DirInfo(source_directory)
    with source_dir_info:
        source_dir_info.gather_info(start_gathering_digests=True)
        assert len(source_dir_info.file_list) == total_files

        stdin_bytes = (
            f"{ATBU_TEST_BACKUP_NAME}{os.linesep}{os.linesep}{os.linesep}".encode()
        )
        rr = run_atbu(
            pytester,
            tmp_path,
            "backup",
            "--incremental-plus",
            source_directory,
            backup_directory,
            stdin=stdin_bytes,
            log_base_name="backup",
        )
        assert rr.ret == ExitCode.OK

        rr = run_atbu(
            pytester,
            tmp_path,
            "verify",
            backup_directory,
            "backup:last",
            "files:*",
            "--compare",
            log_base_name="verify-compare",
        )
        assert rr.ret == ExitCode.OK
        verify_dir_info = extract_dir_info_from_verify_log(output_lines=rr.outlines)
        assert directories_match_entirely_by_path(
            di1=source_dir_info, di2=verify_dir_info
        )
    pass  # pylint: disable=unnecessary-pass


@pytest.mark.parametrize(
    "compression_type",
    backup_restore_parameters,
)
def test_backup_restore_history(
    compression_type,
    tmp_path: Path,
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    source_directory = tmp_path / "SourceDataDir"
    backup_directory = tmp_path / "BackupDestination"

    _, files_created = create_test_data_directory_minimal_vary(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)

    stdin_bytes = (
        f"{ATBU_TEST_BACKUP_NAME}{os.linesep}{os.linesep}{os.linesep}".encode()
    )

    validate_backup_restore_history(
        pytester=pytester,
        tmp_path=tmp_path,
        max_history=5,
        source_directory=source_directory,
        expected_total_files=total_files,
        storage_specifier=backup_directory,
        compression_type=compression_type,
        backup_timeout=60,
        restore_timeout=60,
        initial_backup_stdin=stdin_bytes,
    )
    pass  # pylint: disable=unnecessary-pass

def test_backup_dryrun(
    tmp_path: Path,
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    source_directory = tmp_path / "SourceDataDir"
    backup_directory = tmp_path / "BackupDestination"

    _, files_created = create_test_data_directory_minimal_vary(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)

    stdin_bytes = (
        f"{ATBU_TEST_BACKUP_NAME}{os.linesep}{os.linesep}{os.linesep}".encode()
    )

    validate_backup_dryrun(
        pytester=pytester,
        tmp_path=tmp_path,
        source_directory=source_directory,
        total_original_files=total_files,
        storage_specifier=backup_directory,
        backup_timeout=60,
        restore_timeout=60,
        initial_backup_stdin=stdin_bytes,
    )
    pass  # pylint: disable=unnecessary-pass


def test_credential_export_import(
    tmp_path: Path,
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    storage_def_name = ATBU_TEST_BACKUP_NAME

    source_directory = tmp_path / "SourceDataDir"
    backup_directory = tmp_path / "BackupDestination"

    _, files_created = create_test_data_directory_minimal(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)
    assert total_files > 0

    stdin_bytes = f"{storage_def_name}{os.linesep}{os.linesep}{os.linesep}".encode()
    rr = run_atbu(
        pytester,
        tmp_path,
        "backup",
        "--full",
        source_directory,
        backup_directory,
        stdin=stdin_bytes,
        log_base_name="backup",
    )
    assert rr.ret == ExitCode.OK

    atbu_cfg: AtbuConfig
    (
        atbu_cfg,
        storage_def_name_from_cfg,
        storage_def,
    ) = AtbuConfig.access_filesystem_storage_config(
        storage_location_path=backup_directory,
        resolve_storage_def_secrets=False,
        create_if_not_exist=False,
        prompt_to_create=False,
    )
    assert storage_def_name.lower() == storage_def_name_from_cfg

    validate_cred_export_import(
        pytester=pytester,
        tmp_path=tmp_path,
        atbu_cfg_path=atbu_cfg.path,
        source_directory=source_directory,
        expected_total_files=total_files,
        storage_def_name=storage_def_name,
        storage_specifier=backup_directory,
    )

    # Delete the secrets from potentially global cred store, but leave
    # the def intact in case it needs to be examined.
    # atbu_cfg.delete_storage_def(storage_def_name=storage_def_name)
    atbu_cfg.delete_storage_def_secrets(storage_def_name=storage_def_name)
    pass  # pylint: disable=unnecessary-pass


def test_credential_and_backup_info_recovery(
    tmp_path: Path,
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    storage_def_name = ATBU_TEST_BACKUP_NAME

    source_directory = tmp_path / "SourceDataDir"
    backup_directory = tmp_path / "BackupDestination"

    _, files_created = create_test_data_directory_minimal(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)
    assert total_files > 0

    stdin_bytes = f"{storage_def_name}{os.linesep}{os.linesep}{os.linesep}".encode()
    rr = run_atbu(
        pytester,
        tmp_path,
        "backup",
        "--full",
        source_directory,
        backup_directory,
        stdin=stdin_bytes,
        log_base_name="backup",
    )
    assert rr.ret == ExitCode.OK

    atbu_cfg: AtbuConfig
    (
        atbu_cfg,
        storage_def_name_from_cfg,
        storage_def,
    ) = AtbuConfig.access_filesystem_storage_config(
        storage_location_path=backup_directory,
        resolve_storage_def_secrets=False,
        create_if_not_exist=False,
        prompt_to_create=False,
    )
    assert storage_def_name.lower() == storage_def_name_from_cfg

    validate_backup_recovery(
        pytester=pytester,
        tmp_path=tmp_path,
        atbu_cfg_path=atbu_cfg.path,
        source_directory=source_directory,
        expected_total_files=total_files,
        storage_def_name=storage_def_name,
        storage_specifier=backup_directory,
    )

    # Delete the secrets from potentially global cred store, but leave
    # the def intact in case it needs to be examined.
    # atbu_cfg.delete_storage_def(storage_def_name=storage_def_name)
    atbu_cfg.delete_storage_def_secrets(storage_def_name=storage_def_name)
    pass  # pylint: disable=unnecessary-pass
