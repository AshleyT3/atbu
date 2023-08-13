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

import fnmatch
import glob
import logging
import os
from pathlib import Path
import re
from typing import Union
import copy
import json
from uuid import uuid4
import keyring
from send2trash import send2trash

from atbu.mp_pipeline.mp_global import (
    get_verbosity_level,
)
from atbu.common.util_helpers import (
    convert_to_pathlib_path,
    pathlib_splitdrive,
    deep_union_dicts,
    is_absolute_path,
    prompt_YN,
    create_numbered_backup_of_file,
    get_trash_bin_name,
)
from atbu.common.process_file_lock import ProcessFileLock

from atbu.tools.backup.config_migration_helpers import (
    upgrade_storage_definitions_from_001_to_002,
)

from .constants import *
from .exception import *
from .storage_def_credentials import (
    StorageDefCredentialSet,
    restore_keyring_secrets,
)


def parse_storage_def_specifier(storage_location) -> str:
    what_which = storage_location.lower().split(":", maxsplit=1)
    is_storage_definition_specifier = (
        len(what_which) == 2 # ensure two components
        and len(what_which[0]) > 2 # disambiguate "storage:" specifier from drive letter.
        and what_which[0]
        == CONFIG_SECTION_STORAGE_DEFINITION_SPECIFIER_PREFIX[: len(what_which[0])]
    )
    if is_storage_definition_specifier:
        return what_which[1]
    return None


_STORAGE_DEFINITION_CONFIG_OVERRIDES = {
}

_AUTOMATED_TESTING_MODE = False

def set_automated_testing_mode(enabled: bool):
    global _AUTOMATED_TESTING_MODE
    _AUTOMATED_TESTING_MODE = enabled

def get_automated_testing_mode():
    return _AUTOMATED_TESTING_MODE

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
        section_value_path = section_value_path.split("-")
    if not section_value_path or not isinstance(section_value_path, list):
        raise ValueError(
            f"section_path must be in the format section-section-...-value_name"
        )
    value_cfg = storage_def_dict
    for s in section_value_path[:-1]:
        if s not in value_cfg:
            value_cfg[s] = {}
        value_cfg = value_cfg[s]
    value_cfg[section_value_path[-1]] = value


re_not_allowed_cfg_name = re.compile(r"[^a-z0-9_-]")


def is_storage_def_name_ok(storage_def_name):
    if len(storage_def_name) > MAX_STORAGE_DEF_NAME:
        return False
    return not re_not_allowed_cfg_name.search(storage_def_name)


def is_existing_filesystem_storage_path(storage_location: str):
    """An existing valid filesystem storage path has the following characteristics:

    It exists as a directory.

    It is specified as an absolute path. (For no other reason than to ensure the user specifies
        something explicit/clear.)
    """
    return os.path.isdir(storage_location) and is_absolute_path(storage_location)


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
        CONFIG_VALUE_NAME_VERSION: ATBU_CONFIG_FILE_VERSION_STRING_CURRENT,
        CONFIG_SECTION_GENERAL: {},
        CONFIG_SECTION_STORAGE_DEFINITIONS: {},
    }

    always_migrate: bool = False

    def __init__(self, path: Union[str, Path], cfg: dict = None):
        super().__init__(cfg=cfg)
        self._path = convert_to_pathlib_path(path)

    @staticmethod
    def _get_new_unique_id():
        return str(uuid4())

    @staticmethod
    def create_starting_config():
        return copy.deepcopy(AtbuConfig.STARTING_CONFIG)

    @staticmethod
    def create_from_file(path: Union[str, Path], create_if_not_exist: bool = False):
        atbu_cfg = AtbuConfig(path=path)
        atbu_cfg.load_config_file(create_if_not_exist=create_if_not_exist)
        return atbu_cfg

    @staticmethod
    def _check_upgrade_default_config() -> None:
        """Trigger upgrade by loading the default <HOME>/<USER>/... configuration.
        This is not used after the <HOME>/<UESR> configuration is upgraded/removed
        and split into individual configuration files.
        """
        default_config_path = AtbuConfig.get_user_default_config_file_path()
        if not default_config_path.is_file():
            return
        cfg = AtbuConfig(path=AtbuConfig.get_user_default_config_file_path())
        cfg.load_config_file(create_if_not_exist=False)
        # Upgrade successful, default config is now seperate per-storage-def config
        # files. Delete default configuration which is no longer needed.
        cfg.delete_config_file()

    @staticmethod
    def access_cloud_storage_config(
        storage_def_name: str,
        must_exist: bool = False,
        create_if_not_exist: bool = False,
        storage_def_dict_not_exist_ok: bool = False,
    ) -> tuple[object, str, dict]:
        AtbuConfig._check_upgrade_default_config()
        config_path = AtbuConfig.get_user_storage_def_config_file_path(
            storage_def_name=storage_def_name,
        )
        if not create_if_not_exist and not config_path.exists():
            if must_exist:
                raise StorageDefinitionNotFoundError(
                    f"The storage definition '{storage_def_name}' not found. "
                    f"The storage config file does not exist: {config_path}",
                )
            return None, None, None
        already_existed = config_path.exists()
        atbu_cfg = AtbuConfig(path=config_path)
        atbu_cfg.load_config_file(create_if_not_exist=create_if_not_exist)
        storage_def_dict = atbu_cfg.get_storage_def_dict(
            storage_def_name=storage_def_name,
            must_exist=False,
        )
        if not storage_def_dict_not_exist_ok and already_existed and storage_def_dict is None:
            # Not newly created so storage_def_dict for the storage_def_name is expected.
            raise InvalidStateError(
                f"The storage config was found but does not contain the storage def config: "
                f"storage_def_name={storage_def_name} "
                f"config_path={config_path}"
            )
        return atbu_cfg, storage_def_name, storage_def_dict

    @staticmethod
    def access_filesystem_storage_config(
        storage_location_path: Union[str, Path],
        resolve_storage_def_secrets: bool = False,
        create_if_not_exist: bool = True,
        prompt_to_create: bool = True,
    ) -> tuple[object, str, dict]:  # object is AtbuConfig
        storage_location_path = convert_to_pathlib_path(storage_location_path)
        storage_atbu_dir: Path = storage_location_path / ATBU_DEFAULT_CONFIG_DIR_NAME
        storage_atbu_cfg_path: Path = storage_atbu_dir / ATBU_USER_DEFAULT_CONFIG_FILE_NAME
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
        storage_def_name, storage_def_dict = storage_atbu_cfg.find_filesystem_storage_def(
            storage_path_to_find=storage_location_path
        )
        if (
            storage_atbu_cfg.is_filesystem_backup_config()
            and storage_def_name is not None
            and storage_def_dict is not None
        ):
            #
            # Existing (not new) filesystem storage definition.
            #

            override_config_path = AtbuConfig.get_storage_def_config_file_path_override(
                storage_def_name=storage_def_name,
            )

            if override_config_path is not None:
                override_atbu_cfg = AtbuConfig(path=override_config_path)
                override_atbu_cfg.load_config_file(create_if_not_exist=False)
                override_atbu_cfg.set_storage_container(
                    container_name=storage_atbu_cfg.get_storage_container()
                )
                if override_atbu_cfg.storage_def_id != storage_atbu_cfg.storage_def_id:
                    raise InvalidConfiguration(
                        f"The storage definition IDs do not match: "
                        f"discovered={storage_atbu_cfg.storage_def_id} "
                        f"override={override_atbu_cfg.storage_def_id} "
                        f"discovered path={storage_atbu_cfg.path} "
                        f"override path={override_atbu_cfg.path}"
                    )
                storage_atbu_cfg = override_atbu_cfg

            # pylint: disable=protected-access
            storage_atbu_cfg._remap_filesystem_storage_backup_info_dirs()

            if resolve_storage_def_secrets:
                storage_def_dict = (
                    storage_atbu_cfg.get_storage_def_with_resolved_secrets_deep_copy(
                        storage_def_name=storage_def_name
                    )
                )

        return storage_atbu_cfg, storage_def_name, storage_def_dict

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        self._path = Path(value)

    @property
    def version(self) -> str:
        if not self.cfg:
            raise InvalidConfiguration(f"Cannot find the configuration.")
        if not self.cfg.get(CONFIG_VALUE_NAME_VERSION):
            raise InvalidConfiguration(f"Cannot find the configuration's name.")
        return self.cfg.get(CONFIG_VALUE_NAME_VERSION)

    def create_default_config(self):
        if not self._path:
            raise ValueError(
                "The path is not set, cannot create a default configuration."
            )
        logging.info(f"Writing new configuration: {self._path}")
        self._cfg = AtbuConfig.create_starting_config()
        self.save_config_file()

    def create_config_file_numbered_backup(self):
        backup_path = create_numbered_backup_of_file(
            path=self.path,
            not_exist_ok=True,
        )
        if backup_path is None:
            if self.path.is_file():
                raise AtbuException(f"Unable to backup config file: {str(self.path)}")
            logging.warning(
                f"The config file does not exist so was not backed up: {str(self.path)}"
            )
            return
        logging.info(
            f"The config file was backed up: {str(self.path)} -> to -> {str(backup_path)}"
        )

    def delete_config_file(self):
        bin_name = get_trash_bin_name()
        if self._path.is_file():
            logging.info(f"Removing config file, sending to {bin_name}: {self._path}")
            send2trash(paths=str(self._path))

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
        version_str = cfg.get(CONFIG_VALUE_NAME_VERSION)
        if version_str not in [
            ATBU_CONFIG_FILE_VERSION_STRING_0_01,
            ATBU_CONFIG_FILE_VERSION_STRING_0_02,
            ATBU_CONFIG_FILE_VERSION_STRING_CURRENT
        ]:
            logging.error(
                f"The config version '{version_str}' is invalid: {self._path}"
            )
            raise InvalidConfigurationFile(
                f"The config version '{version_str}' is invalid: {self._path}"
            )
        if version_str == ATBU_CONFIG_FILE_VERSION_STRING_0_01:
            self._upgrade_version_001_to_002(cfg=cfg)
        version_str = cfg.get(CONFIG_VALUE_NAME_VERSION)
        if version_str == ATBU_CONFIG_FILE_VERSION_STRING_0_02:
            self._upgrade_version_002_to_003(cfg=cfg)
        else:
            self._cfg = cfg

    def _upgrade_version_001_to_002(self, cfg: dict):
        print(f"Configuration file: {self.path}")
        print(
            f"Current configuration file version: {cfg.get(CONFIG_VALUE_NAME_VERSION)}"
        )
        print(f"Required configuration file version: {ATBU_CONFIG_FILE_VERSION_STRING_CURRENT}")
        if self.always_migrate:
            a = "y"
        else:
            a = prompt_YN(
                prompt_msg=(
                    f"You must upgrade your configuration file from "
                    f"{cfg.get(CONFIG_VALUE_NAME_VERSION)} to "
                    f"{ATBU_CONFIG_FILE_VERSION_STRING_CURRENT} before proceeding."
                ),
                prompt_question=f"Proceed with configuration upgrade?",
                default_enter_ans="n",
            )
            if a != "y":
                raise InvalidConfigurationFile(
                    f"The configuration was not upgraded. "
                    f"You cannot use this version of the software with your current configuration. "
                    f"Please use the proper version of software or upgrade your configuration files. "
                    f"Ensure you have a backup of your configuration using the older software before upgrading."
                )
            # After accepting initial migration, accept all others.
            # Example: The first prompt is usually to upgrade the global config
            # file (i.e., c:\Users\SomeUser\.atbu\atbu-config.json). When performing
            # an operation on a local file system backup, that local file system backup
            # configuration should also be upgraded.
            AtbuConfig.always_migrate = True
        self.create_config_file_numbered_backup()
        # Migrate from 0.01 to 0.02.
        upgrade_storage_definitions_from_001_to_002(cfg=cfg)
        # Success
        cfg[CONFIG_VALUE_NAME_VERSION] = ATBU_CONFIG_FILE_VERSION_STRING_0_02
        # Migration successful, save configuration file.
        self._cfg = cfg
        self.save_config_file()

    def _upgrade_version_002_to_003(self, cfg: dict):
        print(f"Configuration file: {self.path}")
        print(f"Current configuration file version: {cfg.get(CONFIG_VALUE_NAME_VERSION)}")
        print(f"Required configuration file version: {ATBU_CONFIG_FILE_VERSION_STRING_0_03}")
        if self.always_migrate:
            a = "y"
        else:
            a = prompt_YN(
                prompt_msg=(
                    f"You must upgrade your configuration file from "
                    f"{cfg.get(CONFIG_VALUE_NAME_VERSION)} to "
                    f"{ATBU_CONFIG_FILE_VERSION_STRING_0_03} before proceeding."
                ),
                prompt_question=f"Proceed with configuration upgrade?",
                default_enter_ans="n",
            )
            if a != "y":
                raise InvalidConfigurationFile(
                    f"The configuration was not upgraded. "
                    f"You cannot use this version of the software with your current configuration. "
                    f"Please use the proper version of software or upgrade your configuration "
                    f"files. Ensure you have a backup of your configuration using the older "
                    f"software before upgrading."
                )
            # After accepting initial migration, accept all others.
            AtbuConfig.always_migrate = True
        self.create_config_file_numbered_backup()
        # Migrate from 0.02 to 0.03.

        #
        # From the configuration, extract individual storage definitions into their own
        # configuration files.
        #
        cfg_dir = self._path.parent
        storage_def_name: str
        storage_def_dict: dict
        storage_definitions = cfg[CONFIG_SECTION_STORAGE_DEFINITIONS]
        is_filesystem = False
        for storage_def_name, storage_def_dict in storage_definitions.items():
            print(f"Processing storage definition: {storage_def_name}...")
            interface_type = storage_def_dict.get(CONFIG_VALUE_NAME_INTERFACE_TYPE)
            is_filesystem = False
            if interface_type == CONFIG_INTERFACE_TYPE_FILESYSTEM:
                is_filesystem = True
            if is_filesystem:
                # Overwrite same file.
                new_cfg_path = self._path
                if len(storage_definitions) != 1:
                    raise InvalidConfiguration(
                        f"Expecting file system config to only have a single storage definition: "
                        f"len(storage_definitions)={len(storage_definitions)}"
                    )
            else:
                # Make new separate file.
                new_cfg_path = (
                    cfg_dir / AtbuConfig.get_user_storage_def_config_file_name(
                        storage_def_name=storage_def_name
                    )
                )
            if new_cfg_path.is_file():
                new_cfg_path_backup = create_numbered_backup_of_file(
                    path=new_cfg_path,
                    not_exist_ok=False,
                )
                print(f"Backed up: {str(new_cfg_path)} --> {str(new_cfg_path_backup)}")
            if new_cfg_path.is_dir():
                raise InvalidStateError(
                    f"The new config path should not be a directory: {str(new_cfg_path)}"
                )
            new_cfg_dict = copy.deepcopy(cfg)
            new_cfg_dict[CONFIG_VALUE_NAME_VERSION] = ATBU_CONFIG_FILE_VERSION_STRING_CURRENT
            new_cfg_gen_sec = new_cfg_dict[CONFIG_SECTION_GENERAL]
            if CONFIG_VALUE_NAME_BACKUP_INFO_DIR in new_cfg_gen_sec:
                # For prior version, CONFIG_VALUE_NAME_BACKUP_INFO_DIR was a str.
                # Going forward, CONFIG_VALUE_NAME_BACKUP_INFO_DIR is an array/list.
                new_cfg_gen_sec[CONFIG_VALUE_NAME_BACKUP_INFO_DIR] = [
                    new_cfg_gen_sec[CONFIG_VALUE_NAME_BACKUP_INFO_DIR]
                ]
            else:
                new_cfg_gen_sec[CONFIG_VALUE_NAME_BACKUP_INFO_DIR] = []
            new_storage_def_dict = copy.deepcopy(storage_def_dict)
            if not new_storage_def_dict.get(CONFIG_VALUE_NAME_STORAGE_DEF_UNIQUE_ID):
                new_storage_def_dict[
                    CONFIG_VALUE_NAME_STORAGE_DEF_UNIQUE_ID
                ] = AtbuConfig._get_new_unique_id()
            new_cfg_dict[CONFIG_SECTION_STORAGE_DEFINITIONS] = {
                storage_def_name: new_storage_def_dict,
            }
            new_cfg = AtbuConfig(
                path=new_cfg_path,
                cfg=new_cfg_dict,
            )
            print(f"Saving {storage_def_name}: {new_cfg.path}")
            new_cfg.save_config_file()
            if is_filesystem:
                break
        if is_filesystem:
            # File system's update without changing the file name so self is
            # the updated file system configuration. Simply reload self.
            self.load_config_file()
        else:
            cfg[CONFIG_SECTION_STORAGE_DEFINITIONS] = {}
            cfg[CONFIG_VALUE_NAME_VERSION] = ATBU_CONFIG_FILE_VERSION_STRING_0_03
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

    def validate_name_version(self):
        name = self.get_name()
        version = self.version
        if name != ATBU_CONFIG_NAME:
            raise InvalidConfiguration(
                f"Invalid config name: Expected='{ATBU_CONFIG_NAME}' but got '{name}'"
            )
        if version != ATBU_CONFIG_FILE_VERSION_STRING_CURRENT:
            raise InvalidConfiguration(
                f"Invalid config version: "
                f"Expected='{ATBU_CONFIG_FILE_VERSION_STRING_CURRENT}' but got '{name}'"
            )

    def get_storage_defs_section(self) -> dict:
        return self._get_top_section(CONFIG_SECTION_STORAGE_DEFINITIONS)

    @staticmethod
    def get_user_default_config_dir() -> Path:
        return Path.home() / ATBU_DEFAULT_CONFIG_DIR_NAME

    @staticmethod
    def get_user_default_config_file_path() -> Path:
        return AtbuConfig.get_user_default_config_dir() / ATBU_USER_DEFAULT_CONFIG_FILE_NAME

    @staticmethod
    def get_user_storage_def_config_file_name(storage_def_name: str) -> str:
        return f"{ATBU_STGDEF_CONFIG_FILE_NAME_PREFIX}{storage_def_name}.json"

    @staticmethod
    def get_storage_def_config_file_path_override(
        storage_def_name: str,
    ) -> Path:
        if storage_def_name in _STORAGE_DEFINITION_CONFIG_OVERRIDES:
            return Path(_STORAGE_DEFINITION_CONFIG_OVERRIDES[storage_def_name])
        return None

    @staticmethod
    def get_user_storage_def_config_file_path(
        storage_def_name: str,
        with_overrides: bool = True,
    ) -> Path:
        if with_overrides and storage_def_name in _STORAGE_DEFINITION_CONFIG_OVERRIDES:
            return Path(_STORAGE_DEFINITION_CONFIG_OVERRIDES[storage_def_name])
        return (
            AtbuConfig.get_user_default_config_dir() /
            AtbuConfig.get_user_storage_def_config_file_name(storage_def_name=storage_def_name)
        )

    @staticmethod
    def get_default_backup_info_dir() -> Path:
        """Get the original ATBU default configuration backup information directory.
        This directory was subordinate to the older default configuration file folder.
        It continues to be the default primary backup information directory but can be
        overridden and not used.

        Raises:
            InvalidConfiguration: If the default location cannot be a directory.

        Returns:
            Path: The default backup information directory.
        """
        bid = AtbuConfig.get_user_default_config_dir() / ATBU_DEFAULT_BACKUP_INFO_SUBDIR
        if bid.is_file():
            raise InvalidConfiguration(
                f"Expecting a directory but observed the default backup info directory is a file: ",
                f"{str(bid)}",
            )
        bid.mkdir(parents=True, exist_ok=True)
        return bid

    def get_config_backup_info_dir(self) -> Path:
        """Get the configuration file's backup information directory. The configuration
        backup information directory is the ./backup-info-dir subordinate to the storage
        definition configuration file. This directory may or may not be in the default
        HOME ATBU configuration directory.

        Returns:
            Path: The config backup information directory.
        """
        return self._path.parent / ATBU_DEFAULT_BACKUP_INFO_SUBDIR

    re_extract_storage_def_name = re.compile(
        rf".*\{os.sep}{ATBU_STGDEF_CONFIG_FILE_NAME_PREFIX}([^\s\.]+).json"
    )

    @dataclass
    class StorageDefConfigPathInfo:
        storage_def_name: str
        config_file_path: str

    @staticmethod
    def get_user_storage_def_config_path_info(
        glob_pattern="*"
    ) -> list[StorageDefConfigPathInfo]:
        AtbuConfig._check_upgrade_default_config()
        glob_pattern = (
            AtbuConfig.get_user_default_config_dir() /
            f"{ATBU_STGDEF_CONFIG_FILE_NAME_PREFIX}{str(glob_pattern)}.json"
        )
        remaining_overrides = copy.deepcopy(_STORAGE_DEFINITION_CONFIG_OVERRIDES)
        cpi_list: list[AtbuConfig.StorageDefConfigPathInfo] = []
        for config_file_path in glob.glob(pathname=str(glob_pattern)):
            m = AtbuConfig.re_extract_storage_def_name.match(config_file_path)
            if m is None:
                raise InvalidStateError(
                    f"Cannot extract storage def name from config path: {config_file_path}"
                )
            storage_def_name = m.groups()[0].lower()
            cpi = AtbuConfig.StorageDefConfigPathInfo(
                storage_def_name=storage_def_name,
                config_file_path=config_file_path,
            )
            if cpi.storage_def_name in remaining_overrides:
                cpi.config_file_path = remaining_overrides[cpi.storage_def_name]
                del remaining_overrides[cpi.storage_def_name]
            cpi_list.append(cpi)
        for ovr_def_name, ovr_cfg_path in remaining_overrides.items():
            cpi = AtbuConfig.StorageDefConfigPathInfo(
                storage_def_name=ovr_def_name,
                config_file_path=ovr_cfg_path,
            )
            cpi_list.insert(0, cpi)
        return cpi_list

    @staticmethod
    def get_user_storage_def_names(fnmatch_pattern="*") -> list[str]:
        AtbuConfig._check_upgrade_default_config()
        return [
            cpi.storage_def_name
            for cpi in AtbuConfig.get_user_storage_def_config_path_info()
            if fnmatch.fnmatch(cpi.storage_def_name, fnmatch_pattern)
        ]

    @staticmethod
    def is_user_storage_def_exists(storage_def_name: str) -> bool:
        return len(AtbuConfig.get_user_storage_def_names(fnmatch_pattern=storage_def_name)) != 0

    def get_filesystem_storage_def_root_dir(self) -> Path:
        """Get the file system storage definition's root directory. This method
        assumes the storage definition's container is accurate/resolved.

        Raises:
            InvalidConfiguration: Raised if not a file system storage definition.

        Returns:
            Path: The Path object to the root of the file system storage definition.
        """
        if not self.is_filesystem_backup_config():
            raise InvalidConfiguration(
                f"Configuration is not a filesystem storage definition. "
                f"Cannot get filesystem storage definition root directory: "
                f"path={self.path}"
            )
        return Path(self.get_storage_container())

    def get_filesystem_storage_def_config_dir(self) -> Path:
        return self.get_filesystem_storage_def_root_dir() / ATBU_DEFAULT_CONFIG_DIR_NAME

    def get_filesystem_storage_def_backup_info_dir(self) -> Path:
        return self.get_filesystem_storage_def_config_dir() / ATBU_DEFAULT_BACKUP_INFO_SUBDIR

    @staticmethod
    def _has_replacement_root(path: Path):
        path_str = str(path)
        for rep_field in REPLACEMENT_FIELDS:
            if path_str.startswith(rep_field):
                return True
        return False

    def _remap_filesystem_storage_backup_info_dirs(self):
        """For all backup information directories defined by this configuration,
        remap any such directories to the current file system storage drive.
        """
        if not self.is_filesystem_backup_config():
            return
        fs_sd_root = self.get_filesystem_storage_def_root_dir()
        fs_sd_drive, fs_sd_root_wo_drive = pathlib_splitdrive(fs_sd_root)
        bid_list = self.get_config_backup_info_dirs()
        if not bid_list:
            return
        remapped_bid_list: list[Path] = []
        for bid in bid_list:
            bid_drive, bid_path_wo_drive = pathlib_splitdrive(bid)
            if fs_sd_root_wo_drive not in bid_path_wo_drive.parents:
                remapped_bid_list.append(bid)
            if fs_sd_drive != bid_drive and not AtbuConfig._has_replacement_root(bid_path_wo_drive):
                bid = fs_sd_drive / bid_path_wo_drive
            remapped_bid_list.append(bid)
        self.set_config_backup_info_dirs(remapped_bid_list)

    def find_filesystem_storage_def(
        self, storage_path_to_find: Path
    ) -> tuple[str, dict]:
        if not self.is_filesystem_backup_config():
            return None, None
        storage_def_name, storage_def_dict = self.get_only_storage_def_dict()
        if storage_def_dict is None:
            return None, None
        actual_drive, storage_path_to_find_wo_drive = os.path.splitdrive(storage_path_to_find)
        config_drive, storage_def_path_wo_drive = os.path.splitdrive(
            storage_def_dict[CONFIG_VALUE_NAME_CONTAINER]
        )
        if storage_path_to_find_wo_drive != storage_def_path_wo_drive:
            return None, None
        if actual_drive != config_drive:
            storage_def_dict[CONFIG_VALUE_NAME_CONTAINER] = str(storage_path_to_find)
        return storage_def_name, storage_def_dict

    @staticmethod
    def _get_config_of_type(
        section: dict,
        key_name: str,
        expected_type: type,
        default_value = None,
    ):
        if section is None:
            return default_value
        value = section.get(key_name)
        if value is None:
            return default_value
        if not isinstance(value, expected_type):
            raise InvalidConfiguration(
                f"{key_name} must be a {expected_type} but is "
                f"type={type(value)} value={value}"
            )
        return value

    @staticmethod
    def _get_config_string(
        section: dict,
        key_name: str,
        default_value: str = None,
    ) -> str:
        return AtbuConfig._get_config_of_type(
            section=section,
            key_name=key_name,
            expected_type=str,
            default_value=default_value,
        )

    @staticmethod
    def _get_config_list(
        section: dict,
        key_name: str,
        default_value: list = None,
    ) -> list:
        return AtbuConfig._get_config_of_type(
            section=section,
            key_name=key_name,
            expected_type=list,
            default_value=default_value,
        )

    @staticmethod
    def _get_config_bool(
        section: dict,
        key_name: str,
        default_value: bool = None,
    ) -> bool:
        return AtbuConfig._get_config_of_type(
            section=section,
            key_name=key_name,
            expected_type=bool,
            default_value=default_value,
        )

    @property
    def storage_def_name(self) -> str:
        return self.get_only_storage_def_dict()[0]

    @property
    def storage_def_id(self) -> str:
        _, storage_def_dict = self.get_only_storage_def_dict()
        return storage_def_dict.get(CONFIG_VALUE_NAME_STORAGE_DEF_UNIQUE_ID)

    def get_storage_container(self) -> str:
        _, storage_def_dict = self.get_only_storage_def_dict(not_exist_ok=False)
        return storage_def_dict.get(CONFIG_VALUE_NAME_CONTAINER)

    def set_storage_container(self, container_name):
        _, storage_def_dict = self.get_only_storage_def_dict(not_exist_ok=False)
        storage_def_dict[CONFIG_VALUE_NAME_CONTAINER] = container_name

    def get_interface_type(self) -> str:
        storage_def_name, storage_def_dict = self.get_only_storage_def_dict()
        if storage_def_name is None or storage_def_dict is None:
            return None
        interface_type = storage_def_dict.get(CONFIG_VALUE_NAME_INTERFACE_TYPE)
        if not interface_type:
            raise InvalidConfiguration(
                f"Cannot find '{CONFIG_VALUE_NAME_INTERFACE_TYPE}' in the storage "
                f"definition dictionary."
            )
        return interface_type

    def is_filesystem_backup_config(self):
        return self.get_interface_type() == CONFIG_INTERFACE_TYPE_FILESYSTEM

    def get_config_backup_info_dirs(self) -> list[Path]:
        gen_sec = self.get_general_section()
        if gen_sec is None:
            return []
        if not isinstance(gen_sec, dict):
            raise InvalidConfiguration(
                f"The {CONFIG_SECTION_GENERAL} section should be a dictionary."
            )
        bid_list = AtbuConfig._get_config_list(gen_sec, CONFIG_VALUE_NAME_BACKUP_INFO_DIR)
        if bid_list is None:
            return []
        if not isinstance(bid_list, list):
            raise InvalidConfiguration(
                f"Expected {CONFIG_VALUE_NAME_BACKUP_INFO_DIR} to be a list and not a "
                f"{type(bid_list)}."
            )
        return [Path(bidstr) for bidstr in bid_list]

    def set_config_backup_info_dirs(self, bid_list: list[Union[str,Path]]):
        gen_sec = self.get_general_section()
        if not isinstance(gen_sec, dict):
            raise InvalidConfiguration(
                f"The {CONFIG_SECTION_GENERAL} section should be a dictionary."
            )
        gen_sec[CONFIG_VALUE_NAME_BACKUP_INFO_DIR] = [str(bid) for bid in bid_list]

    def get_resolved_config_backup_info_dirs(self) -> list[Path]:
        cfg_bids_resolved: list[Path] = []
        cfg_bids = self.get_config_backup_info_dirs()
        for cfg_bid in cfg_bids:
            cfg_bid_str = str(cfg_bid)
            cfg_bid_str = cfg_bid_str.replace(
                REPLACEMENT_FIELD_DEFAULT_CONFIG_DIR,
                str(AtbuConfig.get_user_default_config_dir()),
            )
            cfg_bid_str = cfg_bid_str.replace(
                REPLACEMENT_FIELD_CONFIG_DIR,
                str(self._path.parent),
            )
            cfg_bid = Path(cfg_bid_str).resolve()
            cfg_bids_resolved.append(cfg_bid)
        return cfg_bids_resolved

    def get_backup_info_dirs(self) -> list[Path]:
        """Get the backup information directories for this configuration.
        This will return a list of Path objects, each of which is a backup
        information directory.

        The first Path in the returned list is the "primary" backup information
        directory, and is the one expected to contain the latest backup information,
        where the other Path objects (other than the first one) are considered
        secondary and therefore backup copies of the primary backup information.


        Raises:
            BackupInformationDirectoryNotFound: Raised if a backup information
                directory Path cannot be a directory (i.e., storage medium is
                offline or the Path is to a file), or if no backup information
                directories could be deduced by the user's configuration. There
                must always be at least one (primary) backup information directory.

        Returns:
            list[Path]: The list of backup information directories, the first of
                which is considered the "primary" backup information directory.
        """
        default_bid = AtbuConfig.get_default_backup_info_dir().resolve()
        cfg_bids_resolved = self.get_resolved_config_backup_info_dirs()
        cfg_no_default_bid = AtbuConfig._get_config_bool(
            self.get_general_section(),
            CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS,
            False,
        )
        if not cfg_no_default_bid:
            # Original and still the current default behavior, if not overridden using the
            # CONFIG_VALUE_NAME_NO_DEFAULT_BACKUP_INFO_DIR setting, is for the user's HOME
            # .atbu/backup-info-dir to be the primary backup info dir.
            cfg_bids_resolved.insert(0, default_bid)
            # ...and for filesystem storage definitions, the secondary backup information
            # directory is in the target storage configuration directory (aka the "config"
            # backup information directory).
            if self.is_filesystem_backup_config():
                cfg_bids_resolved.insert(1, self.get_filesystem_storage_def_backup_info_dir())
        cfg_bid_resolved_str_set: set[str] = set()
        cfg_bids_final: list[Path] = []
        for cfg_bid in cfg_bids_resolved:
            if not str(cfg_bid) in cfg_bid_resolved_str_set:
                cfg_bids_final.append(cfg_bid)
                cfg_bid_resolved_str_set.add(str(cfg_bid))
        for cfg_bid in cfg_bids_final:
            if not cfg_bid.exists():
                cfg_bid.mkdir(parents=True, exist_ok=True)
            if not cfg_bid.is_dir():
                raise BackupInformationDirectoryNotFound(
                    f"The backup information directory was not found: {str(cfg_bid)}"
                )
        if not cfg_bids_final:
            raise BackupInformationDirectoryNotFound(
                f"No backup information directories were found. "
                f"There must be at least one backup information directory. "
                f"Your configuration is invalid. "
                f"Please review your configuration's backup information directory settings."
            )
        return cfg_bids_final

    def get_primary_backup_info_dir(self) -> Path:
        return self.get_backup_info_dirs()[0]

    def get_primary_backup_info_file_paths(
        self,
        storage_def_name: str,
    ) -> list[str]:
        pattern = self.get_primary_backup_info_dir() / f"{storage_def_name}*"
        return glob.glob(pathname=str(pattern))

    @staticmethod
    def resolve_storage_location(
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

        storage_atbu_cfg: AtbuConfig = None

        if storage_def_name:
            # Specifier found, if config exists, return it directly or with secrets resolved.
            storage_atbu_cfg, _, storage_def_dict = AtbuConfig.access_cloud_storage_config(
                storage_def_name=storage_def_name,
                must_exist=False,
                create_if_not_exist=False,
            )

            if (
                storage_atbu_cfg is not None
                and storage_def_dict is not None
                and resolve_storage_def_secrets
            ):
                storage_def_dict = storage_atbu_cfg.get_storage_def_with_resolved_secrets_deep_copy(
                    storage_def_name=storage_def_name,
                )

            return storage_atbu_cfg, storage_def_name, storage_def_dict

        # Fall through if storage_def specifier not found.
        # See if storage_location is a filesystem storage.

        if is_existing_filesystem_storage_path(storage_location=storage_location):
            try:
                # storage_location is a directory specified as absolute path.
                (
                    storage_atbu_cfg,
                    storage_def_name,
                    storage_def,
                ) = AtbuConfig.access_filesystem_storage_config(
                    storage_location_path=storage_location,
                    resolve_storage_def_secrets=resolve_storage_def_secrets,
                    create_if_not_exist=create_if_not_exist,
                    prompt_to_create=True,
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
        storage_def_dict = self.get_storage_def_dict_deep_copy(
            storage_def_name=storage_def_name,
        )
        if not isinstance(storage_def_dict, dict):
            raise StorageDefinitionNotFoundError(
                f"Cannot find storage definition "
                f"{storage_def_name} in config file {str(self.path)}"
            )

        cred_set = StorageDefCredentialSet(
            storage_def_name=storage_def_name,
            storage_def_dict=storage_def_dict,
        )
        cred_set.populate()
        cred_set.unprotect(
            base64_encoded_secrets=keep_secrets_base64_encoded,
        )
        return cred_set.storage_def_dict

    def get_storage_def_dict(self, storage_def_name, must_exist: bool = False) -> dict:
        storage_def_dict = self.get_storage_defs_section().get(storage_def_name)
        if must_exist and storage_def_dict is None:
            raise StorageDefinitionNotFoundError(
                f"The storage definition '{storage_def_name}' not found."
            )
        return storage_def_dict

    def get_only_storage_def_dict(self, not_exist_ok: bool = True) -> tuple[str, dict]:
        storage_def_section: dict = self.get_storage_defs_section()
        if len(storage_def_section) != 1:
            if not_exist_ok:
                return None, None
            raise InvalidConfiguration(
                f"One storage definition was not found: "
                f"len(storage_def_section)={len(storage_def_section)}"
            )
        storage_def_name, storage_def_dict = list(storage_def_section.items())[0]
        return storage_def_name, storage_def_dict

    def verify_only_one_storage_def(self) -> None:
        storage_def_section: dict = self.get_storage_defs_section()
        if len(storage_def_section) != 1:
            raise InvalidStorageDefinitionFile(
                f"Expected one storage definition configuration but observed :"
                f"{len(storage_def_section)}."
            )

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
        storage_def_section = self.get_storage_defs_section()
        if old_name not in storage_def_section:
            raise ValueError(
                f"Expected to find {old_name} in the configuration."
            )
        storage_def = storage_def_section.pop(
            old_name
        )
        storage_def_section[new_name] = storage_def

    def get_storage_def_encryption_section(self, storage_def_name) -> dict:
        storage_def = self.get_storage_def_dict(storage_def_name=storage_def_name)
        if not storage_def:
            return None
        return storage_def.get(CONFIG_SECTION_ENCRYPTION)

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

    @staticmethod
    def create_cloud_storage_def_config(
        storage_def_name: str,
    ) -> object:
        if AtbuConfig.is_user_storage_def_exists(storage_def_name=storage_def_name):
            raise StorageDefinitionAlreadyExists(
                f"The backup storage definition '{storage_def_name}' already exists."
            )
        config_path = AtbuConfig.get_user_storage_def_config_file_path(
            storage_def_name=storage_def_name,
        )
        atbu_cfg = AtbuConfig(
            path=config_path,
        )

        atbu_cfg.cfg = AtbuConfig.create_starting_config()

        return atbu_cfg

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
        if unique_storage_def_name is None:
            raise InvalidStorageDefinitionName(
                f"unique_storage_def_name not specified, cannot be None."
            )
        unique_storage_def_name = unique_storage_def_name.lower()
        if not is_storage_def_name_ok(storage_def_name=unique_storage_def_name):
            raise InvalidStorageDefinitionName(
                f"unique_storage_def_name '{unique_storage_def_name}' is invalid."
            )
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
        storage_def_dict[
            CONFIG_VALUE_NAME_STORAGE_DEF_UNIQUE_ID
        ] = AtbuConfig._get_new_unique_id()
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
        print(f"Loading backup file {backup_file_path}...")
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
        logging.info(f"Restoring secrets from backup file to keyring.")
        restore_keyring_secrets(
            storage_def_name=storage_def_name,
            storage_def=storage_def_dict,
        )
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
    def access_process_lock_by_storage_def_name(storage_def_name: str) -> ProcessFileLock:
        lock_filename = f".{storage_def_name}-{ATBU_ACRONYM}-lock"
        lock_full_path = AtbuConfig.get_user_default_config_dir() / lock_filename
        return ProcessFileLock(filename=lock_full_path, diag_name=storage_def_name)

    def access_process_lock(self) -> ProcessFileLock:
        return AtbuConfig.access_process_lock_by_storage_def_name(
            storage_def_name=self.storage_def_name,
        )


def get_atbu_config_from_file(
    config_file_path: str,
) -> tuple[AtbuConfig, str, dict]:
    atbu_cfg = AtbuConfig.create_from_file(
        path=config_file_path,
        create_if_not_exist=False,
    )
    atbu_cfg.verify_only_one_storage_def()
    storage_def_name, storage_def_dict = atbu_cfg.get_only_storage_def_dict()
    return atbu_cfg, storage_def_name, storage_def_dict


def register_storage_def_config_override(
    storage_def_config_path: str,
    only_if_not_already_present: bool,
):
    if not os.path.isfile(storage_def_config_path):
        raise InvalidStorageDefinitionFile(
            f"register_storage_def_config_override: "
            f"Cannot find the config file: {storage_def_config_path}"
        )

    storage_def_name: str = None
    try:
        _, storage_def_name, _ = get_atbu_config_from_file(
            config_file_path=storage_def_config_path,
        )
        if not storage_def_name:
            raise InvalidStorageDefinitionName(
                f"Storage definition name is invalid after reading from config: "
                f"{storage_def_config_path}"
            )
    except ConfigFileNotFoundError as ex:
        logging.error(
            f"The configuration file was not found: {storage_def_config_path}"
        )
        raise

    if (
        only_if_not_already_present
        and AtbuConfig.get_user_storage_def_config_file_path(
            storage_def_name=storage_def_name,
        ).is_file()
    ):
        return
    _STORAGE_DEFINITION_CONFIG_OVERRIDES[storage_def_name] = storage_def_config_path


def unregister_storage_def_config_override(
    storage_def_name: str,
):
    if storage_def_name in _STORAGE_DEFINITION_CONFIG_OVERRIDES:
        del _STORAGE_DEFINITION_CONFIG_OVERRIDES[storage_def_name]
