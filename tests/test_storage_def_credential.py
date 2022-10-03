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
from atbu.tools.backup.constants import (
    CONFIG_INTERFACE_TYPE_LIBCLOUD,
    CONFIG_KEY_VALUE_KEYRING_INDIRECTION,
    CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
    CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
    CONFIG_PASSWORD_KIND_ACTUAL,
    CONFIG_VALUE_NAME_DRIVER_STORAGE_KEY,
    CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET,
    CRED_SECRET_KIND_ENCRYPTION,
    CRED_SECRET_KIND_STORAGE,
)

from atbu.tools.backup.credentials import (
    CredentialByteArray,
    Credential,
    CredentialAesKey,
    DescribedCredential
)
from atbu.tools.backup.config import AtbuConfig
from atbu.tools.backup.storage_def_credentials import StorageDefCredentialSet

LOGGER = logging.getLogger(__name__)

ATBU_TEST_BACKUP_NAME = "AtbuTestBackup-5b497bb3-c9ef-48a9-af7b-2327fc17fb65"

# import pdb; pdb.set_trace()
# import pdb; pdb.set_trace()

SIMPLE_SECRET = "secret-1234567890!"
SIMPLE_PASSWORD = "1234567890abcdefghij$"

def setup_module(module):  # pylint: disable=unused-argument
    pass

def teardown_module(module):  # pylint: disable=unused-argument
    pass

def add_encryption_credential_to_set(
    storage_def_name: str,
    cred_set: StorageDefCredentialSet,
    credential_password: CredentialByteArray = None,
):
    cred_encryption = CredentialAesKey()
    cred_encryption.create_key()
    desc_cred_encryption = DescribedCredential(
        credential=cred_encryption,
        config_name=storage_def_name,
        credential_name=CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
        credential_kind=CONFIG_PASSWORD_KIND_ACTUAL,
    )
    cred_set.append(
        desc_cred=desc_cred_encryption,
        affected_config_path_parts=CRED_SECRET_KIND_ENCRYPTION.split("-"),
    )
    if credential_password is not None:
        cred_set.get_encryption_desc_cred().credential.set(
            password=CredentialByteArray(credential_password),
        )

def add_storage_credential_to_set(
    storage_def_name: str,
    cred_set: StorageDefCredentialSet,
    storage_secret: str,
    credential_password: CredentialByteArray = None,
):
    cred_storage = Credential(the_key=CredentialByteArray(storage_secret.encode("utf-8")))
    desc_cred_encryption = cred_set.get_encryption_desc_cred()
    if desc_cred_encryption is not None:
        cred_encryption = desc_cred_encryption.credential
        if cred_encryption.is_password_protected:
            cred_storage.set(password=CredentialByteArray(cred_encryption.password))
    desc_cred_storage = DescribedCredential(
        credential=cred_storage,
        config_name=storage_def_name,
        credential_name=CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
        credential_kind=CONFIG_PASSWORD_KIND_ACTUAL,
    )
    cred_set.append(
        desc_cred=desc_cred_storage,
        affected_config_path_parts=CRED_SECRET_KIND_STORAGE.split("-"),
    )
    if credential_password is not None:
        cred_set.get_storage_desc_cred().credential.set(
            password=CredentialByteArray(credential_password),
        )

def create_test_storage_def_credential_set(
    storage_def_name: str,
    storage_def_dict: dict,
    include_storage_cred: bool,
    storage_secret: str,
    credential_password: CredentialByteArray = None,
) -> StorageDefCredentialSet:

    cred_set = StorageDefCredentialSet(
        storage_def_name=storage_def_name,
        storage_def_dict=storage_def_dict,
    )

    add_encryption_credential_to_set(
        storage_def_name=storage_def_name,
        cred_set=cred_set,
        credential_password=credential_password,
    )

    if include_storage_cred:
        add_storage_credential_to_set(
            storage_def_name=storage_def_name,
            cred_set=cred_set,
            storage_secret=storage_secret,
            credential_password=credential_password,
        )

    return cred_set

@pytest.mark.parametrize(
    "is_storage_secret_in_config,is_populate_init,is_password_protected",
    [
        pytest.param(
            False,
            False,
            False,
            id="secret_in_config=False,populate_init=False,password_protected=False",
        ),
        pytest.param(
            True,
            False,
            False,
            id="secret_in_config=True,populate_init=False,password_protected=False",
        ),
        pytest.param(
            True,
            True,
            False,
            id="secret_in_config=True,populate_init=True,password_protected=False",
        ),
        pytest.param(
            False,
            False,
            True,
            id="secret_in_config=False,populate_init=False,password_protected=True",
        ),
        pytest.param(
            True,
            False,
            True,
            id="secret_in_config=True,populate_init=False,password_protected=True",
        ),
        pytest.param(
            True,
            True,
            True,
            id="secret_in_config=True,populate_init=True,password_protected=True",
        ),
    ]
)
def test_storage_def_credential_set(
    tmp_path: Path,
    pytester: Pytester,
    is_storage_secret_in_config: bool,
    is_populate_init: bool,
    is_password_protected: bool,
):
    """Manually create a StorageDefCredentialSet, validate operations/persistence.

    This scenario initializes the StorageDefCredentialSet by building the credentials
    manually in code, and not deriving some/all from the configuration file.
    """
    atbu_cfg = AtbuConfig.access_default_config()
    storage_def_name = "test_storage_def_credential_set"
    credential_password = None
    if is_password_protected:
        credential_password = CredentialByteArray("test-cred-pwd$".encode("utf-8"))

    storage_secret = "test-storage-secret"
    if not is_storage_secret_in_config:
        other_kv_pairs = {
            CONFIG_VALUE_NAME_DRIVER_STORAGE_KEY: "test-storage-key",
        }
    else:
        other_kv_pairs = {
            CONFIG_VALUE_NAME_DRIVER_STORAGE_KEY: "test-storage-key",
            CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET: f"a:K={storage_secret.encode('utf-8').hex()}"
        }

    atbu_cfg.create_storage_def(
        interface_type=CONFIG_INTERFACE_TYPE_LIBCLOUD,
        provider_id="test-provider-id",
        container="test-container-name",
        other_driver_kv_pairs=other_kv_pairs,
        unique_storage_def_name=storage_def_name,
    )

    if not is_populate_init:
        cred_set = create_test_storage_def_credential_set(
            storage_def_name=storage_def_name,
            storage_def_dict=atbu_cfg.get_storage_def_dict(storage_def_name=storage_def_name),
            include_storage_cred=True,
            storage_secret=storage_secret,
            credential_password=credential_password,
        )
    else:
        cred_set = StorageDefCredentialSet(
            storage_def_name=storage_def_name,
            storage_def_dict=atbu_cfg.get_storage_def_dict(storage_def_name=storage_def_name),
        )
        cred_set.populate()

        if credential_password is not None:
            cred_set.set_password(
                cred_password=CredentialByteArray(credential_password)
            )

        assert cred_set.get_encryption_desc_cred() is None
        assert cred_set.get_storage_desc_cred() is not None

        add_encryption_credential_to_set(
            storage_def_name=storage_def_name,
            cred_set=cred_set,
            credential_password=credential_password,
        )

    desc_cred_encryption = cred_set.get_encryption_desc_cred()
    desc_cred_storage = cred_set.get_storage_desc_cred()
    cred_set.protect()
    cred_set.save()
    atbu_cfg.save_config_file()

    atbu_cfg2 = AtbuConfig.access_default_config()
    storage_def_dict2 = atbu_cfg2.get_storage_def_dict(storage_def_name=storage_def_name)
    cred_set = StorageDefCredentialSet(
        storage_def_name=storage_def_name,
        storage_def_dict=storage_def_dict2,
    )

    encryption_dict, encryption_key_value_name = cred_set.get_affected_section(
        CRED_SECRET_KIND_ENCRYPTION.split("-")
    )
    storage_dict, storage_secret_value_name = cred_set.get_affected_section(
        CRED_SECRET_KIND_STORAGE.split("-")
    )

    assert encryption_dict[encryption_key_value_name] == CONFIG_KEY_VALUE_KEYRING_INDIRECTION
    assert storage_dict[storage_secret_value_name] == CONFIG_KEY_VALUE_KEYRING_INDIRECTION

    cred_set.populate()
    cred_set.unprotect(password=credential_password)

    assert encryption_dict[encryption_key_value_name] != CONFIG_KEY_VALUE_KEYRING_INDIRECTION
    assert storage_dict[storage_secret_value_name] != CONFIG_KEY_VALUE_KEYRING_INDIRECTION
    assert encryption_dict[encryption_key_value_name] == desc_cred_encryption.credential.the_key
    assert storage_dict[storage_secret_value_name] == desc_cred_storage.credential.the_key

    desc_cred_encryption2 = cred_set.get_encryption_desc_cred()
    desc_cred_storage2 = cred_set.get_storage_desc_cred()
    assert desc_cred_encryption2.credential.the_key == desc_cred_encryption.credential.the_key
    assert desc_cred_encryption2.config_name == desc_cred_encryption.config_name
    assert desc_cred_encryption2.credential_name == desc_cred_encryption.credential_name
    assert desc_cred_encryption2.credential_kind == desc_cred_encryption.credential_kind

    assert desc_cred_storage2.credential.the_key == desc_cred_storage.credential.the_key
    assert desc_cred_storage2.config_name == desc_cred_storage.config_name
    assert desc_cred_storage2.credential_name == desc_cred_storage.credential_name
    assert desc_cred_storage2.credential_kind == desc_cred_storage.credential_kind
