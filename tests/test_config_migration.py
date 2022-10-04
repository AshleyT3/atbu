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

import copy
import json
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
    MonkeyPatch,
)
import pytest

from atbu.tools.backup.config import AtbuConfig
from atbu.tools.backup.credentials import (
    CredentialAesKey,
    CredentialByteArray,
)
import atbu.tools.backup.credentials as credentials
from atbu.tools.backup.config_migration_helpers import (
    Version_001,
    set_password_to_keyring_001,
)
import atbu.tools.backup.config_migration_helpers as config_migration_helpers
from atbu.tools.backup.storage_def_credentials import StorageDefCredentialSet

Version001_storage_def_name1 = "my-cloud-backup-53fcc53f-a5a5-4939-a88a-e8ad1c95fb0e"

Version001_config = {
    "name": "ATBU Configuration",
    "version": "0.01",
    "general": {"backup-info-dir": "C:\\Users\\TestUser\\.atbu\\atbu-backup-info"},
    "storage-definitions": {
        Version001_storage_def_name1: {
            "interface": "someinterface",
            "provider": "some_storage_provider",
            "container": "my-cloud-backup-xyz",
            "driver": {
                "key": "some-storage-key",
                "project": "some-storage-project",
                "secret": "keyring",
            },
            "keyring-mapping": {
                "driver-secret": {
                    "service": Version001_storage_def_name1,
                    "username": "ATBU-storage-password",
                },
                "encryption-key": {
                    "service": Version001_storage_def_name1,
                    "username": "ATBU-backup-enc-key",
                },
            },
            "encryption": {"key": "keyring"},
        }
    },
}


@pytest.mark.parametrize(
    "is_backup_encryption,is_storage_secret,is_password_protected",
    [
        pytest.param(
            True,
            True,
            False,
            id="is_backup_encryption=True,is_storage_secret=True,is_password_protected=False",
        ),
        pytest.param(
            True,
            True,
            True,
            id="is_backup_encryption=True,is_storage_secret=True,is_password_protected=True",
        ),
        pytest.param(
            True,
            False,
            True,
            id="is_backup_encryption=True,is_storage_secret=False,is_password_protected=True",
        ),
        pytest.param(
            False,
            True,
            False,
            id="is_backup_encryption=False,is_storage_secret=True,is_password_protected=False",
        ),
    ],
)
def test_migrate_001_to_002(
    tmp_path: Path,
    pytester: Pytester,
    monkeypatch: MonkeyPatch,
    is_backup_encryption: bool,
    is_storage_secret: bool,
    is_password_protected: bool,
):
    atbu_cfg = AtbuConfig.access_default_config()

    if is_password_protected:

        cred_password_str = "test-cred-password$"
        cred_password = CredentialByteArray(cred_password_str.encode("utf-8"))

        def mock_prompt_password_return(
            prompt,
            prompt_again=None,
            hidden: bool = True,
        ):
            return CredentialByteArray(cred_password)

        monkeypatch.setattr(
            credentials,
            "prompt_for_password_with_yubikey_opt",
            mock_prompt_password_return,
        )

    test_atbu_cfg_001 = copy.deepcopy(Version001_config)
    storage_defs_section = test_atbu_cfg_001[
        Version_001.CONFIG_SECTION_STORAGE_DEFINITIONS
    ]
    storage_def_section = storage_defs_section[Version001_storage_def_name1]
    storage_def_mapping_section = storage_def_section[
        Version_001.CONFIG_SECTION_KEYRING_MAPPING
    ]
    storage_def_driver_section = storage_def_section[Version_001.CONFIG_SECTION_DRIVER]
    if not is_backup_encryption:
        del storage_def_section[Version_001.CONFIG_SECTION_ENCRYPTION]
        del storage_def_mapping_section[
            Version_001.CONFIG_SECTION_KEYRING_MAPPING_ENCRYPTION_KEY
        ]
    if not is_storage_secret:
        del storage_def_section[Version_001.CONFIG_SECTION_DRIVER]
        del storage_def_mapping_section[
            Version_001.CONFIG_SECTION_KEYRING_MAPPING_DRIVER_SECRET
        ]
    if len(storage_def_section[Version_001.CONFIG_SECTION_KEYRING_MAPPING]) == 0:
        del storage_def_section[Version_001.CONFIG_SECTION_KEYRING_MAPPING]
    with open(atbu_cfg.path, "w", encoding="utf-8") as config_file:
        config_file.write(json.dumps(test_atbu_cfg_001, indent=4))

    cred_enc = None
    storage_secret = None
    cred_count = 0
    if is_backup_encryption:
        cred_count += 1
    if is_storage_secret:
        cred_count += 1

    if is_backup_encryption:
        cred_enc = CredentialAesKey()
        cred_enc.create_key()
        if is_password_protected:
            cred_enc.set(password=CredentialByteArray(cred_password))
            cred_enc.encrypt_key()
        set_password_to_keyring_001(
            service_name=Version001_storage_def_name1,
            username=Version_001.CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
            password_type=Version_001.CONFIG_PASSWORD_TYPE_ACTUAL,
            password_bytes=cred_enc.get_material_as_bytes(),
            password_is_base64=False,
        )
        if is_password_protected:
            cred_enc.decrypt_key()  # prepare for validation below.

    if is_storage_secret:
        storage_secret = CredentialByteArray("storage-secret-abc123$".encode("utf-8"))
        set_password_to_keyring_001(
            service_name=Version001_storage_def_name1,
            username=Version_001.CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
            password_type=Version_001.CONFIG_PASSWORD_TYPE_ACTUAL,
            password_bytes=storage_secret,
            password_is_base64=False,
        )

    storage_def_dict = copy.deepcopy(
        test_atbu_cfg_001[Version_001.CONFIG_SECTION_STORAGE_DEFINITIONS][
            Version001_storage_def_name1
        ]
    )
    cred_set = StorageDefCredentialSet(
        storage_def_name=Version001_storage_def_name1,
        storage_def_dict=storage_def_dict,
    )
    try:
        cred_set.populate()
        if is_storage_secret:
            pytest.fail(f"Populate of old 001 credentials should fail.")
        assert len(cred_set.storage_def_creds) == cred_count
    except BaseException:
        if not is_storage_secret:
            # Not a use case, but this state indicates mismatch between test assumption mismatch and
            # actual behavior.
            pytest.fail(
                f"Populate of old 001 credentials without storage secret should *not* fail."
            )
        assert len(cred_set.storage_def_creds) == 0

    # Re-get the overwritten config to trigger the migration.
    AtbuConfig.always_migrate = True
    atbu_cfg = AtbuConfig.access_default_config()

    cred_set = StorageDefCredentialSet(
        storage_def_name=Version001_storage_def_name1,
        storage_def_dict=atbu_cfg.get_storage_def_dict(
            storage_def_name=Version001_storage_def_name1,
            must_exist=True,
        ),
    )

    cred_set.populate()
    cred_set.unprotect()
    assert len(cred_set.storage_def_creds) == cred_count

    mig_desc_cred_encryption = cred_set.get_encryption_desc_cred()
    if is_backup_encryption:
        mig_cred_encryption = mig_desc_cred_encryption.credential
        assert mig_cred_encryption.the_key == cred_enc.the_key
    else:
        assert mig_desc_cred_encryption is None

    mig_desc_cred_storage = cred_set.get_storage_desc_cred()
    if is_storage_secret:
        mig_cred_storage = mig_desc_cred_storage.credential
        assert mig_cred_storage.the_key == storage_secret
    else:
        assert mig_desc_cred_storage is None
