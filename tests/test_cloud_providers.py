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
r"""Cloud storage basic E2E.
"""

# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=unused-import

import os
from pathlib import Path
import logging
import keyring
import pytest

# Importing google.api_core.exceptions acts as a
# workaround for an issue where, if it is used
# by a factory used by a test, and loaded dynamically
# the first test will succeed, the others failing.
# This only happens with pytest and seems to relate
# to stale state in protobuf message.cc in relation to
# how the environment is managed when pytester is used,
# where id(_message.Message) changes at Python level, but
# not in the message.cc related pyd (dll).
import google.api_core.exceptions

LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-import,wrong-import-position
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

from atbu.tools.backup.constants import (
    CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
    CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
    CONFIG_PASSWORD_KIND_FILENAME,
    CONFIG_PASSWORD_KIND_ACTUAL,
    CONFIG_VALUE_NAME_CONTAINER,
    CREDS_SUBCMD_CREATE_STORAGE_DEF,
)
from atbu.tools.backup.config import AtbuConfig

from atbu.tools.backup.storage_interface.base import StorageInterfaceFactory

# pylint: disable=unused-import
from .secrets import (
    AWS_STORAGE_ACCESSKEY,
    AWS_STORAGE_SECRET,
    AZSDK_AZURE_BLOB_STORAGE_SECRET,
    AZSDK_AZURE_BLOB_STORAGE_USERKEY,
    LIBCLOUD_AZURE_BLOB_STORAGE_SECRET,
    LIBCLOUD_AZURE_BLOB_STORAGE_USERKEY,
    GOOGLE_STORAGE_ACCESS_KEY,
    GOOGLE_STORAGE_SECRET,
    GOOGLE_STORAGE_SERVICE_ACCOUNT_CLIENT_EMAIL,
    GOOGLE_STORAGE_SERVICE_ACCOUNT_JSON_PATH,
    GOOGLE_STORAGE_SERVICE_ACCOUNT_PROJECT_ID,
)

from .common_helpers import (
    create_test_data_directory_minimal_vary,
    establish_random_seed,
    create_test_data_directory_basic,
    create_test_data_directory_minimal,
    DirInfo,
    run_atbu,
    extract_storage_definition_and_config_file_path,
    validate_backup_dryrun,
    validate_backup_recovery,
    validate_backup_restore,
    validate_backup_restore_history,
    validate_cred_export_import,
)

from atbu.tools.backup.backup_constants import DatabaseFileType

TEST_BACKUP_NAME = "atbu-backup-5b497bb3-c9ef-48a9-af7b-2327fc17fb65"
TEST_CONTAINER_BASE_NAME = "atbu-bucket"

# import pdb; pdb.set_trace()
# import pdb; pdb.set_trace()


def setup_module(module):  # pylint: disable=unused-argument
    pass


def teardown_module(module):  # pylint: disable=unused-argument
    pass


def get_storage_factory(storage_def_name: str) -> StorageInterfaceFactory:
    return StorageInterfaceFactory.create_factory_from_storage_def_name(
        storage_def_name=storage_def_name
    )


def get_storage_def_dict(storage_def_name: str) -> dict:
    cfg: AtbuConfig
    cfg, _, storage_def_dict = AtbuConfig.access_cloud_storage_config(
        storage_def_name=storage_def_name,
        must_exist=True,
        create_if_not_exist=False,
    )
    return storage_def_dict


def get_all_storage_def_names() -> list[str]:
    return AtbuConfig.get_user_storage_def_names()


def get_container_name(storage_def_name: str) -> str:
    storage_def_dict = get_storage_def_dict(storage_def_name=storage_def_name)
    return storage_def_dict[CONFIG_VALUE_NAME_CONTAINER]


def create_storage_definition_json(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    tmp_path: Path,
    pytester: Pytester,
    use_secrets_prompt: bool = False,
) -> tuple[str, str, str]:

    if use_secrets_prompt:
        # No secrets on command line.
        driver_arg = ""
        # Input secrets...
        # access key<ENTER>
        # secret access key<ENTER>
        # ENTER ENTER to accept both defaults for backup encryption.
        stdin_resp_enable_enc_pwd_not_req = (
            f"{userkey}{os.linesep}" +
            f"{secret}{os.linesep}" +
            f"{os.linesep}{os.linesep}"
        ).encode()
    else:
        # Specify all driver arguments, including secrets, on command line.
        driver_arg = f"key={userkey},secret={secret}"
        # ENTER ENTER to accept both defaults.
        stdin_resp_enable_enc_pwd_not_req = f"{os.linesep}{os.linesep}".encode()

    # Specify other cloud storage driver kv pairs on command line.
    # If project id is specified, add it to command line.
    if project_id is not None:
        driver_arg = (driver_arg + f",project={project_id}").strip(", ")

    if len(driver_arg) > 0:
        # Specify driver_arg.
        rr = run_atbu(
            pytester,
            tmp_path,
            "creds",
            CREDS_SUBCMD_CREATE_STORAGE_DEF,
            TEST_BACKUP_NAME,
            interface,
            provider,
            f"{TEST_CONTAINER_BASE_NAME}*",
            driver_arg,
            stdin=stdin_resp_enable_enc_pwd_not_req,
            log_base_name=f"{CREDS_SUBCMD_CREATE_STORAGE_DEF}-json",
        )
    else:
        # Do not specify driver_arg.
        rr = run_atbu(
            pytester,
            tmp_path,
            "creds",
            CREDS_SUBCMD_CREATE_STORAGE_DEF,
            TEST_BACKUP_NAME,
            interface,
            provider,
            f"{TEST_CONTAINER_BASE_NAME}*",
            stdin=stdin_resp_enable_enc_pwd_not_req,
            log_base_name=f"{CREDS_SUBCMD_CREATE_STORAGE_DEF}-json",
        )
    assert rr.ret == ExitCode.OK

    storage_def_name_atbu_cfg_path_list = (
        extract_storage_definition_and_config_file_path(rr.outlines)
    )
    assert len(storage_def_name_atbu_cfg_path_list) >= 1
    last_save = storage_def_name_atbu_cfg_path_list[-1]
    storage_def_name = last_save[0]
    atbu_cfg_path = last_save[1]

    cfg, _, _ = AtbuConfig.access_cloud_storage_config(
        storage_def_name=storage_def_name,
        must_exist=True,
        create_if_not_exist=False,
    )

    container_name = cfg.get_storage_def_dict(storage_def_name=storage_def_name)[
        CONFIG_VALUE_NAME_CONTAINER
    ]

    return storage_def_name, atbu_cfg_path, container_name


def delete_all_objects(storage_def_name: str):
    factory = get_storage_factory(storage_def_name=storage_def_name)

    interface = factory.create_storage_interface()
    container_name = get_container_name(storage_def_name=storage_def_name)
    container = interface.get_container(container_name=container_name)
    list_objs = container.list_objects()
    for obj in list_objs:
        container.delete_object(object_name=obj.name)


def delete_container(storage_def_name: str):
    factory = get_storage_factory(storage_def_name=storage_def_name)
    interface = factory.create_storage_interface()
    container_name = get_container_name(storage_def_name=storage_def_name)

    delete_all_objects(storage_def_name=storage_def_name)

    interface.delete_container(container_name=container_name)


def delete_all_containers():
    all_storage_def_names = get_all_storage_def_names()
    for name in all_storage_def_names:
        try:
            delete_container(storage_def_name=name)
        except Exception as ex:
            LOGGER.error(f"failed to delete container {name}. {ex}")


def delete_storage_definition_json(
    tmp_path: Path,
    pytester: Pytester,
):
    delete_container(storage_def_name=TEST_BACKUP_NAME)

    # Enter Y for yes to confirm storage def deletion.
    # Enter Y for yes to confirm deletion of backup information.
    stdin_resp_enter_y_for_yes = f"y{os.linesep}y{os.linesep}".encode()

    rr = run_atbu(
        pytester,
        tmp_path,
        "creds",
        "delete-storage-def",
        TEST_BACKUP_NAME,
        stdin=stdin_resp_enter_y_for_yes,
        log_base_name="delete-storage-def",
    )
    assert rr.ret == ExitCode.OK

    kr_pwd_after_del = keyring.get_password(
        service_name=TEST_BACKUP_NAME, username=CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD
    )
    assert kr_pwd_after_del is None

    kr_pwd_after_del = keyring.get_password(
        service_name=TEST_BACKUP_NAME,
        username=CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
    )
    assert kr_pwd_after_del is None


@pytest.fixture(autouse=True)
def cleanup_keyring(pytester: Pytester):
    yield

    try:
        delete_all_containers()
    except Exception:
        pass

    try:
        keyring.delete_password(
            service_name=TEST_BACKUP_NAME,
            username=CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
        )
    except Exception:
        pass

    try:
        keyring.delete_password(
            service_name=TEST_BACKUP_NAME,
            username=CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
        )
    except Exception:
        pass


backup_restore_parameters = [
    pytest.param(
        "google",
        "google_storage",
        GOOGLE_STORAGE_SERVICE_ACCOUNT_PROJECT_ID,
        GOOGLE_STORAGE_SERVICE_ACCOUNT_CLIENT_EMAIL,
        GOOGLE_STORAGE_SERVICE_ACCOUNT_JSON_PATH,
        CONFIG_PASSWORD_KIND_FILENAME,
        id="google",
        marks=pytest.mark.skipif(
            GOOGLE_STORAGE_SERVICE_ACCOUNT_CLIENT_EMAIL == "skip",
            reason="secrets not available.",
        ),
    ),
    pytest.param(
        "azure",
        "azure_blobs",
        None,
        AZSDK_AZURE_BLOB_STORAGE_USERKEY,
        AZSDK_AZURE_BLOB_STORAGE_SECRET,
        CONFIG_PASSWORD_KIND_ACTUAL,
        id="azsdk_azure",
        marks=pytest.mark.skipif(
            AZSDK_AZURE_BLOB_STORAGE_USERKEY == "skip", reason="secrets not available."
        ),
    ),
    pytest.param(
        "libcloud",
        "azure_blobs",
        None,
        LIBCLOUD_AZURE_BLOB_STORAGE_USERKEY,
        LIBCLOUD_AZURE_BLOB_STORAGE_SECRET,
        CONFIG_PASSWORD_KIND_ACTUAL,
        id="libcloud_azure",
        marks=pytest.mark.skipif(
            LIBCLOUD_AZURE_BLOB_STORAGE_USERKEY == "skip", reason="secrets not available."
        ),
    ),
    pytest.param(
        "libcloud",
        "s3",
        None,
        AWS_STORAGE_ACCESSKEY,
        AWS_STORAGE_SECRET,
        CONFIG_PASSWORD_KIND_ACTUAL,
        id="aws",
        marks=pytest.mark.skipif(
            AWS_STORAGE_ACCESSKEY == "skip", reason="secrets not available."
        ),
    ),
]


@pytest.mark.parametrize(
    "interface,provider,project_id,userkey,secret,secret_type",
    backup_restore_parameters,
)
def test_create_storage_definition_json(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    secret_type,
    tmp_path: Path,
    pytester: Pytester,
):
    storage_def_name, atbu_cfg_path, container_name = create_storage_definition_json(
        interface,
        provider,
        project_id,
        userkey,
        secret,
        tmp_path=tmp_path,
        pytester=pytester,
    )
    assert storage_def_name == TEST_BACKUP_NAME
    assert os.path.isfile(atbu_cfg_path)

    cfg, _, _ = AtbuConfig.access_cloud_storage_config(
        storage_def_name=storage_def_name,
        must_exist=True,
        create_if_not_exist=False,
    )
    storage_def_dict = cfg.get_storage_def_with_resolved_secrets_deep_copy(
        storage_def_name=TEST_BACKUP_NAME, keep_secrets_base64_encoded=False
    )
    assert container_name.startswith(TEST_CONTAINER_BASE_NAME)
    assert len(container_name) > len(TEST_CONTAINER_BASE_NAME)
    client_email_from_cfg = storage_def_dict["driver"]["key"]
    if project_id is not None:
        project_id_from_cfg = storage_def_dict["driver"]["project"]
        assert project_id_from_cfg == project_id
    secret_from_cfg = storage_def_dict["driver"]["secret"].decode("utf-8")
    password_type_from_cfg = storage_def_dict["driver"]["password_type"]
    assert client_email_from_cfg == userkey
    assert secret_from_cfg == secret
    assert password_type_from_cfg == secret_type

    delete_storage_definition_json(tmp_path=tmp_path, pytester=pytester)
    pass  # pylint: disable=unnecessary-pass

@pytest.mark.parametrize(
    "interface,provider,project_id,userkey,secret,secret_type",
    backup_restore_parameters,
)
def test_create_storage_definition_json__secrets_prompt(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    secret_type,
    tmp_path: Path,
    pytester: Pytester,
):
    storage_def_name, atbu_cfg_path, container_name = create_storage_definition_json(
        interface,
        provider,
        project_id,
        userkey,
        secret,
        tmp_path=tmp_path,
        pytester=pytester,
        use_secrets_prompt=True,
    )
    assert storage_def_name == TEST_BACKUP_NAME
    assert os.path.isfile(atbu_cfg_path)

    cfg, _, _ = AtbuConfig.access_cloud_storage_config(
        storage_def_name=storage_def_name,
        must_exist=True,
        create_if_not_exist=False,
    )
    storage_def_dict = cfg.get_storage_def_with_resolved_secrets_deep_copy(
        storage_def_name=TEST_BACKUP_NAME, keep_secrets_base64_encoded=False
    )
    assert container_name.startswith(TEST_CONTAINER_BASE_NAME)
    assert len(container_name) > len(TEST_CONTAINER_BASE_NAME)
    client_email_from_cfg = storage_def_dict["driver"]["key"]
    if project_id is not None:
        project_id_from_cfg = storage_def_dict["driver"]["project"]
        assert project_id_from_cfg == project_id
    secret_from_cfg = storage_def_dict["driver"]["secret"].decode("utf-8")
    password_type_from_cfg = storage_def_dict["driver"]["password_type"]
    assert client_email_from_cfg == userkey
    assert secret_from_cfg == secret
    assert password_type_from_cfg == secret_type

    delete_storage_definition_json(tmp_path=tmp_path, pytester=pytester)
    pass  # pylint: disable=unnecessary-pass


@pytest.mark.parametrize(
    "interface,provider,project_id,userkey,secret,secret_type",
    backup_restore_parameters,
)
def test_backup_restore(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    secret_type,
    tmp_path: Path,
    pytester: Pytester,
):
    storage_def_name, atbu_cfg_path, container_name = create_storage_definition_json(
        interface,
        provider,
        project_id,
        userkey,
        secret,
        tmp_path=tmp_path,
        pytester=pytester,
    )
    assert storage_def_name == TEST_BACKUP_NAME
    assert os.path.isfile(atbu_cfg_path)

    establish_random_seed(tmp_path)

    source_directory = tmp_path / "SourceDataDir"

    _, files_created = create_test_data_directory_basic(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)
    assert total_files > 0

    storage_specifier = f"storage:{TEST_BACKUP_NAME}"

    validate_backup_restore(
        pytester=pytester,
        tmp_path=tmp_path,
        source_directory=source_directory,
        initial_expected_total_files=total_files,
        storage_specifier=storage_specifier,
        compression_type="normal",
        db_type=None,
        backup_base_name=None,
        backup_timeout=60 * 5,
        restore_timeout=60 * 5,
        initial_backup_stdin=None,
    )

    delete_storage_definition_json(tmp_path=tmp_path, pytester=pytester)
    pass  # pylint: disable=unnecessary-pass


@pytest.mark.parametrize(
    "interface,provider,project_id,userkey,secret,secret_type",
    backup_restore_parameters,
)
def test_backup_restore__secrets_prompt(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    secret_type,
    tmp_path: Path,
    pytester: Pytester,
):
    storage_def_name, atbu_cfg_path, container_name = create_storage_definition_json(
        interface,
        provider,
        project_id,
        userkey,
        secret,
        tmp_path=tmp_path,
        pytester=pytester,
        use_secrets_prompt=True,
    )
    assert storage_def_name == TEST_BACKUP_NAME
    assert os.path.isfile(atbu_cfg_path)

    establish_random_seed(tmp_path)

    source_directory = tmp_path / "SourceDataDir"

    _, files_created = create_test_data_directory_minimal_vary(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)
    assert total_files > 0

    storage_specifier = f"storage:{TEST_BACKUP_NAME}"

    validate_backup_restore(
        pytester=pytester,
        tmp_path=tmp_path,
        source_directory=source_directory,
        initial_expected_total_files=total_files,
        storage_specifier=storage_specifier,
        compression_type="normal",
        db_type=None,
        backup_base_name=None,
        backup_timeout=60 * 5,
        restore_timeout=60 * 5,
        initial_backup_stdin=None,
    )

    delete_storage_definition_json(tmp_path=tmp_path, pytester=pytester)
    pass  # pylint: disable=unnecessary-pass


@pytest.mark.parametrize(
    "interface,provider,project_id,userkey,secret,secret_type",
    backup_restore_parameters,
)
def test_backup_restore_history(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    secret_type,
    tmp_path: Path,
    pytester: Pytester,
):
    storage_def_name, atbu_cfg_path, container_name = create_storage_definition_json(
        interface,
        provider,
        project_id,
        userkey,
        secret,
        tmp_path=tmp_path,
        pytester=pytester,
    )
    assert storage_def_name == TEST_BACKUP_NAME
    assert os.path.isfile(atbu_cfg_path)

    establish_random_seed(tmp_path)

    source_directory = tmp_path / "SourceDataDir"

    _, files_created = create_test_data_directory_minimal_vary(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)
    assert total_files > 0

    storage_specifier = f"storage:{TEST_BACKUP_NAME}"

    validate_backup_restore_history(
        pytester=pytester,
        tmp_path=tmp_path,
        max_history=3,
        source_directory=source_directory,
        expected_total_files=total_files,
        storage_specifier=storage_specifier,
        compression_type="normal",
        db_type=None,
        backup_base_name=None,
        backup_timeout=60 * 5,
        restore_timeout=60 * 5,
        initial_backup_stdin=None,
    )

    delete_storage_definition_json(tmp_path=tmp_path, pytester=pytester)
    pass  # pylint: disable=unnecessary-pass



@pytest.mark.parametrize(
    "interface,provider,project_id,userkey,secret,secret_type",
    backup_restore_parameters,
)
def test_backup_dryrun(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    secret_type,
    tmp_path: Path,
    pytester: Pytester,
):
    storage_def_name, atbu_cfg_path, container_name = create_storage_definition_json(
        interface,
        provider,
        project_id,
        userkey,
        secret,
        tmp_path=tmp_path,
        pytester=pytester,
    )
    assert storage_def_name == TEST_BACKUP_NAME
    assert os.path.isfile(atbu_cfg_path)

    establish_random_seed(tmp_path)

    source_directory = tmp_path / "SourceDataDir"

    _, files_created = create_test_data_directory_minimal_vary(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)
    assert total_files > 0

    storage_specifier = f"storage:{TEST_BACKUP_NAME}"

    validate_backup_dryrun(
        pytester=pytester,
        tmp_path=tmp_path,
        source_directory=source_directory,
        total_original_files=total_files,
        storage_specifier=storage_specifier,
        backup_timeout=60 * 5,
        restore_timeout=60 * 5,
        initial_backup_stdin=None,
    )

    delete_storage_definition_json(tmp_path=tmp_path, pytester=pytester)
    pass  # pylint: disable=unnecessary-pass


@pytest.mark.parametrize(
    "interface,provider,project_id,userkey,secret,secret_type",
    backup_restore_parameters,
)
def test_credential_export_import(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    secret_type,
    tmp_path: Path,
    pytester: Pytester,
):
    storage_def_name, atbu_cfg_path, container_name = create_storage_definition_json(
        interface,
        provider,
        project_id,
        userkey,
        secret,
        tmp_path=tmp_path,
        pytester=pytester,
    )
    assert storage_def_name == TEST_BACKUP_NAME
    assert os.path.isfile(atbu_cfg_path)

    establish_random_seed(tmp_path)

    source_directory = tmp_path / "SourceDataDir"

    _, files_created = create_test_data_directory_minimal(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)
    assert total_files > 0

    #
    # Backup file. Restoring this, or not, is basis for other
    # results below.
    #
    rr = run_atbu(
        pytester,
        tmp_path,
        "backup",
        "--full",
        source_directory,
        f"storage:{storage_def_name}",
        timeout=60 * 5,
        log_base_name="backup",
    )
    assert rr.ret == ExitCode.OK

    validate_cred_export_import(
        pytester=pytester,
        tmp_path=tmp_path,
        atbu_cfg_path=atbu_cfg_path,
        source_directory=source_directory,
        expected_total_files=total_files,
        storage_def_name=storage_def_name,
        storage_specifier=f"storage:{storage_def_name}",
    )

    delete_storage_definition_json(tmp_path=tmp_path, pytester=pytester)
    pass  # pylint: disable=unnecessary-pass


@pytest.mark.parametrize(
    "interface,provider,project_id,userkey,secret,secret_type",
    backup_restore_parameters,
)
def test_credential_and_backup_info_recovery(
    interface,
    provider,
    project_id,
    userkey,
    secret,
    secret_type,
    tmp_path: Path,
    pytester: Pytester,
):
    storage_def_name, atbu_cfg_path, container_name = create_storage_definition_json(
        interface,
        provider,
        project_id,
        userkey,
        secret,
        tmp_path=tmp_path,
        pytester=pytester,
    )
    assert storage_def_name == TEST_BACKUP_NAME
    assert os.path.isfile(atbu_cfg_path)

    establish_random_seed(tmp_path)

    source_directory = tmp_path / "SourceDataDir"

    _, files_created = create_test_data_directory_minimal(
        path_to_dir=source_directory,
    )
    total_files = len(files_created)
    assert total_files > 0

    #
    # Backup file. Restoring this, or not, is basis for other
    # results below.
    #
    rr = run_atbu(
        pytester,
        tmp_path,
        "backup",
        "--full",
        source_directory,
        f"storage:{storage_def_name}",
        timeout=60 * 5,
        log_base_name="backup",
    )
    assert rr.ret == ExitCode.OK

    validate_backup_recovery(
        pytester=pytester,
        tmp_path=tmp_path,
        atbu_cfg_path=atbu_cfg_path,
        source_directory=source_directory,
        expected_total_files=total_files,
        storage_def_name=storage_def_name,
        storage_specifier=f"storage:{storage_def_name}",
    )

    delete_storage_definition_json(tmp_path=tmp_path, pytester=pytester)
    pass  # pylint: disable=unnecessary-pass
