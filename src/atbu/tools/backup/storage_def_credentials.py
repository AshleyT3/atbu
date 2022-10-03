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
r"""Storage definition credentials and related helpers.
"""

import base64
import os
from typing import Union

from .constants import *
from .exception import *
from .credentials import (
    Credential,
    CredentialAesKey,
    CredentialByteArray,
    CredentialStore,
    DescribedCredential,
    prompt_for_password_unlock_credential,
    raw_cred_bytes_to_type_base64_cred_bytes,
)

def get_credential_class(
    store_credential_name: str,
):
    # Determine the type needed by using the cred_def info.
    #   Backup encryption key: CredentialAesKey
    #   Storage secret: Credential

    cls = None
    if store_credential_name == CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION:
        cls = CredentialAesKey
    elif store_credential_name == CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD:
        cls = Credential
    else:
        raise ValueError(
            f"Unexpected: store_credential_name={store_credential_name}"
        )
    return cls


@dataclass
class StorageDefCredential:
    desc_cred: DescribedCredential
    affected_section: dict
    affected_section_key: str


class StorageDefCredentialSet:
    def __init__(
        self,
        storage_def_name: str = None,
        storage_def_dict: dict = None,
    ) -> None:
        self.storage_def_name = storage_def_name
        self.storage_def_dict = storage_def_dict
        self.storage_def_creds = list[StorageDefCredential]()
    def get_affected_section(
        self,
        affected_config_path_parts: Union[str, list[str]],
    ) -> tuple[dict, str]:
        if isinstance(affected_config_path_parts, str):
            # Split to coerce str into storage definition path parts. i.e.,
            #   'driver-secret' -> ['driver', 'secret']
            #   'encryption-key' -> ['encryption', 'key']
            affected_config_path_parts = affected_config_path_parts.split("-")
        if not isinstance(affected_config_path_parts, list):
            raise ValueError(
                f"affected_config_path_parts must be either a str or list of "
                f"section parts."
            )
        # Walk from top of storage_def down to the second-to-last section
        # which is where the secret goes.
        affected_section = self.storage_def_dict
        for section_part in affected_config_path_parts[:-1]:
            if section_part not in affected_section:
                affected_section[section_part] = {}
            affected_section = affected_section[section_part]
        return affected_section, affected_config_path_parts[-1]
    def populate(self):
        """For each credential associated with this set's storage definition,
        add the credential to the set.
        """
        if len(self.storage_def_creds) != 0:
            raise InvalidStateError(
                f"StorageDefCredentialSet.populate can only be called on an empty set."
            )
        for _, cred_def in CREDENTIAL_DEFINITIONS.items():

            (
                affected_section,
                affected_section_key,
            ) = self.get_affected_section(
                affected_config_path_parts=cred_def.section_path,
            )

            if affected_section_key not in affected_section:
                continue

            raw_cred_value = affected_section[affected_section_key]

            if raw_cred_value == CONFIG_KEY_VALUE_KEYRING_INDIRECTION:
                desc_cred = CredentialStore().get_credential(
                    config_name=self.storage_def_name,
                    credential_name=cred_def.store_credential_name,
                )
            else:
                # Currently, the Credential* type is not persisted in the raw.
                # Determine class to use from store credential name.
                cls = get_credential_class(
                    store_credential_name=cred_def.store_credential_name,
                )
                cred_ascii_bytes = CredentialByteArray(raw_cred_value.encode("utf-8"))
                (
                    password_type,
                    cba_password_base64,
                ) = raw_cred_bytes_to_type_base64_cred_bytes(
                    cred_ascii_bytes=cred_ascii_bytes,
                )
                credential = cls.create_credential_from_bytes(
                    cred_bytes=cba_password_base64
                )
                desc_cred = DescribedCredential(
                    credential=credential,
                    config_name=self.storage_def_name,
                    credential_name=cred_def.store_credential_name,
                    credential_kind=password_type,
                )
            self.append(
                desc_cred=desc_cred,
                affected_config_path_parts=cred_def.section_path,
            )
    def append(
        self,
        desc_cred: DescribedCredential,
        affected_config_path_parts: Union[str, list[str]],
    ):
        (
            affected_section,
            affected_section_key,
        ) = self.get_affected_section(
            affected_config_path_parts=affected_config_path_parts,
        )
        self.storage_def_creds.append(
            StorageDefCredential(
                desc_cred=desc_cred,
                affected_section=affected_section,
                affected_section_key=affected_section_key,
            )
        )
    def set_password(
        self,
        cred_password: CredentialByteArray,
    ):
        for storage_def_cred in self.storage_def_creds:
            credential = storage_def_cred.desc_cred.credential
            if credential.is_password_protected:
                if credential.is_password_required:
                    raise CredentialStateInvalid(
                        f"Cannot set password while credential is protected."
                    )
            if cred_password is not None:
                credential.prepare_for_new_password()
                credential.set(password=CredentialByteArray(cred_password))
            else:
                credential.clear_password_protection()
    def unprotect(
        self,
        base64_encoded_secrets: bool = False,
        password: CredentialByteArray = None,
    ):
        password_protected_status = None
        for storage_def_cred in self.storage_def_creds:
            credential = storage_def_cred.desc_cred.credential
            if not credential.is_password_protected:
                if password_protected_status is not None and password_protected_status:
                    # A previous credential in the set was password-protected.
                    # This is currently not a use case.
                    raise CredentialSetInvalid(
                        f"Credentials in the set have differing password protection status."
                    )
                password_protected_status = False
            else:
                if password_protected_status is not None and not password_protected_status:
                    # A previous credential in the set was *not* password-protected.
                    # This is currently not a use case.
                    raise CredentialSetInvalid(
                        f"Credentials in the set have differing password protection status."
                    )
                password_protected_status = True
                if password is None:
                    prompt_for_password_unlock_credential(credential=credential)
                    password = credential.password
                else:
                    credential.set(password=CredentialByteArray(password))
                    credential.decrypt_key()
            secret_to_use = credential.the_key
            if base64_encoded_secrets:
                secret_to_use = base64.b64encode(
                    credential.get_material_as_bytes()
                ).decode("utf-8")
            storage_def_cred.affected_section[
                storage_def_cred.affected_section_key
            ] = secret_to_use
            storage_def_cred.affected_section[
                CONFIG_PASSWORD_TYPE
            ] = storage_def_cred.desc_cred.credential_kind

    def protect(self):
        password_protected_status = None
        for storage_def_cred in self.storage_def_creds:
            credential = storage_def_cred.desc_cred.credential
            cred_name = storage_def_cred.desc_cred.credential_name
            if not credential.is_password_protected:
                if password_protected_status is not None and password_protected_status:
                    # A previous credential in the set was password-protected.
                    # This is currently not a use case.
                    raise CredentialSetInvalid(
                        f"Credentials in the set have differing password protection status."
                    )
                password_protected_status = False
                continue
            if password_protected_status is not None and not password_protected_status:
                # A previous credential in the set was *not* password-protected.
                # This is currently not a use case.
                raise CredentialSetInvalid(
                    f"Credentials in the set have differing password protection status."
                )
            password_protected_status = True
            print(f"Encrypting key '{cred_name}'...", end="")
            storage_def_cred.desc_cred.credential.encrypt_key()
            print(f"encrypted.")
            credential.clear_password()
    def save(self):
        rollback_info = []
        try:
            for storage_def_cred in self.storage_def_creds:
                desc_cred = storage_def_cred.desc_cred
                # TODO: Save store and file.
                cba_old = CredentialStore().set_credential(desc_cred=desc_cred)
                if cba_old is not None:
                    rollback_info.append(
                        (
                            desc_cred.config_name,
                            desc_cred.credential_name,
                            cba_old,
                        )
                    )
                storage_def_cred.affected_section[
                    storage_def_cred.affected_section_key
                ] = CONFIG_KEY_VALUE_KEYRING_INDIRECTION
        except BaseException as ex:
            print(f"Failure saving credentials: {ex}")
            try:
                if len(rollback_info) > 0:
                    print(f"Rolling back already writting changes...")
                for rbi in rollback_info:
                    print(f"Undoing: config_name={rbi[0]} credential_name={rbi[1]}")
                    CredentialStore().provider.set_cred_bytes(
                        config_name=rbi[0],
                        credential_name=rbi[1],
                        cred_ascii_bytes=rbi[2],
                    )
            except BaseException as ex2:
                print(f"Rollback error: {ex2}")
            raise
    def get_desc_cred(
        self,
        credential_name: str,
    ):
        for storage_def_cred in self.storage_def_creds:
            cred_name = storage_def_cred.desc_cred.credential_name
            if cred_name == credential_name:
                return storage_def_cred.desc_cred
        return None
    def get_encryption_desc_cred(self):
        return self.get_desc_cred(credential_name=CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION)
    def get_storage_desc_cred(self):
        return self.get_desc_cred(credential_name=CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD)


def prompt_user_password_file_does_not_exist(default_filename: str):
    is_exist = default_filename is not None and os.path.isfile(default_filename)
    print(f"Specify a path to an existing password .json file.")
    def_qual = ""
    if is_exist:
        def_qual = "<ENTER> for the default, "
        print(
            f"If you do not specify a name and press <ENTER>, the default name will be used."
        )
        print(f"Default path (file exists): {default_filename}")
    a = input(f"Enter the path, {def_qual}or 'n' to abort:")
    if a.lower() in ["n", "no"]:
        return None
    if is_exist and a == "":
        return default_filename
    return a


def restore_keyring_secrets(
    storage_def_name: str,
    storage_def: dict,
):
    for cred_def_friendly_name, cred_def in CREDENTIAL_DEFINITIONS.items():
        affected_config_path_parts = cred_def.section_path.split("-")
        affected_section = storage_def
        for section_name in affected_config_path_parts[:-1]:
            if section_name not in affected_section:
                affected_section = None
                break
            affected_section = affected_section[section_name]
        if affected_section is None or len(affected_section) == 0:
            # TODO: Consider determining from file what must be present.
            # For now, output a message to assist with refactoring verification.
            print(f"The credential for '{cred_def_friendly_name}' not found. Continuing...")
            continue
        password_type = affected_section.get(CONFIG_PASSWORD_TYPE)
        if password_type is None:
            raise CredentialTypeNotFoundError(
                f"restore_keyring_secrets: Cannot find credential type."
            )
        base64_cred_str = affected_section[affected_config_path_parts[-1]]
        cba_password = CredentialByteArray(
            base64_cred_str.encode("utf-8")
        )

        desc_cred = DescribedCredential.create_from_base64(
            config_name=storage_def_name,
            credential_name=cred_def.store_credential_name,
            password_type_code=password_type,
            cba_password_base64=cba_password,
        )

        if password_type == CONFIG_PASSWORD_KIND_FILENAME:

            credential = desc_cred.credential
            encrypt_key = False
            if credential.is_password_protected and not credential.is_private_key_ready:
                print(f"An OAuth file name credential is password-protected.")
                print(f"To validate the filename, you need to enter the backup password.")
                prompt_for_password_unlock_credential(
                    credential=credential,
                )
                encrypt_key = True
            filename = credential.the_key.decode("utf-8")
            while not os.path.isfile(filename):
                print(f"The credential file does not exist: {filename}")
                user_specified_filename = prompt_user_password_file_does_not_exist(
                    filename
                )
                if user_specified_filename is None:
                    raise CredentialSecretFileNotFoundError(
                        f"An existing credential password filename was not specified, "
                        f"aborting restore."
                    )
                if os.path.isfile(user_specified_filename):
                    credential.set(
                        the_key=CredentialByteArray(
                            user_specified_filename.encode("utf-8")
                        )
                    )
                    filename = user_specified_filename
                    break
                print(
                    f"ERROR: The filename entered does not exist: {user_specified_filename}"
                )
                print(
                    f"You must specify a path to an existing .json password file "
                    f"(i.e., a service account .json OAuth2 file)."
                )
            print(f"The OAuth file exists: {filename}")
            if encrypt_key:
                print(f"Re-encrypting filename crednetial.")
                credential.encrypt_key()

        CredentialStore().set_credential(desc_cred=desc_cred)
        affected_section[affected_config_path_parts[-1]] = CONFIG_KEY_VALUE_KEYRING_INDIRECTION
