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
from send2trash import send2trash

from atbu.common.util_helpers import get_trash_bin_name, prompt_YN
from atbu.mp_pipeline.mp_global import switch_to_non_queued_logging

from .exception import *
from .constants import *
from .config import (
    AtbuConfig,
    is_existing_filesystem_storage_path,
    is_storage_def_name_ok,
    parse_storage_def_specifier,
)
from .storage_def_credentials import StorageDefCredentialSet
from .credentials import (
    Credential,
    CredentialAesKey,
    CredentialByteArray,
    DescribedCredential,
    prompt_for_password,
    prompt_for_password_with_yubikey_opt,
)
from .storage_interface.base import (
    AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR,
    StorageInterfaceFactory,
)


def password_prompt(
    what: str = None,
    hidden: bool = True,
) -> CredentialByteArray:

    if what is None:
        what = "password"

    def _is_password_valid(password: CredentialByteArray) -> bool:
        MAX_SIZE_IN_BYTES = 500  # Arbitrary, big enough.
        if len(password) > MAX_SIZE_IN_BYTES:
            print(f"The {what} you entered is too long.")
            print(f"The maximum length is {MAX_SIZE_IN_BYTES} UTF-8 encoded bytes.")
            return False
        return True

    return prompt_for_password(
        prompt=f"Enter {what}:",
        hidden=hidden,
        is_password_valid_func=_is_password_valid,
    )


def backup_password_prompt_wizard() -> CredentialByteArray:
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
        prompt_question=(
            "Require a (p)assword or allow (a)utomatic use of your backup's private key? "
        ),
        default_enter_ans="a",
        choices={"p": "[P/a]", "a": "[p/A]"},
    )

    if a == "a":
        return None
    else:
        print(
            """
You have chosen to require a password before a backup/restore can begin which requires you
to enter a password.
"""
        )
        password = prompt_for_password_with_yubikey_opt(
            prompt="Enter a password for this backup:",
            prompt_again="Enter a password for this backup again:",
        )
    return password


def setup_backup_encryption_wizard(
    storage_atbu_cfg: AtbuConfig, storage_def_name: str, debug_mode: bool = False
) -> DescribedCredential:
    """Setup a password for the backup encryption credential if desired by user.

    Args:
        storage_atbu_cfg (AtbuConfig): The configuration to use.
        storage_def_name (str): The storage definition name.
        debug_mode (bool, optional): Output debug info if True. Defaults to False.

    Raises:
        EncryptionAlreadyEnabledError: Encryption already enabled for the specified
            storage definition configuration.

    Returns:
        DescribedCredential: The DescribedCredential with a credential attribute
            that has its password in the clear if a password was specified.
    """
    a = prompt_YN(
        prompt_msg="The destination can be encrypted.",
        prompt_question="Would you like encryption enabled?",
    )
    credential: CredentialAesKey = None
    if a != "y":
        print(f"Files backed up to this destination will *not* be encrypted.")
        return None

    if storage_atbu_cfg.is_storage_def_configured_for_encryption(
        storage_def_name=storage_def_name
    ):
        raise EncryptionAlreadyEnabledError(
            f"Encryption is already enabled for storage_def={storage_def_name}."
        )
    cba_password = backup_password_prompt_wizard()
    print(f"Creating backup encryption key...", end="")
    credential = CredentialAesKey()
    credential.create_key()
    print(f"created.")
    if cba_password is not None:
        print(f"Setting password.")
        credential.set(password=cba_password)
    else:
        print(
            f"No password set because you want to keep the backup encryption key unencrypted."
        )

    return DescribedCredential(
        credential=credential,
        config_name=storage_def_name,
        credential_name=CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
        credential_kind=CONFIG_PASSWORD_KIND_ACTUAL,
    )


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
            f"Container name had the {AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR} "
            f"auto-find/create indicator. "
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
            f"The storage definition '{storage_def_name}' already exists. "
            f"Delete it first, or choose a different name."
        )

    storage_def_name = storage_def_name.lower()
    if not is_storage_def_name_ok(storage_def_name=storage_def_name):
        raise InvalidStorageDefinitionName(
            f"The name '{storage_def_name}' is invalid. Allowed characters: "
            f"lowercase alphanumeric, underscore, hyphen/dash."
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

    _, storage_def_dict = atbu_cfg.create_storage_def(
        interface_type=interface,
        provider_id=provider,
        container=container,
        other_driver_kv_pairs=other_driver_kv_pairs,
        unique_storage_def_name=storage_def_name,
        include_iv=include_iv,
    )

    #
    # Determine storage credential type (i.e., password, file, or env var file).
    #

    cred_storage_kind = CONFIG_PASSWORD_KIND_ACTUAL
    secret_str = secret.decode("utf-8")
    if os.path.isfile(secret_str) and is_OAuth2_secret_json_file(path=secret_str):
        # Yes, secret is directly an existing file name.
        cred_storage_kind = CONFIG_PASSWORD_KIND_FILENAME
    else:
        # Not a direct file name.
        # Check if env var.
        ev = os.getenv(secret_str)
        if isinstance(ev, str) and is_OAuth2_secret_json_file(path=ev):
            # Yes, env var is file.
            cred_storage_kind = CONFIG_PASSWORD_KIND_ENVVAR

    #
    # Create/save the credentials.
    #

    try:

        #
        # Create the backup encryption credential.
        # If no encryption, desc_cred_encryption is None.
        #

        desc_cred_encryption = setup_backup_encryption_wizard(
            storage_atbu_cfg=atbu_cfg,
            storage_def_name=storage_def_name,
            debug_mode=debug_mode,
        )

        #
        # Create the storage credential.
        # If there is an encryption credential, and it is password-protected,
        # use the same password to protect the storage credential.
        #

        cred_storage = Credential(the_key=secret)
        if desc_cred_encryption is not None:
            cred_encryption = desc_cred_encryption.credential
            if cred_encryption.is_password_protected:
                cred_storage.set(password=cred_encryption.password)

        desc_cred_storage = DescribedCredential(
            credential=cred_storage,
            config_name=storage_def_name,
            credential_name=CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
            credential_kind=cred_storage_kind,
        )

        #
        # Create a credential set to hold/lock/save all credentials.
        #

        cred_set = StorageDefCredentialSet(
            storage_def_name=storage_def_name,
            storage_def_dict=storage_def_dict,
        )
        if desc_cred_encryption is not None:
            cred_set.append(
                desc_cred=desc_cred_encryption,
                affected_config_path_parts=CRED_SECRET_KIND_ENCRYPTION.split("-"),
            )
        cred_set.append(
            desc_cred=desc_cred_storage,
            affected_config_path_parts=CRED_SECRET_KIND_STORAGE.split("-"),
        )

        #
        # Lock and save all credentials.
        #

        print(f"Storing...")
        cred_set.protect()
        cred_set.save()
        print(f"Credentials stored.")
        print(f"Saving {atbu_cfg.path}")
        atbu_cfg.save_config_file()
        logging.info(f"Storage definition {storage_def_name} saved.")
        logging.debug(f"Storage definition {storage_def_name} saved to {atbu_cfg.path}")

        if desc_cred_encryption is None:
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
                f"Due to error, deleting storage definition '{storage_def_name}'. "
                f"{message} {exc_to_string(ex)}"
            )
            atbu_cfg.delete_storage_def(storage_def_name=storage_def_name)
            atbu_cfg.save_config_file()
        raise


def handle_delete_storage_definition(
    storage_def_name: str,
    skip_confirmation_prompt: bool,
    delete_backup_info: bool,
):
    """Delete a storage definition.

    Args:
        storage_def_name: The storage definition name.
        skip_confirmation_prompt: If True, then no
            prompting will occur, definition will be
            deleted.
        delete_backup_info: If True, the backup information
            will also be deleted, if False the backup
            information will not be deleted. If None,
            and skip_confirmation_prompt==False, the
            user will be prompted about backup information,
            otherwise in the case of not prompting, the
            backup information will not be deleted. The
            goal is to be cautious about deleting backup
            informoation despite it being recoverable from
            a good backup. Essentially, the user must be
            explicitly one way or another about including
            backup information in the deletion process.
    """
    switch_to_non_queued_logging()
    bin_name = get_trash_bin_name()
    atbu_cfg = AtbuConfig.access_default_config()
    if not atbu_cfg.is_storage_def_exists(storage_def_name=storage_def_name):
        print(f"The storage definition '{storage_def_name}' does not exist.")
        return

    existing_backup_info = atbu_cfg.get_backup_info_file_paths(
        storage_def_name=storage_def_name
    )

    if not skip_confirmation_prompt:
        print(
            f"""*** WARNING *** WARNING *** WARNING *** WARNING *** WARNING *** WARNING
The storage definition '{storage_def_name}' exists.
If this is an encrypted backup where the private key is not backed up,
you *will* *lose* *access* to all data in this backup if you delete this
configuration.
"""
        )
        if (
            delete_backup_info is not None  # If user was explicit
            and delete_backup_info  # and user said Yes to deleting BI
            and len(existing_backup_info) > 0  # and there is BI to delete
        ):
            print()
            print(
                f"""If you delete this storage definition, the following backup information
will also be deleted:
"""
            )
            print()
            for bip in existing_backup_info:
                print(f"    {bip}")
            print()
        a = prompt_YN(
            prompt_msg=f"You are about to delete a backup storage definition.",
            prompt_question=f"Are you certain you want to delete '{storage_def_name}' ",
            default_enter_ans="n",
        )
        if a != "y":
            print("The storage definition will not be deleted.")
            return
        if (
            delete_backup_info is None  # user was not explicit
            and len(existing_backup_info) > 0  # there is BI to delete
        ):
            print()
            print(f"This storage definition also has backup information as follows:")
            print()
            for bip in existing_backup_info:
                print(f"    {bip}")
            print()
            print(
                f"""If you are planning to immediately re-import this same configuration,
or you otherwise need this backup information, you should not delete it.

While this backup information is typically recoverable from a non-corrupt
backup, it is generally a good idea to err on the side of caution and back
it up if you are uncertain.

If you choose 'y' below to delete the above files, they will no longer be
available. This app will attempt to send the files to the {bin_name},
so you may be able to recover them from there if needed.

If you choose *not* to delete these files along with the storage definition,
and you later attempt import/recovery of a storage definition of the same name,
the lingering presence of these older files may interfere or be out of sync with
that newly imported configuration.
                """
            )
            a = prompt_YN(
                prompt_msg=(
                    f"Choose whether to also delete the above backup information files (a=abort)."
                ),
                prompt_question=(
                    f"Delete backup information files along with '{storage_def_name}' "
                ),
                default_enter_ans="a",
                choices={"y": "[Y/n/a]", "n": "[y/N/a]", "a": "[y/n/A]"},
            )
            if a == "a":
                print("The storage definition will not be deleted.")
                return
            delete_backup_info = a == "y"
    logging.info(f"Deleting storage definition '{storage_def_name}'...")
    atbu_cfg.delete_storage_def(storage_def_name=storage_def_name)
    logging.info(f"Saving configuration file {atbu_cfg.path}...")
    atbu_cfg.save_config_file()
    if delete_backup_info:
        logging.info("Deleting backup information...")
        for bip in existing_backup_info:
            logging.info(f"    Sending file to {bin_name}: {bip}")
            send2trash(bip)
    elif len(existing_backup_info) > 0:
        logging.info(f"Skipping deletion of the following backup information...")
        for bip in existing_backup_info:
            logging.info(f"    {bip}")
    else:
        logging.info(f"There is no backup information for '{storage_def_name}'.")
    logging.info(f"The storage definition '{storage_def_name}' was deleted.")


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
        # It must therefore be a storage-def-specifier or
        # simply/directly the storage_def_name itself.
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
    if args.subcmd == CREDS_SUBCMD_CREATE_STORAGE_DEF:
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
            storage_def_name=storage_def_name,
            skip_confirmation_prompt=args.force,
            delete_backup_info=args.delete_backup_info,
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
    elif args.subcmd in [
        CRED_OPERATION_SET_PASSWORD,
        CRED_OPERATION_SET_PASSWORD_ALIAS,
    ]:

        switch_to_non_queued_logging()

        storage_def_dict = storage_atbu_cfg.get_storage_def_dict(
            storage_def_name=storage_def_name,
            must_exist=True,
        )

        cred_set = StorageDefCredentialSet(
            storage_def_name=storage_def_name,
            storage_def_dict=storage_def_dict,
        )

        cred_set.populate()
        cred_set.unprotect()

        password_type = args.password_type

        if password_type == CRED_OPERATION_SET_PASSWORD_TYPE_BACKUP:
            if args.password is not None:
                raise CredentialRequestInvalidError(
                    f"A command line password cannot be specified for the "
                    f"{CRED_OPERATION_SET_PASSWORD_TYPE_BACKUP} password."
                )
            cba_password = backup_password_prompt_wizard()
            cred_set.set_password(cba_password)
        elif password_type == CRED_OPERATION_SET_PASSWORD_TYPE_STORAGE:
            desc_cred_storage = cred_set.get_storage_desc_cred()
            if args.password is None:
                cba_password = password_prompt(what="storage secret", hidden=False)
            else:
                cba_password = CredentialByteArray.create_from_string(args.password)
            desc_cred_storage.credential.set(the_key=cba_password)
            desc_cred_storage.credential_kind = CONFIG_PASSWORD_KIND_ACTUAL
        elif password_type == CRED_OPERATION_SET_PASSWORD_TYPE_FILENAME:
            desc_cred_storage = cred_set.get_storage_desc_cred()
            if args.password is None:
                cba_password = password_prompt(
                    what="OAuth2 .json file path",
                    hidden=False,
                )
            else:
                cba_password = CredentialByteArray.create_from_string(args.password)
            desc_cred_storage.credential.set(the_key=cba_password)
            desc_cred_storage.credential_kind = CONFIG_PASSWORD_KIND_FILENAME
        elif password_type == CRED_OPERATION_SET_PASSWORD_TYPE_ENVVAR:
            desc_cred_storage = cred_set.get_storage_desc_cred()
            if args.password is None:
                cba_password = password_prompt(
                    what="OAuth2 .json file path environment variable",
                    hidden=False,
                )
            else:
                cba_password = CredentialByteArray.create_from_string(args.password)
            desc_cred_storage.credential.set(the_key=cba_password)
            desc_cred_storage.credential_kind = CONFIG_PASSWORD_KIND_ENVVAR
        else:
            raise InvalidStateError(f"Unexpected password type '{password_type}'")

        print(f"Storing credentials...")
        cred_set.protect()
        cred_set.save()
        print(f"Credentials stored.")
    else:
        raise InvalidCommandLineArgument("Unknown command.")
