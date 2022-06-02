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
r"""Credential and storage-definition-related creation/management.
"""

import json
import os
import logging
import re
from typing import Union

from ..common.util_helpers import prompt_YN
from ..common.mp_global import switch_to_non_queued_logging
from ..common.constants import *
from .config import (
    AtbuConfig,
    is_existing_filesystem_storage_path,
    is_storage_def_name_ok,
    parse_storage_def_specifier,
)
from .credentials import (
    Credential,
    CredentialByteArray,
    prompt_for_password,
    set_password_to_keyring,
)
from ..common.exception import (
    AtbuException,
    ContainerAlreadyExistsError,
    ContainerAutoCreationFailed,
    CredentialRequestInvalidError,
    CredentialTypeNotFoundError,
    InvalidCommandLineArgument,
    InvalidContainerNameError,
    InvalidStateError,
    InvalidStorageDefinitionName,
    PasswordAuthenticationFailure,
    CredentialInvalid,
    StorageDefinitionNotFoundError,
    UnexpectedOperation,
    EncryptionAlreadyEnabledError,
    CredentialSecretDerivationError,
    StorageDefinitionAlreadyExists,
    exc_to_string,
)
from .storage_interface.base import (
    AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR,
    StorageInterfaceFactory,
)


def handle_credential_change(
    operation: CRED_OPERATION_HINT,
    key_to_affect: CRED_KEY_TYPE_HINT,
    atbu_cfg: AtbuConfig,
    storage_def_name: str,
    credential: Union[str, list, Credential],
    debug_mode: bool = False,
):
    if not storage_def_name:
        raise ValueError(f"Invalid backup storage definition: {storage_def_name}")

    #
    # Given key_to_affect, the following dict provides info about what
    # keyring username to use as well as what ATBU config nodes to affect.
    #
    AFFECTED_KEY_TO_INFO = {
        CRED_KEY_TYPE_ENCRYPTION: (
            CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
            "encryption/key",
        ),
        CRED_KEY_TYPE_STORAGE: (
            CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
            "driver/secret",
        ),
    }

    #
    # Given operation, look up the password type to store.
    #
    OPERATION_TO_PASSWORD_TYPE = {
        CRED_OPERATION_SET_PASSWORD: CONFIG_PASSWORD_TYPE_ACTUAL,
        CRED_OPERATION_SET_PASSWORD_TO_FILENAME: CONFIG_PASSWORD_TYPE_FILENAME,
        CRED_OPERATION_SET_PASSWORD_TO_ENVVAR: CONFIG_PASSWORD_TYPE_ENVVAR,
        CRED_OPERATION_SET_PASSWORD_TO_PRIVATE_KEY: CONFIG_PASSWORD_TYPE_ACTUAL,
    }

    #
    # Determine username and config section given key_to_affect.
    #
    username = AFFECTED_KEY_TO_INFO[key_to_affect][0]
    section_path = AFFECTED_KEY_TO_INFO[key_to_affect][1]
    password_type = OPERATION_TO_PASSWORD_TYPE[operation]

    logging.info(f"Keyring information:")
    logging.info(f"Key={key_to_affect}")
    logging.info(f"Service={storage_def_name}")
    logging.info(f"Username={username}")
    logging.debug(f"password_type={password_type}")
    logging.debug(f"section_path={section_path}")

    if key_to_affect not in [CRED_KEY_TYPE_STORAGE, CRED_KEY_TYPE_ENCRYPTION]:
        raise UnexpectedOperation(f"The the '{key_to_affect}' key is unexpected.")

    #
    # CRED_KEY_TYPE_ENCRYPTION
    #
    if key_to_affect == CRED_KEY_TYPE_ENCRYPTION:

        if operation not in [
            CRED_OPERATION_SET_PASSWORD,
            CRED_OPERATION_SET_PASSWORD_TO_PRIVATE_KEY,
        ]:
            raise UnexpectedOperation(
                f"The operation '{operation}' for the '{key_to_affect}' key is unexpected."
            )

        if not isinstance(credential, Credential):
            raise CredentialTypeNotFoundError(
                f"A Credential type is expected when setting the '{key_to_affect}' secret"
            )

        if operation == CRED_OPERATION_SET_PASSWORD_TO_PRIVATE_KEY:
            # Direct private key, ensure key is present.
            if not credential.is_private_key_ready:
                raise CredentialInvalid(
                    f"Cannot set the '{key_to_affect}' key. "
                    f"The Credential is invalid because the private key is not immediately available"
                )
            # Direct key storage.
            credential_bytes = credential.get_as_bytes(include_key=True)
            if debug_mode:
                print(f"handle_credential_change: key={credential.the_key.hex(' ')}")
                print(f"handle_credential_change: b={credential_bytes}")
        elif operation == CRED_OPERATION_SET_PASSWORD:
            # Private key will be password-protected.
            if not credential.is_private_key_possible:
                raise CredentialInvalid(
                    f"Cannot set the '{key_to_affect}' key. "
                    f"The Credential cannot be used to derive the private key and is therefore invalid."
                )
            credential_bytes = credential.get_as_bytes(
                include_work_factor=True,
                include_salt=True,
                include_password_auth_hash=True,
                include_IV=True,
                include_encrypted_key=True,
            )
            if debug_mode:
                if credential.the_key:
                    print(
                        f"handle_credential_change: key={credential.the_key.hex(' ')}"
                    )
                else:
                    print(f"handle_credential_change: key=<none>")
                print(f"handle_credential_change: b={credential_bytes}")
    #
    # CRED_KEY_TYPE_STORAGE
    #
    elif key_to_affect == CRED_KEY_TYPE_STORAGE:

        if operation not in [
            CRED_OPERATION_SET_PASSWORD,
            CRED_OPERATION_SET_PASSWORD_TO_FILENAME,
            CRED_OPERATION_SET_PASSWORD_TO_ENVVAR,
        ]:
            raise UnexpectedOperation(
                f"The operation '{operation}' for the '{key_to_affect}' key is unexpected."
            )

        if not isinstance(credential, (CredentialByteArray, bytearray, bytes, str)):
            raise CredentialInvalid(
                f"The credential type '{type(credential)}' is not expected when setting the '{key_to_affect}' key."
            )

        credential_bytes = credential
        if isinstance(credential, str):
            credential_bytes = credential.encode("utf-8")
    #
    # Unexpected
    #
    else:
        raise UnexpectedOperation(f"The '{key_to_affect}' is unexpected.")

    set_password_to_keyring(
        service_name=storage_def_name,
        username=username,
        password_type=password_type,
        password_bytes=credential_bytes,
    )

    #
    # Update the configuration to reference the keyring data.
    #
    atbu_cfg.set_config_keyring_mapping(
        storage_def_name=storage_def_name, username=username, section_path=section_path
    )
    atbu_cfg.save_config_file()


def set_encryption_password_wizard(
    atbu_cfg: AtbuConfig,
    storage_def_name: str,
    encryption_already_enabled_ok: bool = False,
    debug_mode: bool = False,
):
    credential: Credential = None
    if atbu_cfg.is_storage_def_configured_for_encryption(
        storage_def_name=storage_def_name
    ):
        if not encryption_already_enabled_ok:
            raise EncryptionAlreadyEnabledError(
                f"Encryption is already enabled for storage_def={storage_def_name}."
            )
        try:
            credential = atbu_cfg.get_storage_def_encryption_credential(
                storage_def_name=storage_def_name, unlock=True
            )
        except (PasswordAuthenticationFailure, CredentialSecretDerivationError) as ex:
            if ex.message:
                print(ex.message)
            raise

    #
    # Generate/store random 256-bit private key.
    # Associate the user's password with the private key.
    #
    print(
        """
You can require the backup to ask for a password before starting a backup/restore,
or you can allow a backup to proceed automatically without requiring your password.

When you choose the automatic approach which does not require a password, you are
allowing your backup 'private key' to be used automatically by this program. When
doing this, your backup private key is stored in a manner where, not only this
program, but other programs and people who have access to your computer or its
contents may be able to access and use your private key.

You can switch between requiring your password or using the automatic approach as
needed/desired. Regardless of your choice, you should be certain to back up your
security information (i.e., private key, related info) which you can do at any time.

"""
    )
    a = prompt_YN(
        prompt_msg="Choose whether to require password or not.",
        prompt_question="Require a (p)assword or allow (a)utomatic use of your backup's private key? ",
        default_enter_ans="a",
        choices={"p": "[P/a]", "a": "[p/A]"},
    )

    if not credential:
        print(f"Creating key...", end="")
        credential = Credential()
        credential.create_key()
        print(f"created.")

    if debug_mode:
        print(f"set_encryption_password_wizard: key={credential.the_key.hex(' ')}")

    if a == "a":
        cred_operation = CRED_OPERATION_SET_PASSWORD_TO_PRIVATE_KEY
    else:
        cred_operation = CRED_OPERATION_SET_PASSWORD
        print(
            """
You have chosen to require a password before a backup/restore can begin which requires you
to enter a password.
"""
        )
        password = prompt_for_password(
            prompt="Enter a password for this backup:",
            prompt_again="Enter a password for this backup again:",
        )
        credential.prepare_for_new_password()
        credential.set(password=password)
        print(f"Encrypting key...", end="")
        credential.encrypt_key()
        print(f"encrypted.")
        credential.clear_password()

    print(f"Storing...")
    handle_credential_change(
        operation=cred_operation,
        key_to_affect=CRED_KEY_TYPE_ENCRYPTION,
        atbu_cfg=atbu_cfg,
        storage_def_name=storage_def_name,
        credential=credential,
        debug_mode=debug_mode,
    )


def setup_backup_encryption_wizard(
    storage_atbu_cfg: AtbuConfig, storage_def_name: str, debug_mode: bool = False
) -> bool:
    a = prompt_YN(
        prompt_msg="The destination can be encrypted.",
        prompt_question="Would you like encryption enabled?",
    )
    is_encrypted = False
    if a == "y":
        set_encryption_password_wizard(
            atbu_cfg=storage_atbu_cfg,
            storage_def_name=storage_def_name,
            debug_mode=debug_mode,
        )
        print(f"Your key is stored.")
        is_encrypted = True
    else:
        print(f"Files backed up to this destination will *not* be encrypted.")
    print(f"Saving {storage_atbu_cfg.path}")
    storage_atbu_cfg.save_config_file()
    print(f"{storage_atbu_cfg.path} has been saved.")
    return is_encrypted


def is_OAuth2_secret_json_file(path: str) -> bool:
    if path is None or not os.path.isfile(path):
        return False
    # There is a candidate file, see if it ends with .json and contains expected fields...
    logging.info(
        f"Secret seems to reference a file either directly or indirectly: {path}"
    )
    if not path.lower().endswith(".json"):
        logging.warning(f"No .json extension, will not use file as secret: {path}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as cred_file:
            c: dict = json.load(cred_file)
        if c.get("type") is None and c.get("private_key") is None:
            logging.warning(
                f"No 'type' or 'private_key' fields found, will not use file as secret: {path}"
            )
            return False
        # It appears to be a file, such as service account file (i.e., with OAuth2 creds)...
        logging.info(f"Secret will be considered a reference to a file: {path}")
        return True
    except Exception:
        logging.warning(f"Cannot open file, will not use file as secret: {path}")
        return False


def handle_container_auto_creation(
    storage_def_name: str, try_create_if_not_autofind: bool
) -> bool:
    atbu_config = AtbuConfig.access_default_config()
    storage_def_dict = atbu_config.get_storage_def_dict(
        storage_def_name=storage_def_name
    )
    if storage_def_dict is None:
        raise StorageDefinitionNotFoundError(
            f"Cannot find storage defintion '{storage_def_name}'."
        )
    container_name = storage_def_dict[CONFIG_VALUE_NAME_CONTAINER]
    auto_find_name = container_name[-1] == AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR
    if not auto_find_name and not try_create_if_not_autofind:
        # Auto find implies a need to create a container, whereas just
        # the name requires --create-container. If neither auto find
        # nor --create-container, return.
        return False
    if auto_find_name:
        logging.info(
            f"Container name had the {AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR} auto-find/create indicator. "
            f"Searching for unique container name using base name {container_name}..."
        )
    factory = StorageInterfaceFactory.create_factory_from_storage_def_name(
        storage_def_name=storage_def_name
    )
    container_name = factory.storage_def_dict[CONFIG_VALUE_NAME_CONTAINER]
    interface = factory.create_storage_interface()
    try:
        ci = interface.create_container(container_name=container_name)
        logging.info(f"Found/created container name '{ci.name}'.")
        logging.info(f"Updating configuration with that new name.")
    except ContainerAlreadyExistsError:
        logging.warning(
            f"WARNING: The container name chosen already exists: {container_name}"
        )
        logging.warning(
            f"If you do not intend to use this container name, try againg with a different name."
        )
        logging.info(f"Using container name '{container_name}'.")
        logging.info(f"Updating configuration with that existing name.")
    except InvalidContainerNameError:
        logging.error(f"The container name is invalid: {container_name}")
        raise
    except ContainerAutoCreationFailed as ex:
        logging.error(exc_to_string(ex))
        logging.error(
            f"Auto find container with creation failed for name '{container_name}' "
            f"Check the errors and the name."
        )
        raise
    storage_def_dict[CONFIG_VALUE_NAME_CONTAINER] = ci.name
    atbu_config.save_config_file()
    return True


def handle_create_storage_definition(
    storage_def_name: str,
    interface: str,
    provider: str,
    container: str,
    driver_params: str,
    create_container: bool,
    include_iv: bool,
    debug_mode: bool = False,
):
    # Disable MP queued logging to ensure any console
    # logging is in sync with print statements.
    switch_to_non_queued_logging()

    atbu_cfg = AtbuConfig.access_default_config()

    if not storage_def_name:
        raise ValueError(
            f"Invalid name storage_def_name '{storage_def_name}' specified."
        )
    if not interface:
        raise ValueError(f"Invalid name interface '{interface}' specified.")
    if not provider:
        raise ValueError(f"Invalid name provider '{provider}' specified.")
    if not container:
        raise ValueError(f"Invalid name container '{container}' specified.")
    if not driver_params:
        raise ValueError(f"Invalid name container '{driver_params}' specified.")

    if atbu_cfg.is_storage_def_exists(storage_def_name=storage_def_name):
        raise StorageDefinitionAlreadyExists(
            f"The storage definition '{storage_def_name}' already exists. Delete it first, or choose a different name."
        )

    storage_def_name = storage_def_name.lower()
    if not is_storage_def_name_ok(storage_def_name=storage_def_name):
        raise InvalidStorageDefinitionName(
            f"The name '{storage_def_name}' is invalid. Allowed characters: lowercase alphanumeric, underscore, hyphen/dash."
        )

    secret = CredentialByteArray()
    m = re.match(r".*,secret=([^,]+)", driver_params)
    if m:
        # A base64 secret may contain '=' so remove and parse separately.
        secret = CredentialByteArray(m.groups()[0].encode("utf-8"))
        driver_params = re.sub(r",\s*secret=([^,]+)", "", driver_params)
    other_driver_kv_pairs = dict(
        kv_pair.split("=") for kv_pair in driver_params.split(",")
    )

    other_driver_kv_pairs[CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET] = secret

    _, _ = atbu_cfg.create_storage_def(
        interface_type=interface,
        provider_id=provider,
        container=container,
        other_driver_kv_pairs=other_driver_kv_pairs,
        unique_storage_def_name=storage_def_name,
        include_iv=include_iv,
    )

    operation = CRED_OPERATION_SET_PASSWORD
    secret_str = secret.decode("utf-8")
    if os.path.isfile(secret_str) and is_OAuth2_secret_json_file(path=secret_str):
        # Yes, secret is directly an existing file name.
        operation = CRED_OPERATION_SET_PASSWORD_TO_FILENAME
    else:
        # Not a direct file name.
        # Check if env var.
        ev = os.getenv(secret_str)
        if isinstance(ev, str) and is_OAuth2_secret_json_file(path=ev):
            # Yes, env var is file.
            operation = CRED_OPERATION_SET_PASSWORD_TO_ENVVAR

    try:
        # Save to keyring and indirect storage definition to reference the keyring creds.
        handle_credential_change(
            operation=operation,
            key_to_affect=CRED_KEY_TYPE_STORAGE,
            atbu_cfg=atbu_cfg,
            storage_def_name=storage_def_name,
            credential=secret,
            debug_mode=debug_mode,
        )

        atbu_cfg.save_config_file()

        logging.info(f"Storage definition {storage_def_name} saved.")
        logging.debug(f"Storage definition {storage_def_name} saved to {atbu_cfg.path}")

        is_encrypted = setup_backup_encryption_wizard(
            storage_atbu_cfg=atbu_cfg,
            storage_def_name=storage_def_name,
            debug_mode=debug_mode,
        )

        if not is_encrypted:
            logging.warning(
                f"WARNING: The storage definition '{storage_def_name}' will *not* be encrypted."
            )
        else:
            logging.info(
                f"The storage definition '{storage_def_name}' will be encrypted."
            )

        handle_container_auto_creation(
            storage_def_name=storage_def_name,
            try_create_if_not_autofind=create_container,
        )

        logging.info(f"Storage definition {storage_def_name} successfully created.")
    except Exception as ex:
        message = str(ex)
        if isinstance(ex, AtbuException):
            message = ex.message
        if atbu_cfg.is_storage_def_exists(storage_def_name=storage_def_name):
            logging.warning(
                f"Due to error, deleting storage definition '{storage_def_name}'. {message} {exc_to_string(ex)}"
            )
            atbu_cfg.delete_storage_def(storage_def_name=storage_def_name)
            atbu_cfg.save_config_file()
        raise


def handle_delete_storage_definition(
    storage_def_name: str, skip_confirmation_prompt: bool = False
):
    switch_to_non_queued_logging()
    atbu_cfg = AtbuConfig.access_default_config()
    if not atbu_cfg.is_storage_def_exists(storage_def_name=storage_def_name):
        print(f"The storage definition '{storage_def_name}' does not exist.")
        return

    if not skip_confirmation_prompt:
        print(
            f"""
    *** WARNING *** WARNING *** WARNING *** WARNING *** WARNING *** WARNING
    The storage definition '{storage_def_name}' exists.
    If this is an encrypted backup where the private key is not backed up,
    you will lose access to all data in this backup if you delete this
    configuration.
    """
        )
        a = prompt_YN(
            prompt_msg=f"You are about to delete a backup storage definition.",
            prompt_question=f"Are you certain you want to delete '{storage_def_name}' ",
            default_enter_ans="n",
        )
        if a != "y":
            print("The storage definition will not be deleted.")
            return
    atbu_cfg.delete_storage_def(storage_def_name=storage_def_name)
    atbu_cfg.save_config_file()
    print("The storage definition was deleted.")


def handle_creds(args):
    logging.debug(f"handle_creds")
    storage_def_name = args.storage_def
    orig_storage_def_name = storage_def_name  # pylint: disable=unused-variable
    storage_atbu_cfg: AtbuConfig
    show_secrets = False
    if hasattr(args, "show_secrets"):
        show_secrets = args.show_secrets
    if not is_existing_filesystem_storage_path(storage_location=storage_def_name):
        #
        # Storage definition is not a filesystem storage.
        # It must therefore be a storage-def-specifier or simply/directly the storage_def_name itself.
        # Resolve to a storage_def_name...
        #
        parsed_name = parse_storage_def_specifier(storage_location=storage_def_name)
        if parsed_name:
            storage_def_name = parsed_name
        storage_atbu_cfg = AtbuConfig.access_default_config()
    else:
        #
        # Filesystem storage.
        #
        storage_atbu_cfg, storage_def_name, _ = AtbuConfig.access_filesystem_config(
            storage_location_path=storage_def_name,
            create_if_not_exist=True,
            prompt_to_create=True,
        )
    if args.subcmd == "create-storage-def":
        handle_create_storage_definition(
            storage_def_name=storage_def_name,
            interface=args.interface,
            provider=args.provider,
            container=args.container,
            driver_params=args.driver_params,
            create_container=args.create_container,
            include_iv=args.include_iv,
            debug_mode=show_secrets,
        )
    elif args.subcmd == "delete-storage-def":
        handle_delete_storage_definition(
            storage_def_name=storage_def_name, skip_confirmation_prompt=args.force
        )
    elif args.subcmd == "export":
        backup_file_path = args.filename
        if not backup_file_path:
            raise InvalidCommandLineArgument(
                f"You must specify a filename to save the storage definition to."
            )
        if os.path.isdir(backup_file_path):
            raise InvalidCommandLineArgument(
                f"The specified file is a directory: {backup_file_path}"
            )
        if os.path.isfile(backup_file_path) and not args.overwrite:
            raise InvalidCommandLineArgument(
                f"The file already exists: {backup_file_path}"
            )
        storage_atbu_cfg.save_storage_def_with_cleartext_secrets(
            storage_def_name=storage_def_name, backup_file_path=backup_file_path
        )
    elif args.subcmd == "import":
        switch_to_non_queued_logging()
        # TODO: Handle args.create_config
        backup_file_path = args.filename
        if not backup_file_path:
            raise InvalidCommandLineArgument(
                f"You must specify the filename of the storage definition and "
                f"credentials to restore."
            )
        if os.path.isdir(backup_file_path):
            raise InvalidCommandLineArgument(
                f"The specified file is a directory: {backup_file_path}"
            )
        if not os.path.isfile(backup_file_path):
            raise InvalidCommandLineArgument(
                f"The file does not exist: {backup_file_path}"
            )
        storage_atbu_cfg.restore_storage_def(
            storage_def_new_name=storage_def_name,
            backup_file_path=backup_file_path,
            prompt_if_exists=args.prompt,
        )
    elif args.subcmd == "set-password":
        operation = CRED_OPERATION_SET_PASSWORD
        if args.key_type == CRED_KEY_TYPE_ENCRYPTION:
            if args.password is not None:
                logging.error(
                    f"A command line password cannot be specified for {CRED_KEY_TYPE_ENCRYPTION}, "
                    f"only for {CRED_KEY_TYPE_STORAGE}."
                )
                logging.info(
                    f"To change the {CRED_KEY_TYPE_ENCRYPTION} password, do not specify a password "
                    f"on the command line which allows a console UI to prompt you."
                )
                raise CredentialRequestInvalidError(
                    f"A command line password cannot be specified for {CRED_KEY_TYPE_ENCRYPTION}."
                )
            set_encryption_password_wizard(
                atbu_cfg=storage_atbu_cfg,
                storage_def_name=storage_def_name,
                encryption_already_enabled_ok=True,
                debug_mode=show_secrets,
            )
        elif args.key_type == CRED_KEY_TYPE_STORAGE:
            if args.password is None:
                raise CredentialRequestInvalidError(
                    f"A password is required to set the password for the {CRED_KEY_TYPE_STORAGE}."
                )
            handle_credential_change(
                operation=operation,
                key_to_affect=args.key_type,
                atbu_cfg=storage_atbu_cfg,
                storage_def_name=storage_def_name,
                credential=args.password,
                debug_mode=show_secrets,
            )
        else:
            raise InvalidStateError(f"Unexpected key type '{args.key_type}'")
    elif args.subcmd == "set-password-filename":
        if args.filename is None:
            raise CredentialRequestInvalidError(
                f"A filename is required to set the password filename for the {CRED_KEY_TYPE_STORAGE}."
            )
        operation = CRED_OPERATION_SET_PASSWORD_TO_FILENAME
        handle_credential_change(
            operation=operation,
            key_to_affect=CRED_KEY_TYPE_STORAGE,
            atbu_cfg=storage_atbu_cfg,
            storage_def_name=storage_def_name,
            credential=args.filename,
            debug_mode=show_secrets,
        )
    elif args.subcmd == "set-password-envvar":
        operation = CRED_OPERATION_SET_PASSWORD_TO_ENVVAR
        if args.key_type == CRED_KEY_TYPE_STORAGE:
            handle_credential_change(
                operation=operation,
                key_to_affect=args.key_type,
                atbu_cfg=storage_atbu_cfg,
                storage_def_name=storage_def_name,
                credential=args.env_var,
                debug_mode=show_secrets,
            )
        else:
            raise InvalidStateError(f"Key type '{args.key_type} not allowed.'")
    else:
        raise InvalidCommandLineArgument("Unknown command.")
