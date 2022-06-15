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
r"""ATBU Configuration-related classes/functions.
- AtbuConfig is the primary class.
"""

import base64
import fnmatch
import glob
import logging
import os
from pathlib import Path
import re
from typing import Union
import uuid
import copy
import json
import keyring

from atbu.mp_pipeline.mp_global import get_verbosity_level
from atbu.common.util_helpers import (
    convert_to_pathlib_path,
    deep_union_dicts,
    is_absolute_path,
    is_valid_base64_string,
    prompt_YN,
)

from .constants import *
from .exception import *
from .credentials import (
    Credential,
    CredentialByteArray,
    get_password_from_keyring,
    get_enc_credential_from_keyring,
    set_password_to_keyring,
)


def parse_storage_def_specifier(storage_location) -> str:
    what_which = storage_location.lower().split(":", maxsplit=1)
    is_storage_definition_specifier = (
        len(what_which) == 2
        and len(what_which[0]) > 2  # ensure two components
        and what_which[0]  # disambiguate "storage:" specifier from drive letter.
        == CONFIG_SECTION_STORAGE_DEFINITION_SPECIFIER_PREFIX[: len(what_which[0])]
    )
    if is_storage_definition_specifier:
        return what_which[1]
    return None


def get_default_config_dir():
    return Path.home() / ATBU_DEFAULT_CONFIG_DIR_NAME


def get_default_config_file_path():
    return get_default_config_dir() / ATBU_DEFAULT_CONFIG_FILE_NAME


def update_config_list_to_dict(items: list):
    """Given the path/name and value pairs in the items list, build a dict
    with all config values represented by items.

    Example::

        given items=[("a.b.c","1"), ("a.e.f","2")]
        return {
            "a": {
                "b": {
                    "c": "1"
                }
                "e": {
                    "f": "2"
                }
            }
        }

"""
    if not isinstance(items, list):
        raise ValueError(f"The items parameter must be a list")
    if not isinstance(items[0], tuple):
        if len(items) % 2 != 0:
            raise ValueError(
                f"Each config location/name must have an accompanying value."
            )
        it = iter(items)
        items = [*zip(it, it)]
    result = {}
    for p in items:
        dest_node = result
        updated_sections = p[0].split(".")
        value = p[1]
        for i, s in enumerate(updated_sections):
            if i >= len(updated_sections) - 1:
                break
            if s not in dest_node:
                dest_node[s] = {}
            dest_node = dest_node[s]
        if s is None:  # pylint: disable=undefined-loop-variable
            raise InvalidStateError(
                f"update_config_list_to_dict: expect 's' to be set "
                f"to one before last period-separated values."
            )
        dest_node[s] = value  # pylint: disable=undefined-loop-variable
    return result


def add_config_items(items: list, config: dict):
    """Merge the dict created from items into config, return the new config to caller."""
    if config is None:
        config = {}
    updates = update_config_list_to_dict(items=items)
    if get_verbosity_level() >= 2:
        logging.debug(f"add_config_items: updates={updates}")
    deep_union_dicts(dest=config, src=updates)
    return config


def add_path_value(
    storage_def_dict: dict, section_value_path: Union[str, list[str]], value: str
):
    if section_value_path is None:
        raise ValueError(f"section_path is required")
    if isinstance(section_value_path, str):
        section_value_path = section_value_path.split("/")
    if not section_value_path or not isinstance(section_value_path, list):
        raise ValueError(
            f"section_path must be in the format section/section/.../value_name"
        )
    value_cfg = storage_def_dict
    for s in section_value_path[:-1]:
        if s not in value_cfg:
            value_cfg[s] = {}
        value_cfg = value_cfg[s]
    value_cfg[section_value_path[-1]] = value


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


def restore_keyring_secrets(storage_def: dict):
    keyring_section: dict = storage_def.get(CONFIG_SECTION_KEYRING_MAPPING)
    if not keyring_section:
        return
    affected_config_path: str
    for affected_config_path, keyring_lookup_info in keyring_section.items():
        service_name = keyring_lookup_info[CONFIG_VALUE_NAME_KEYRING_SERVICE]
        username = keyring_lookup_info[CONFIG_VALUE_NAME_KEYRING_USERNAME]
        affected_config_path_parts = affected_config_path.split("-")
        affected_section = storage_def
        for section_part in affected_config_path_parts[:-1]:
            affected_section = affected_section[section_part]
        password_type = affected_section.get(CONFIG_PASSWORD_TYPE)
        if password_type is None:
            raise CredentialTypeNotFoundError(
                f"restore_keyring_secrets: Cannot find credential type."
            )
        cba_password = CredentialByteArray(
            affected_section[affected_config_path_parts[-1]].encode("utf-8")
        )

        if password_type == CONFIG_PASSWORD_TYPE_FILENAME:
            filename = base64.b64decode(cba_password.decode("utf-8")).decode("utf-8")
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
                    cba_password = CredentialByteArray(
                        base64.b64encode(user_specified_filename.encode())
                    )
                    break
                print(
                    f"ERROR: The filename entered does not exist: {user_specified_filename}"
                )
                print(
                    f"You must specify a path to an existing .json password file "
                    f"(i.e., a service account .json OAuth2 file)."
                )

        set_password_to_keyring(
            service_name=service_name,
            username=username,
            password_type=password_type,
            password_bytes=cba_password,
            password_is_base64=True,
        )
        affected_section[
            affected_config_path_parts[-1]
        ] = CONFIG_KEY_VALUE_KEYRING_INDIRECTION


re_not_allowed_cfg_name = re.compile(r"[^a-z0-9_-]")


def is_storage_def_name_ok(storage_def_name):
    return not re_not_allowed_cfg_name.search(storage_def_name)


def is_existing_filesystem_storage_path(storage_location: str):
    """An existing valid filesystem storage path has the following characteristics:

        It exists as a directory.

        It is specified as an absolute path. (For no other reason than to ensure the user specifies
            something explicit/clear.)
    """
    return os.path.isdir(storage_location) and is_absolute_path(storage_location)


def add_keyring_mapping(cfg: dict, section_value_path, service: str, username: str):
    """Add a keyring mapping for section_value_path.
    For example, if section_value_path=='encryption/key', create a 'keyring-mapping' dict named
    'encryption-key' which itself has two values service/username for use in setting/getting from
    the keyring.
    """
    if cfg is None:
        raise ValueError(f"cfg must be specified")
    if section_value_path is None:
        raise ValueError(f"section_path is required")
    if isinstance(section_value_path, str):
        section_value_path = section_value_path.split("/")
    if not section_value_path or not isinstance(section_value_path, list):
        raise ValueError(
            f"section_path must be in the format section/section/.../value_name"
        )
    if CONFIG_SECTION_KEYRING_MAPPING not in cfg:
        cfg[CONFIG_SECTION_KEYRING_MAPPING] = {}
    mapping_value_name = "-".join(section_value_path)
    if mapping_value_name not in cfg[CONFIG_SECTION_KEYRING_MAPPING]:
        cfg[CONFIG_SECTION_KEYRING_MAPPING][mapping_value_name] = {}
    cfg[CONFIG_SECTION_KEYRING_MAPPING][mapping_value_name][
        CONFIG_VALUE_NAME_KEYRING_SERVICE
    ] = service
    cfg[CONFIG_SECTION_KEYRING_MAPPING][mapping_value_name][
        CONFIG_VALUE_NAME_KEYRING_USERNAME
    ] = username


class AtbuConfigNode:
    def __init__(self, cfg: dict):
        self._cfg = cfg
        if not self._cfg:
            self._cfg = {}

    @property
    def cfg(self):
        return self._cfg

    @cfg.setter
    def cfg(self, value):
        self._cfg = value

    def set_config_from_items(self, items: list):
        """Interpret items as pairs of following...

            ['dot.separated.string', 'string_value', ...]

        ...where the first of the pair, the dot-sep string,
        is interpreted as a path into the dict config, where
        the last component is the value name, and 'string_value'
        its value.

        Note, this is not schema checked and is complete
        free-format so can cause invalid configurations.
        """
        if not isinstance(items, list) or len(items) % 2 != 0:
            raise ValueError(
                f"The items are invalid and must specify a two items, "
                f"a dot-separated path and value, for each affected config item. "
                f"items:{items}"
            )
        # Merge the caller-specified config nodes/values into the existing configuration.
        add_config_items(items, self._cfg)

    def _get_top_section(self, name) -> dict:
        section = self._cfg.get(name)
        if not section:
            self._cfg[name] = {}
            section = self._cfg[name]
        if not isinstance(section, dict):
            raise ConfigSectionNotFound(
                f"The section '{name}' config section is not the expected dictionary."
            )
        return section

    def get_json(self):
        return json.dumps(self._cfg, indent=4)


class AtbuConfig(AtbuConfigNode):

    STARTING_CONFIG = {
        CONFIG_VALUE_NAME_CONFIG_NAME: ATBU_CONFIG_NAME,
        CONFIG_VALUE_NAME_VERSION: ATBU_CONFIG_FILE_VERSION_STRING,
        CONFIG_SECTION_GENERAL: {},
        CONFIG_SECTION_STORAGE_DEFINITIONS: {},
    }

    def __init__(self, path: Union[str, Path], cfg: dict = None):
        super().__init__(cfg=cfg)
        self._path = convert_to_pathlib_path(path)

    @staticmethod
    def create_starting_config():
        return copy.deepcopy(AtbuConfig.STARTING_CONFIG)

    @staticmethod
    def create_from_file(path: Union[str, Path], create_if_not_exist: bool = False):
        atbu_cfg = AtbuConfig(path=path)
        atbu_cfg.load_config_file(create_if_not_exist=create_if_not_exist)
        return atbu_cfg

    @staticmethod
    def access_default_config(create_if_not_exist: bool = True):
        cfg = AtbuConfig(path=get_default_config_file_path())
        cfg.load_config_file(create_if_not_exist=create_if_not_exist)
        return cfg

    @staticmethod
    def access_filesystem_config(
        storage_location_path: Union[str, Path],
        resolve_storage_def_secrets: bool = False,
        create_if_not_exist: bool = True,
        prompt_to_create: bool = True,
    ) -> tuple[object, str, dict]:  # object is AtbuConfig
        storage_location_path = convert_to_pathlib_path(storage_location_path)
        storage_atbu_dir: Path = storage_location_path / ATBU_DEFAULT_CONFIG_DIR_NAME
        storage_atbu_cfg_path: Path = storage_atbu_dir / ATBU_DEFAULT_CONFIG_FILE_NAME
        if not storage_atbu_cfg_path.is_file():
            user_says_ok_to_create = "y"
            if prompt_to_create:
                print(
                    f"""
The configuration file does not exist: {storage_atbu_cfg_path}
If you specified the correct location and are aware there should not be an existing
configuration, you can choose to have one created for you.
"""
                )
                user_says_ok_to_create = prompt_YN(
                    prompt_msg=f"Config to create: {storage_atbu_cfg_path}",
                    prompt_question=f"Create config file at this location? ",
                    default_enter_ans="n",
                )
            if not create_if_not_exist or user_says_ok_to_create != "y":
                raise ConfigFileNotFoundError(
                    f"Cannot find the .atbu configuration file: {str(storage_atbu_cfg_path)}"
                )
        storage_atbu_cfg: AtbuConfig = AtbuConfig(path=storage_atbu_cfg_path)
        storage_atbu_cfg.load_config_file(create_if_not_exist=create_if_not_exist)
        storage_def_name, storage_def = storage_atbu_cfg.find_filesystem_storage_def(
            storage_path_to_find=storage_location_path
        )
        if resolve_storage_def_secrets and storage_def_name and storage_def:
            storage_def = (
                storage_atbu_cfg.get_storage_def_with_resolved_secrets_deep_copy(
                    storage_def_name=storage_def_name
                )
            )
        return storage_atbu_cfg, storage_def_name, storage_def

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        self._path = Path(value)

    def create_default_config(self):
        if not self._path:
            raise ValueError(
                "The path is not set, cannot create a default configuration."
            )
        logging.info(f"Writing new configuration: {self._path}")
        self._cfg = AtbuConfig.create_starting_config()
        self.save_config_file()

    def save_config_file(self):
        if self._path.is_file():
            backup_path: Path = self._path.with_suffix(self._path.suffix + ".bak")
            backup_path.unlink(missing_ok=True)
            self._path.rename(backup_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as config_file:
            config_file.write(json.dumps(self._cfg, indent=4))

    def load_config_file(self, create_if_not_exist: bool = True):
        if self._path.is_dir():
            raise ConfigFileNotFoundError(
                f"The path '{self._path}' must be a file not a directory."
            )
        if not self._path.exists():
            if create_if_not_exist:
                self.create_default_config()
            if not self._path.exists() or not self._path.is_file():
                raise ConfigFileNotFoundError(
                    f"The specified configuration file does "
                    f"not exist or is not a file. {self._path}"
                )
        cfg: dict = None
        try:
            with open(self._path, "r", encoding="utf-8") as cfg_file:
                cfg = json.load(cfg_file)
        except BaseException as err:
            logging.error(
                f"Specified configuration file exists and "
                f"appears to be invalid: {exc_to_string(err)}"
            )
            raise
        if (
            not cfg.get(CONFIG_VALUE_NAME_CONFIG_NAME)
            or cfg[CONFIG_VALUE_NAME_CONFIG_NAME] != ATBU_CONFIG_NAME
        ):
            logging.error(f"The config name is invalid: {self._path}")
            raise InvalidConfigurationFile(f"The config name is invalid: {self._path}")
        if (
            not cfg.get(CONFIG_VALUE_NAME_VERSION)
            or cfg[CONFIG_VALUE_NAME_VERSION] != "0.01"
        ):  # TODO change constants
            logging.error(f"The config version is invalid: {self._path}")
            raise InvalidConfigurationFile(
                f"The config version is invalid: {self._path}"
            )
        self._cfg = cfg

    def get_general_section(self) -> dict:
        return self._get_top_section(CONFIG_SECTION_GENERAL)

    def get_name(self) -> str:
        if not self.cfg:
            raise InvalidConfiguration(f"Cannot find the configuration.")
        name = self.cfg.get(CONFIG_VALUE_NAME_CONFIG_NAME)
        if not name:
            raise InvalidConfiguration(f"Cannot find the configuration's name.")
        return name

    def get_version(self) -> str:
        if not self.cfg:
            raise InvalidConfiguration(f"Cannot find the configuration.")
        version = self.cfg.get(CONFIG_VALUE_NAME_VERSION)
        if not version:
            raise InvalidConfiguration(f"Cannot find the configuration's name.")
        return version

    def validate_name_version(self):
        name = self.get_name()
        version = self.get_version()
        if name != ATBU_CONFIG_NAME:
            raise InvalidConfiguration(
                f"Invalid config name: Expected='{ATBU_CONFIG_NAME}' but got '{name}'"
            )
        if version != ATBU_CONFIG_FILE_VERSION_STRING:
            raise InvalidConfiguration(
                f"Invalid config version: "
                f"Expected='{ATBU_CONFIG_FILE_VERSION_STRING}' but got '{name}'"
            )

    def get_storage_defs_section(self) -> dict:
        return self._get_top_section(CONFIG_SECTION_STORAGE_DEFINITIONS)

    def get_storage_def_names(self, fnmatch_pattern="*") -> list[str]:
        fnmatch_pattern = fnmatch_pattern.lower()
        return [
            name
            for name in self.get_storage_defs_section().keys()
            if fnmatch.fnmatch(name, fnmatch_pattern)
        ]

    def find_filesystem_storage_def(
        self, storage_path_to_find: Path
    ) -> tuple[str, dict]:
        for storage_def_name, storage_def in self._cfg[
            CONFIG_SECTION_STORAGE_DEFINITIONS
        ].items():
            storage_def_path = Path(storage_def[CONFIG_VALUE_NAME_CONTAINER])
            if storage_path_to_find == storage_def_path:
                return storage_def_name, storage_def
        return None, None

    def get_backup_info_dir(self):
        backup_info_dir = self._path.parent / ATBU_DEFAULT_BACKUP_INFO_SUBDIR
        if not backup_info_dir.exists():
            backup_info_dir.mkdir(parents=True, exist_ok=True)
        if not backup_info_dir.is_dir():
            raise BackupInformationDirectoryNotFound(
                f"The backup information directory was not found: {str(backup_info_dir)}"
            )
        # TODO: The following is from a legacy approach, kept until certain it can be removed.
        g = self.get_general_section()
        g[CONFIG_VALUE_NAME_BACKUP_INFO_DIR] = str(backup_info_dir)
        self.save_config_file()
        return backup_info_dir

    def get_backup_info_file_paths(
        self,
        storage_def_name: str,
    ) -> list[str]:
        pattern = self.get_backup_info_dir() / f"{storage_def_name}*"
        return glob.glob(pathname=str(pattern))

    def resolve_storage_location(
        self,
        storage_location,
        resolve_storage_def_secrets=False,
        create_if_not_exist=False,
    ) -> tuple[object, str, dict]:  # object is AtbuConfig
        """Given a user-specified storage_location, try to resolve
        to an existing or newly created storage_def.

            Possible return values (always a tuple of 3):
                1)  (self, storage_def_name, storage_def):
                        storage_location is storage def specifier
                        defined in default ATBU configuration.
                2)  (storage_atbu_cfg, storage_def_name, storage_def):
                        storage_location is a file system storage whose
                3)  (None, None, None):
                        storage_location is not resolved to anything.
        """
        # Parse as potential specifier.
        storage_def_name = parse_storage_def_specifier(
            storage_location=storage_location
        )
        if storage_def_name:
            # Specifier found, if config exists, return it directly or with secrets resolved.
            # Return None if does not exist.
            storage_def = self.get_storage_def_dict(storage_def_name=storage_def_name)
            if resolve_storage_def_secrets and storage_def:
                # Resolve secrets before returning.
                storage_def = self.get_storage_def_with_resolved_secrets_deep_copy(
                    storage_def_name=storage_def_name
                )
            return self, storage_def_name, storage_def

        # Fall through if storage_def specifier not found.
        # See if storage_location is a filesystem storage.

        storage_atbu_cfg: AtbuConfig = None
        if is_existing_filesystem_storage_path(storage_location=storage_location):
            try:
                # storage_location is a directory specified as absolute path.
                (
                    storage_atbu_cfg,
                    storage_def_name,
                    storage_def,
                ) = AtbuConfig.access_filesystem_config(
                    storage_location_path=storage_location,
                    resolve_storage_def_secrets=resolve_storage_def_secrets,
                    create_if_not_exist=create_if_not_exist,
                )
                return storage_atbu_cfg, storage_def_name, storage_def
            except ConfigFileNotFoundError:
                pass
        # storage_location is not resolved.
        return None, None, None

    def get_storage_def_dict_deep_copy(self, storage_def_name: str) -> dict:
        # TODO search for usage re atbu_cfg
        storage_definitions = self.get_storage_defs_section()
        storage_def = storage_definitions.get(storage_def_name)
        if storage_def is not None:
            storage_def = copy.deepcopy(storage_def)
        return storage_def

    def get_storage_def_with_resolved_secrets_deep_copy(
        self, storage_def_name: str, keep_secrets_base64_encoded: bool = False
    ) -> dict:
        storage_def = self.get_storage_def_dict_deep_copy(
            storage_def_name=storage_def_name
        )
        if not storage_def:
            raise StorageDefinitionNotFoundError(
                f"Cannot find storage definition "
                f"{storage_def_name} in config file {str(self._path)}"
            )
        self._resolve_keyring_secrets(
            storage_def=storage_def, base64_encoded_secrets=keep_secrets_base64_encoded
        )
        return storage_def

    def get_storage_def_dict(self, storage_def_name, must_exist: bool = False) -> dict:
        storage_def_dict = self.get_storage_defs_section().get(storage_def_name)
        if must_exist and storage_def_dict is None:
            raise StorageDefinitionNotFoundError(
                f"The storage definition '{storage_def_name}' not found."
            )
        return storage_def_dict

    def get_only_storage_def_dict(self) -> dict:
        storage_def_section: dict = self.get_storage_defs_section()
        if len(storage_def_section) != 1:
            return None
        storage_def_name, storage_def = list(storage_def_section.items())[0]
        return storage_def_name, storage_def

    def is_storage_def_exists(self, storage_def_name) -> bool:
        return self.get_storage_def_dict(storage_def_name=storage_def_name) is not None

    def get_storage_def_compression_section(self, storage_def_name) -> dict:
        storage_def_dict = self.get_storage_def_dict(
            storage_def_name=storage_def_name,
            must_exist=True,
        )
        return storage_def_dict.get(CONFIG_SECTION_COMPRESSION)

    def get_compression_settings_deep_copy(self, storage_def_name) -> dict:
        compression_sect = self.get_storage_def_compression_section(
            storage_def_name=storage_def_name,
        )
        if compression_sect is not None:
            compression_sect = copy.deepcopy(compression_sect)
        else:
            compression_sect = {}
        if not isinstance(compression_sect, dict):
            raise ConfigSectionNotFound(
                f"For '{storage_def_name}' compression section, "
                f"expected dict but got {type(compression_sect)}"
            )
        for k, v in ATBU_BACKUP_COMPRESSION_DEFAULTS.items():
            if k not in compression_sect:
                compression_sect[k] = v
        return compression_sect

    def rename_storage_def(self, old_name, new_name):
        """Rename an existing storage def in this configuration."""
        AtbuConfig.rename_section_storage_def(
            config_section=self.get_storage_defs_section(),
            old_storage_def_name=old_name,
            new_storage_def_name=new_name,
        )

    def get_storage_def_encryption_section(self, storage_def_name) -> dict:
        storage_def = self.get_storage_def_dict(storage_def_name=storage_def_name)
        if not storage_def:
            return None
        return storage_def.get(CONFIG_SECTION_ENCRYPTION)

    def get_storage_def_keyring_mapping_section(self, storage_def_name) -> dict:
        storage_def = self.get_storage_def_dict(storage_def_name=storage_def_name)
        if not storage_def:
            return None
        return storage_def.get(CONFIG_SECTION_KEYRING_MAPPING)

    def get_storage_def_keyring_mapping_encryption_key_section(
        self, storage_def_name
    ) -> dict:
        keyring_mapping = self.get_storage_def_keyring_mapping_section(
            storage_def_name=storage_def_name
        )
        if not keyring_mapping:
            return None
        return keyring_mapping.get(CONFIG_SECTION_KEYRING_MAPPING_ENCRYPTION_KEY)

    def is_storage_def_configured_for_encryption(self, storage_def_name):
        storage_def = self.get_storage_def_dict(storage_def_name=storage_def_name)
        if not storage_def:
            return False
        enc_section: dict = storage_def.get(CONFIG_SECTION_ENCRYPTION)
        if enc_section is None:
            return False
        # The encryption section may exist before any encryption is enabled,
        # but if the "key" value is set, it means encryption has been enabled.
        if enc_section.get(CONFIG_VALUE_NAME_ENCRYPTION_KEY) is None:
            # Not enabled.
            return False
        # Enabled.
        return True

    def delete_storage_def_secrets(self, storage_def_name: str):
        try:
            keyring.delete_password(
                service_name=storage_def_name,
                username=CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
            )
        except keyring.errors.PasswordDeleteError:
            pass

        try:
            keyring.delete_password(
                service_name=storage_def_name,
                username=CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
            )
        except keyring.errors.PasswordDeleteError:
            pass

    def delete_storage_def(self, storage_def_name: str):
        if not self.is_storage_def_exists(storage_def_name=storage_def_name):
            return
        self.delete_storage_def_secrets(storage_def_name=storage_def_name)
        del self.get_storage_defs_section()[storage_def_name]

    def create_storage_def(
        self,
        interface_type: CONFIG_INTERFACE_HINT,
        provider_id: str,
        container: str,
        project: str = None,
        storage_key: str = None,
        storage_secret: str = None,
        other_driver_kv_pairs: dict = None,
        unique_storage_def_name: str = None,
        include_iv: bool = True,
        include_backup_info: bool = True,
    ) -> tuple[str, dict]:
        if not unique_storage_def_name:
            unique_storage_def_name = str(uuid.uuid4())
        unique_storage_def_name = unique_storage_def_name.lower()
        if self.is_storage_def_exists(unique_storage_def_name):
            raise StorageDefinitionAlreadyExists(
                f"The backup storage definition '{unique_storage_def_name}' already exists."
            )
        self.get_storage_defs_section()[unique_storage_def_name] = {
            CONFIG_VALUE_NAME_INTERFACE_TYPE: interface_type,
            CONFIG_VALUE_NAME_PROVIDER: provider_id,
            CONFIG_VALUE_NAME_CONTAINER: str(container),
            CONFIG_SECTION_DRIVER: {},
        }
        storage_def_dict = self.get_storage_defs_section()[unique_storage_def_name]
        driver_section = storage_def_dict[CONFIG_SECTION_DRIVER]
        if storage_key:
            driver_section[CONFIG_VALUE_NAME_DRIVER_STORAGE_KEY] = storage_key
        if storage_secret:
            driver_section[CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET] = storage_secret
        if project:
            driver_section[CONFIG_VALUE_NAME_DRIVER_STORAGE_PROJECT] = project
        if other_driver_kv_pairs:
            for k, v in other_driver_kv_pairs.items():
                driver_section[k] = v
        if include_iv != CONFIG_STORAGE_PERSISTED_IV_DEFAULT_VALUE:
            # Set include_iv since it is not the default value.
            storage_def_dict[CONFIG_SECTION_ENCRYPTION] = {
                CONFIG_VALUE_NAME_STORAGE_PERSISTED_IV: include_iv
            }
        if include_backup_info != CONFIG_STORAGE_PERSISTED_BACKUP_INFO_DEFAULT_VALUE:
            # Set value indicating whether or not to store backup information
            # to the file/cloud storage.
            storage_def_dict[
                CONFIG_VALUE_NAME_STORAGE_PERSISTED_BACKUP_INFO
            ] = include_backup_info
        return (
            unique_storage_def_name,
            storage_def_dict,
        )

    def create_filesystem_storage_def(
        self, storage_location_path: Path, unique_storage_def_name: str = None
    ) -> tuple[str, dict]:
        return self.create_storage_def(
            interface_type=CONFIG_INTERFACE_TYPE_FILESYSTEM,
            provider_id=CONFIG_INTERFACE_TYPE_FILESYSTEM,
            container=str(storage_location_path),
            unique_storage_def_name=unique_storage_def_name,
        )

    def is_filesystem_storage_def(self, storage_def_name: str) -> bool:
        sdd = self.get_storage_def_dict(storage_def_name=storage_def_name)
        if sdd is None:
            raise StorageDefinitionNotFoundError(
                f"The storage definition '{storage_def_name}' was not found."
            )
        return sdd[CONFIG_VALUE_NAME_INTERFACE_TYPE] == CONFIG_INTERFACE_TYPE_FILESYSTEM

    def save_storage_def_with_cleartext_secrets(
        self, storage_def_name: Union[str, list], backup_file_path: str
    ):
        if isinstance(storage_def_name, str):
            storage_def_name = [storage_def_name]
        if not isinstance(storage_def_name, list) or len(storage_def_name) == 0:
            raise ValueError(f"No storage definition names specified to restore.")
        # Get copy of current configuration, less storage definitions.
        cfg_for_save = copy.deepcopy(self._cfg)
        storage_definitions_section = {}
        cfg_for_save[CONFIG_SECTION_STORAGE_DEFINITIONS] = storage_definitions_section
        for name in storage_def_name:
            logging.info(f"Getting storage definition {name}...")
            storage_def_copy = self.get_storage_def_with_resolved_secrets_deep_copy(
                storage_def_name=name, keep_secrets_base64_encoded=True
            )
            storage_definitions_section[name] = storage_def_copy
        logging.info(f"Saving backup to {backup_file_path} ...")
        with open(backup_file_path, "w", encoding="utf-8") as backup_file:
            backup_file.write(json.dumps(cfg_for_save, indent=4))
        logging.info(f"Backup complete.")

    def restore_storage_def(
        self,
        storage_def_new_name: str,
        backup_file_path: str,
        prompt_if_exists: bool = True,
    ) -> bool:
        logging.info(f"Loading backup file {backup_file_path}...")
        atbu_stg_cfg = AtbuConfig.create_from_file(path=backup_file_path)
        atbu_stg_cfg.validate_name_version()
        (
            storage_def_old_name,
            storage_def_dict,
        ) = atbu_stg_cfg.get_only_storage_def_dict()
        if storage_def_new_name is None:
            storage_def_new_name = storage_def_old_name
        atbu_stg_cfg.rename_storage_def(
            old_name=storage_def_old_name,
            new_name=storage_def_new_name,
        )
        storage_def_name, storage_def_dict = atbu_stg_cfg.get_only_storage_def_dict()
        if storage_def_name != storage_def_new_name:
            raise InvalidStateError(
                f"Expected storage_def to have new name "
                f"'{storage_def_new_name}' but observed '{storage_def_name}'."
            )
        logging.info(f"Restoring secrets from backup file to keyring.")
        restore_keyring_secrets(storage_def=storage_def_dict)
        if storage_def_new_name in self.get_storage_defs_section():
            if prompt_if_exists:
                print(
                    f"""
*** WARNING *** WARNING *** WARNING *** WARNING *** WARNING *** WARNING
The storage definition '{storage_def_new_name}' exists. You are about to
replace it with '{storage_def_old_name}'. If this is an encrypted backup
where the private key is not backed up, you will lose access to all data
in this backup if you delete this configuration.
            """
                )
                a = prompt_YN(
                    prompt_msg=f"You are about to overwrite a backup storage definition.",
                    prompt_question=(
                        f"Are you certain you want to overwrite '{storage_def_new_name}' "
                    ),
                    default_enter_ans="n",
                )
                if a != "y":
                    print("The storage definition will not be overwritten.")
                    return None
        logging.info(
            f"Restoring {storage_def_old_name} as {storage_def_new_name} from {backup_file_path}"
        )
        g = atbu_stg_cfg.get_general_section()
        if CONFIG_VALUE_NAME_BACKUP_INFO_DIR in g:
            # Retained for legacy purposes, has no effect, but cleaner not to import it.
            del g[CONFIG_VALUE_NAME_BACKUP_INFO_DIR]
        # Merge 'general' and 'storage-definitions' sections from import to dest config.
        deep_union_dicts(
            dest=self.get_storage_defs_section(),
            src=atbu_stg_cfg.get_storage_defs_section(),
        )
        deep_union_dicts(
            dest=self.get_general_section(), src=atbu_stg_cfg.get_general_section()
        )
        logging.info(f"Saving configuration {str(self._path)}...")
        self.save_config_file()
        logging.info(f"Configuration updated... restore complete")
        return storage_def_name

    @staticmethod
    def rename_section_storage_def(
        config_section: dict, old_storage_def_name: str, new_storage_def_name: str
    ):
        """Renames a storage def. The config-section argument can be the
        top node of the storage_defs section, or a single storage_def dict.
        If just a storage_def dict, then only the keyring renaming occurs
        because the storage_def name is not present without having the keys
        the dict within which it lives.
        """
        # If entire storage def section...
        if CONFIG_SECTION_STORAGE_DEFINITIONS in config_section:
            if (
                old_storage_def_name
                not in config_section[CONFIG_SECTION_STORAGE_DEFINITIONS]
            ):
                raise ValueError(
                    f"Expected to find {old_storage_def_name} in the configuration."
                )
            storage_def = config_section[CONFIG_SECTION_STORAGE_DEFINITIONS].pop(
                old_storage_def_name
            )
            config_section[CONFIG_SECTION_STORAGE_DEFINITIONS][
                new_storage_def_name
            ] = storage_def
            config_section = config_section[CONFIG_SECTION_STORAGE_DEFINITIONS][
                new_storage_def_name
            ]
        # Rename service name in any encryption mappings...
        keyring_section: dict = config_section.get(CONFIG_SECTION_KEYRING_MAPPING)
        if not keyring_section:
            return
        for keyring_lookup_info in keyring_section.values():
            if (
                isinstance(keyring_lookup_info, dict)
                and CONFIG_VALUE_NAME_KEYRING_SERVICE in keyring_lookup_info
            ):
                keyring_lookup_info[
                    CONFIG_VALUE_NAME_KEYRING_SERVICE
                ] = new_storage_def_name

    def _resolve_keyring_secrets(
        self,
        storage_def: dict,
        base64_encoded_secrets: bool = False,
    ):
        # Access 'keyring-mapping' section.
        keyring_section: dict = storage_def.get(CONFIG_SECTION_KEYRING_MAPPING)
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
            service_name = keyring_lookup_info[CONFIG_VALUE_NAME_KEYRING_SERVICE]
            username = keyring_lookup_info[CONFIG_VALUE_NAME_KEYRING_USERNAME]

            # Walk from top of config_section down to the second-to-last section which is
            # where the secret goes.
            affected_section = storage_def
            for section_part in affected_config_path_parts[:-1]:
                affected_section = affected_section[section_part]

            # Given service/user names, get the secret.
            (_, password_type, cba_password) = get_password_from_keyring(
                service_name=service_name,
                username=username,
                keep_secret_base64_encoded=base64_encoded_secrets,
            )

            secret_for_caller = cba_password
            if base64_encoded_secrets and isinstance(cba_password, CredentialByteArray):
                secret_for_caller = cba_password.decode("utf-8")
                if not is_valid_base64_string(str_to_check=secret_for_caller):
                    raise InvalidBase64StringError(
                        f"The secret for '{affected_config_path_parts[-1]}' is not base64 encoded."
                    )

            affected_section[affected_config_path_parts[-1]] = secret_for_caller
            affected_section[CONFIG_PASSWORD_TYPE] = password_type

    def get_storage_def_encryption_credential(
        self, storage_def_name, unlock=False
    ) -> Credential:
        storage_def_encryption_key_section = (
            self.get_storage_def_keyring_mapping_encryption_key_section(
                storage_def_name=storage_def_name
            )
        )
        if not storage_def_encryption_key_section:
            raise CredentialNotFoundError(
                f"The credential for '{storage_def_name}' was not found. "
                f"Encryption key section not found."
            )
        service_name = storage_def_encryption_key_section.get(
            CONFIG_VALUE_NAME_KEYRING_SERVICE
        )
        username = storage_def_encryption_key_section.get(
            CONFIG_VALUE_NAME_KEYRING_USERNAME
        )
        if not service_name or not username:
            raise CredentialNotFoundError(
                f"The credential for '{storage_def_name}' was not found. "
                f"Keyring service and/or username not found."
            )
        if username != CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION:
            raise CredentialNotFoundError(
                f"The credential for '{storage_def_name}' was not found. "
                f"The username is not {CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION}."
            )

        credential = get_enc_credential_from_keyring(
            service_name=service_name, username=username, unlock=unlock
        )

        return credential

    def set_config_keyring_mapping(
        self, storage_def_name: str, username: str, section_path: str
    ):
        """Given a storage definition, storage_def_name, set the configuration so that the
        credentials defined by section_path are setup to indicate they are stored in the
        keyring under a specified service and username. The storage_def_name and username become
        the keyring service and username respectively.
        """
        storage_def_dict = self.get_storage_def_dict_deep_copy(
            storage_def_name=storage_def_name
        )
        if storage_def_dict is None:
            storage_def_dict = {}
        # Add the value keyring in the respective section_path. Later, when read, this effectively
        # causes an indirection to the appropriate keyring section of the same config file.
        add_path_value(
            storage_def_dict=storage_def_dict,
            section_value_path=section_path,
            value="keyring",
        )
        # Add the keyring settings indirected by the prior change above.
        add_keyring_mapping(
            cfg=storage_def_dict,
            section_value_path=section_path,
            service=storage_def_name,
            username=username,
        )
        storage_defs_update = {
            CONFIG_SECTION_STORAGE_DEFINITIONS: {storage_def_name: storage_def_dict}
        }
        deep_union_dicts(dest=self.cfg, src=storage_defs_update)
