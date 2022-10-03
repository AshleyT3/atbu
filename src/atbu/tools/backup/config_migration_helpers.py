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
r"""ATBU Configuration-related migration helper classes/functions.
"""

import base64
from dataclasses import dataclass
import keyring

from atbu.common.util_helpers import (
    is_valid_base64_string,
)
# Import module to mock credentials.* once directly.
import atbu.tools.backup.credentials as credentials
from .constants import (
    CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
    CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
    CONFIG_PASSWORD_KIND_ACTUAL,
    CRED_SECRET_KIND_ENCRYPTION,
    CRED_SECRET_KIND_STORAGE,
)
from .exception import (
    ConfigMigrationError,
    CredentialNotFoundError,
    InvalidBase64StringError,
    PasswordAuthenticationFailure,
    CredentialInvalid,
    CredentialSecretDerivationError,
)
from .credentials import (
    Credential,
    CredentialByteArray,
    CredentialAesKey,
    DescribedCredential,
)
from .storage_def_credentials import StorageDefCredentialSet

@dataclass
class Version_001:
    AT_PREFIX = "at"
    AT_PREFIX_U = "AT"
    ATBU_ACRONYM = f"{AT_PREFIX}bu"
    ATBU_ACRONUM_U = f"{AT_PREFIX_U}BU"

    CONFIG_SECTION_KEYRING_MAPPING = "keyring-mapping"
    CONFIG_SECTION_KEYRING_MAPPING_ENCRYPTION_KEY = "encryption-key"
    CONFIG_SECTION_KEYRING_MAPPING_DRIVER_SECRET = "driver-secret"

    CONFIG_VALUE_NAME_KEYRING_SERVICE = "service"
    CONFIG_VALUE_NAME_KEYRING_USERNAME = "username"

    CONFIG_KEY_VALUE_KEYRING_INDIRECTION = "keyring"

    CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION = f"{ATBU_ACRONUM_U}-backup-enc-key"
    CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD = f"{ATBU_ACRONUM_U}-storage-password"

    CRED_KEY_TYPE_STORAGE = "storage-secret"
    CRED_KEY_TYPE_ENCRYPTION = "encryption-key"

    CONFIG_PASSWORD_TYPE = "password_type"
    CONFIG_PASSWORD_TYPE_ACTUAL = "actual"
    CONFIG_PASSWORD_TYPE_FILENAME = "filename"
    CONFIG_PASSWORD_TYPE_ENVVAR = "envvar"
    PASSWORD_TYPE_CHAR_TO_TYPE = {
        i[0]: i
        for i in [
            CONFIG_PASSWORD_TYPE_ACTUAL,
            CONFIG_PASSWORD_TYPE_FILENAME,
            CONFIG_PASSWORD_TYPE_ENVVAR,
        ]
    }

    CONFIG_SECTION_DRIVER = "driver"
    CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET = "secret"

    CONFIG_SECTION_ENCRYPTION = "encryption"
    CONFIG_VALUE_NAME_ENCRYPTION_KEY = "key"

    CONFIG_SECTION_STORAGE_DEFINITIONS = "storage-definitions"

def set_password_to_keyring_001(
    service_name: str,
    username: str,
    password_type: str,
    password_bytes: CredentialByteArray,
    password_is_base64: bool = False,
) -> None:
    if not service_name:
        raise CredentialInvalid(
            f"Cannot store credential. The supplied service name must be a non-empty string."
        )

    if not username:
        raise CredentialInvalid(
            f"Cannot store credential. The supplied user name must be a non-empty string."
        )

    if not password_type:
        raise CredentialInvalid(
            f"Cannot store credential. The supplied password type must be a non-empty string."
        )

    password_type_code = password_type[0]
    if password_type_code not in Version_001.PASSWORD_TYPE_CHAR_TO_TYPE:
        raise CredentialInvalid(
            f"Cannot store credential. The supplied password type '{password_type}' is invalid."
        )

    if not password_bytes:
        raise CredentialInvalid(
            f"Cannot store credential. The password was not supplied."
        )

    if not password_is_base64:
        password_bytes = CredentialByteArray(base64.b64encode(password_bytes))

    if not is_valid_base64_string(str_to_check=password_bytes):
        raise InvalidBase64StringError(
            f"Expected password_bytes to be a base64-encoded string."
        )

    keyring.set_password(
        service_name=service_name,
        username=username,
        password=f"{password_type_code}:{str(password_bytes, 'utf-8')}",
    )

def _get_base64_password_from_keyring(
    service_name: str,
    username: str,
) -> tuple[str, str, CredentialByteArray]:
    raw_password = keyring.get_password(service_name=service_name, username=username)
    if raw_password is None:
        raise CredentialNotFoundError(
            f"The credential was not found in the keyring: "
            f"service_name={service_name} username={username}"
        )
    password_parts = raw_password.split(":", maxsplit=1)
    if len(password_parts) != 2:
        raise CredentialInvalid(
            f"The stored credential is not in the expected two-part format."
        )
    password_type_code = password_parts[0]
    cba_password_base64 = CredentialByteArray(password_parts[1].encode("utf-8"))

    if len(password_type_code) == 0:
        raise CredentialInvalid(
            f"The stored credential is not in the expected format. "
            f"The password type code is not present. "
            f"service_name={service_name} username={username}"
        )

    if len(cba_password_base64) == 0:
        raise CredentialInvalid(
            f"The stored credential is not in the expected format. "
            f"The password is not present. "
            f"service_name={service_name} username={username}"
        )

    if not is_valid_base64_string(cba_password_base64):
        raise InvalidBase64StringError(
            f"Expected stored credential to be in base64 format."
        )

    if password_type_code not in Version_001.PASSWORD_TYPE_CHAR_TO_TYPE:
        raise CredentialInvalid(
            f"The stored credential is not in the expected format. "
            f"The password type code '{password_type_code}' is unknown. "
            f"service_name={service_name} username={username}"
        )

    password_type = Version_001.PASSWORD_TYPE_CHAR_TO_TYPE[password_type_code]

    return (password_type_code, password_type, cba_password_base64)


def _unlock_credential_001(credential: CredentialAesKey):
    """Unlock a CredentialAesKey instance which is to make its private key/secret
    available in the clear. If the private key is password-protected, ask
    for a password. The result of calling this function is an unlocked
    credential or an exception.

        Exceptions:
            PasswordAuthenticationFailure: Too many attempts with incorrect password.
            CredentialSecretDerivationError: Something unexpected indicates the key
            is not available despite having been decrypted (likely a program bug or
            something esoteric such as system corruption).
    """
    if not credential.is_private_key_possible:
        raise CredentialInvalid(
            f"The private key is not available. "
            f"The credential is invalid or corrupt."
        )
    if not credential.is_private_key_ready:
        if not credential.is_password_required:
            credential.decrypt_key()
        else:
            attempts = 5
            while True:
                password = credentials.prompt_for_password_with_yubikey_opt(
                    prompt="Enter the password for this backup:"
                )
                credential.set(password=password)
                try:
                    attempts -= 1
                    credential.decrypt_key()
                    break
                except PasswordAuthenticationFailure:
                    if attempts > 0:
                        print(f"The password appears to be invalid, try again.")
                    else:
                        print(f"Still incorrect.")
                        raise
        if not credential.is_private_key_ready:
            raise CredentialSecretDerivationError(
                "Unexpected failure, canonot access the credential."
            )

def _get_password_from_keyring(
    service_name: str,
    username: str,
) -> tuple[str, str, CredentialByteArray]:
    (
        password_type_code,
        password_type,
        cba_password_base64,
    ) = _get_base64_password_from_keyring(
        service_name=service_name,
        username=username,
    )

    cba_password = CredentialByteArray(base64.b64decode(cba_password_base64))

    if (
        username == Version_001.CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION
        and password_type == Version_001.CONFIG_PASSWORD_TYPE_ACTUAL
    ):
        credential = CredentialAesKey.create_credential_from_bytes(cred_bytes=cba_password)
        _unlock_credential_001(credential=credential)
        # The actual 0.01 code only propagates the key but migration requires
        # the CredentialAesKey instance.
        cba_password = credential
        # cba_password = credential.the_key
        # del credential

    return (password_type_code, password_type, cba_password)

def _resolve_keyring_secrets(
    storage_def_dict: dict,
):
    # Access 'keyring-mapping' section.
    keyring_section: dict = storage_def_dict.get(Version_001.CONFIG_SECTION_KEYRING_MAPPING)
    if not keyring_section:
        return

    # For each 'keyring-mapping' item:
    #    item's name:
    #       encoded with string such as 'driver-secret' to indicate mapping
    #       relates from secret to { ... "driver": { ... "secret": <secret> ... } ... }
    #    items's value:
    #       indicates keyring service/username with secret.
    affected_config_path: str
    for affected_config_path, keyring_lookup_info in keyring_section.items():
        # Split item's name to get the storage definition path parts.
        affected_config_path_parts = affected_config_path.split("-")

        # Get the service/user names.
        service_name = keyring_lookup_info[Version_001.CONFIG_VALUE_NAME_KEYRING_SERVICE]
        username = keyring_lookup_info[Version_001.CONFIG_VALUE_NAME_KEYRING_USERNAME]

        # Walk from top of config_section down to the second-to-last section which is
        # where the secret goes.
        affected_section = storage_def_dict
        for section_part in affected_config_path_parts[:-1]:
            affected_section = affected_section[section_part]

        # Given service/user names, get the secret.
        (_, password_type, cba_password) = _get_password_from_keyring(
            service_name=service_name,
            username=username,
        )

        affected_section[affected_config_path_parts[-1]] = cba_password
        affected_section[Version_001.CONFIG_PASSWORD_TYPE] = password_type


@dataclass
class StorageDefMigrationItem_001:
    storage_def_name: str
    storage_def_dict: dict
    cred_set: StorageDefCredentialSet


def prepare_for_storage_def_migration_001(
    cfg: dict,
) -> list[StorageDefMigrationItem_001]:
    """For each storage definition, return a StorageDefMigrationItem_001 containing
    the storage def's credentials in a StorageDefCredentialSet. The set will be
    unprotected and unsaved upon return (i.e., not written yet). For each storage
    definition in the supplied configuration, update the dictionary to remove the
    old keyring mapping. When the caller writes the cred set, the dictionary will
    be updated further.

    Args:
        cfg (dict): The v0.01 ATBU configuration to convert to v0.02.

    Returns:
        list[StorageDefMigrationItem_001]: One migration item for each storage
        definition found.
    """
    migration_items = list[StorageDefMigrationItem_001]()
    storage_definitions = cfg[Version_001.CONFIG_SECTION_STORAGE_DEFINITIONS]
    storage_def_name: str
    storage_def_dict: dict
    for storage_def_name, storage_def_dict in storage_definitions.items():
        print(f"Processing storage definition: {storage_def_name}...")
        _resolve_keyring_secrets(storage_def_dict=storage_def_dict)
        if storage_def_dict.get(Version_001.CONFIG_SECTION_KEYRING_MAPPING) is not None:
            del storage_def_dict[Version_001.CONFIG_SECTION_KEYRING_MAPPING]
        cred_storage = None
        cred_storage_type = None
        cred_encryption = None
        storage_section = storage_def_dict.get(Version_001.CONFIG_SECTION_DRIVER)
        if isinstance(storage_section, dict) and len(storage_section) != 0:
            storage_secret = storage_section.get(
                Version_001.CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET
            )
            if not isinstance(storage_secret, CredentialByteArray):
                raise ConfigMigrationError(
                    f"Expected storage secret to be CredentialByteArray but got "
                    f"'{type(storage_secret)}'.")
            cred_storage = Credential(the_key=storage_secret)
            cred_storage_type = storage_section.get(Version_001.CONFIG_PASSWORD_TYPE)
            if not isinstance(cred_storage_type, str) or len(cred_storage_type) == 0:
                raise ConfigMigrationError(
                    f"Expected non-zero len str cred_storage_type: "
                    f"type={type(cred_storage_type)} "
                    f"len={len(cred_storage_type)}"
                )
        else:
            print(f"No cloud storage section found for '{storage_def_name}'.")
        encryption_section = storage_def_dict.get(Version_001.CONFIG_SECTION_ENCRYPTION)
        if isinstance(encryption_section, dict):
            cred_encryption = encryption_section.get(Version_001.CONFIG_VALUE_NAME_ENCRYPTION_KEY)
            if not isinstance(cred_encryption, CredentialAesKey):
                raise ConfigMigrationError(
                    f"Expected CredentialAesKey but got {type(cred_encryption)}"
                )
            if cred_storage is not None and cred_encryption.is_password_protected:
                if (
                    not isinstance(cred_encryption.password, CredentialByteArray)
                    or len(cred_encryption.password) == 0
                ):
                    raise ConfigMigrationError(
                        f"Password not found for password-protected encryption key: "
                        f"type={type(cred_encryption.password)} "
                        f"len={len(cred_encryption.password)}"
                    )
                cred_storage.prepare_for_new_password()
                cred_storage.set(password=CredentialByteArray(cred_encryption.password))
        cred_set = StorageDefCredentialSet(
            storage_def_name=storage_def_name,
            storage_def_dict=storage_def_dict,
        )
        if cred_encryption is not None:
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
        if cred_storage is not None:
            desc_cred_storage = DescribedCredential(
                credential=cred_storage,
                config_name=storage_def_name,
                credential_name=CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
                credential_kind=cred_storage_type,
            )
            cred_set.append(
                desc_cred=desc_cred_storage,
                affected_config_path_parts=CRED_SECRET_KIND_STORAGE.split("-"),
            )
        migration_items.append(
            StorageDefMigrationItem_001(
                storage_def_name=storage_def_name,
                storage_def_dict=storage_def_dict,
                cred_set=cred_set,
            )
        )
    if len(storage_definitions) != len(migration_items):
        raise ConfigMigrationError(
            f"Mismatched storage definition count: "
            f"config={len(storage_definitions)} "
            f"migration_items={len(migration_items)}."
        )
    return migration_items

def upgrade_storage_definitions_from_001_to_002(
    cfg: dict,
):
    migration_items = prepare_for_storage_def_migration_001(cfg=cfg)
    for mi in migration_items:
        mi.cred_set.protect()
        mi.cred_set.save()
