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
r"""Backup-related command line handlers.
"""
import os
from pathlib import Path
import logging
from typing import Union

from ..common.constants import *
from ..common.exception import *
from ..common.util_helpers import *
from .config import AtbuConfig, is_storage_def_name_ok, parse_storage_def_specifier
from .creds_cmdline import setup_backup_encryption_wizard
from .backup_selections import get_local_file_information
from .backup_core import Backup, StorageDefinition


def get_local_filesystem_backup_info(
    storage_location_path: Union[str, Path],
    resolve_storage_def_secrets: bool = False,
    create_if_not_exist: bool = False,
    prompt_to_create: bool = False,
):
    storage_location_path = convert_to_pathlib_path(storage_location_path)
    if storage_location_path is None or storage_location_path.is_file():
        raise ValueError(
            "The backup storage location must be an absolute path and not an existing file."
        )
    if not is_absolute_path(path_to_dir=storage_location_path):
        raise ValueError("The backup storage location must be an absolute path.")

    storage_atbu_cfg: AtbuConfig
    (
        storage_atbu_cfg,
        storage_def_name,
        storage_def,
    ) = AtbuConfig.access_filesystem_config(
        storage_location_path=storage_location_path,
        resolve_storage_def_secrets=resolve_storage_def_secrets,
        create_if_not_exist=create_if_not_exist,
        prompt_to_create=prompt_to_create,
    )
    return storage_atbu_cfg, storage_def_name, storage_def


def get_local_filesystem_backup_with_wizard(
    storage_location_path: Union[str, Path],
    default_storage_def_name: str = None,
    debug_mode: bool = False,
) -> tuple[AtbuConfig, str, dict]:
    storage_location_path = convert_to_pathlib_path(storage_location_path)
    if storage_location_path is None or storage_location_path.is_file():
        raise ValueError(
            "The backup storage location must be an absolute path and not an existing file."
        )
    if not is_absolute_path(path_to_dir=storage_location_path):
        raise ValueError("The backup storage location must be an absolute path.")

    storage_atbu_cfg, storage_def_name, storage_def = get_local_filesystem_backup_info(
        storage_location_path=storage_location_path,
        create_if_not_exist=True,
        prompt_to_create=False,
    )
    print(f"Storage location: {str(storage_location_path)}")
    print(f"Storage definition: {str(storage_atbu_cfg.path)}")
    if storage_def is not None:
        return storage_atbu_cfg, storage_def_name, storage_def

    if not default_storage_def_name:
        default_storage_def_name = os.path.split(storage_location_path)[1]
    default_storage_def_name = default_storage_def_name.lower()
    print(
        f"Backup destinations require a storage definition which retains information about the"
    )
    print(
        f"storage location, including how to access it and whether it's cloud or filesystem-based."
    )
    print(
        f"Enter a user-friendly name for this backup destination's storage definition."
    )
    print(f"Any name you enter will be converted to all lower case.")
    print(
        f"If you press ENTER without entering anything, '{default_storage_def_name}' will be used."
    )
    while True:
        storage_def_name = input("Enter a name (letters, numbers, spaces): ")
        if len(storage_def_name) == 0:
            print(f"Using '{default_storage_def_name}'.")
            storage_def_name = default_storage_def_name
        if storage_atbu_cfg.is_storage_def_exists(storage_def_name=storage_def_name):
            print(f"That name already exists, try another name.")
            continue
        storage_def_name = storage_def_name.lower()
        if not is_storage_def_name_ok(storage_def_name=storage_def_name):
            print(f"Invalid character(s).")
            continue
        print(f"Using the name '{storage_def_name}'...")
        break
    print(f"Creating backup storage definition...")
    storage_def_name, storage_def = storage_atbu_cfg.create_filesystem_storage_def(
        storage_location_path=storage_location_path,
        unique_storage_def_name=storage_def_name,
    )
    print(f"Created storage definition {storage_def_name} for {storage_location_path}")
    setup_backup_encryption_wizard(
        storage_atbu_cfg=storage_atbu_cfg,
        storage_def_name=storage_def_name,
        debug_mode=debug_mode,
    )
    return storage_atbu_cfg, storage_def_name, storage_def


def establish_storage_path_location():
    while True:
        print(
            f"Enter an absolute path to directory to act as the storage location for the backup."
        )
        print(f"The directory should either be non-existent or empty.")
        storage_location_path = input(f"Enter storage location path:")
        if (
            os.path.exists(storage_location_path)
            and len(os.listdir(storage_location_path)) != 0
        ):
            print(
                f"The specified storage location path exists and is not empty, try again."
            )
            continue
        return storage_location_path


def handle_new_local_filesystem_storage_def(
    default_storage_def_name: str, storage_location: str, debug_mode: bool = False
) -> tuple[AtbuConfig, str, dict]:

    if not storage_location:
        storage_location = establish_storage_path_location()
    #
    # Local filesystem storage:
    #
    (
        atbu_cfg_to_use,
        storage_def_name,
        storage_def,
    ) = get_local_filesystem_backup_with_wizard(
        storage_location_path=storage_location,
        default_storage_def_name=default_storage_def_name,
        debug_mode=debug_mode,
    )

    general_section = atbu_cfg_to_use.get_general_section()
    storage_backup_info_dir = general_section.get(CONFIG_VALUE_NAME_BACKUP_INFO_DIR)
    if storage_backup_info_dir is not None:
        storage_backup_info_dir = Path(storage_backup_info_dir)
        if storage_backup_info_dir.is_file():
            raise ExpectedDirectoryIsFileError(
                f"Expected a directory but observed a file: {storage_backup_info_dir}"
            )
        storage_backup_info_dir.mkdir(parents=True, exist_ok=True)

    return atbu_cfg_to_use, storage_def_name, storage_def


def handle_backup(args):
    backup_type = None
    sneaky_corruption_detection: bool = args.detect_bitrot
    if args.full:
        backup_type = ATBU_BACKUP_TYPE_FULL
    elif args.incremental:
        backup_type = ATBU_BACKUP_TYPE_INCREMENTAL
    elif args.ip:
        backup_type = ATBU_BACKUP_TYPE_INCREMENTAL_PLUS
    else:
        raise ValueError(f"Could not derive backup type.")

    deduplication_option = None
    if args.dedup is not None:
        if backup_type != ATBU_BACKUP_TYPE_INCREMENTAL_PLUS:
            raise InvalidCommandLineArgument(
                f"The --dedup option is only valid with --incremental-plus"
            )
        deduplication_option = args.dedup[0]

    source_locations: list[str] = args.source_dirs
    dest_location: str = args.dest_storage_specifier
    exclude_patterns: list[str] = args.exclude

    logging.debug(f"Backup type: {backup_type}")
    logging.debug(f"Source locations: {source_locations}")
    logging.debug(f"Dest location: {dest_location}")
    logging.debug(f"Exclude patterns: {exclude_patterns}")
    logging.debug(f"sneaky_corruption_detection: {sneaky_corruption_detection}")

    #
    # Default config is user's configuration file located on the device.
    # It may contain storage definitions. In addition to this device config,
    # local filesystem storage definitions can contain their own storage
    # location configuration. To clarity, this is the device's config. See
    # further below for the need to access a storage location's config.
    #
    default_cfg = AtbuConfig.access_default_config()

    #
    # The config to use is the one relating to the backup destination.
    # If it's a filesystem local disk then atbu_cfg_to_use is usually
    # the ATBU config file found in that disk's .atbu folder, otherwise
    # it's a config in the default_cfg which is default_cfg == atbu_cfg_to_use
    # at the start but can change below.
    #
    atbu_cfg_to_use: AtbuConfig = default_cfg

    # Get/create user's backup information directory if not already created.
    user_backup_info_dir: Path = default_cfg.get_backup_info_dir()

    # First in this list should be user's machine backup info dir.
    # Another can be added below for the destination where applicable.
    backup_info_dirs: list[str] = [str(user_backup_info_dir)]

    storage_def_name = parse_storage_def_specifier(storage_location=dest_location)
    if storage_def_name:
        #
        # A "storage:<storage_def_name>" was specified.
        # The storage_def_name may or may not exist,
        # and if it exists, may be either cloud/local.
        #
        storage_def_dict = default_cfg.get_storage_def_dict(
            storage_def_name=storage_def_name
        )
        if not storage_def_dict:
            # Does not exist yet.
            raise StorageDefinitionNotFoundError(
                f"The storage definition '{storage_def_name}' was not found. "
                f"You can create a storage definition using '{ATBU_PROGRAM_NAME} creds create-storage-def ...' or"
                f"by manually editing the {default_cfg.path} config file."
            )
    else:
        #
        # Local filesystem storage:
        #
        atbu_cfg_to_use, storage_def_name, _ = handle_new_local_filesystem_storage_def(
            default_storage_def_name=None, storage_location=dest_location
        )

        backup_info_dirs.append(str(atbu_cfg_to_use.get_backup_info_dir()))

    storage_def_dict = atbu_cfg_to_use.get_storage_def_with_resolved_secrets_deep_copy(
        storage_def_name=storage_def_name
    )

    storage_def = StorageDefinition.storage_def_from_dict(
        storage_def_name=storage_def_name, storage_def_dict=storage_def_dict
    )

    logging.info(f"Backup location(s)...")
    for idx, source_location in enumerate(source_locations):
        idx_str = f"  Source location #{idx} "
        logging.info(f"{idx_str:.<35} {source_location}")

    logging.info(f"Searching for files...")
    file_info_list = get_local_file_information(
        src_dirs_wc=source_locations, exclude_patterns=exclude_patterns
    )
    if len(file_info_list) == 0:
        logging.info(f"No files found, nothing to backup.")
        return

    compression_settings = atbu_cfg_to_use.get_compression_settings_deep_copy(
        storage_def_name=storage_def_name,
    )
    if args.compression is not None:
        compression_settings[CONFIG_VALUE_NAME_COMPRESSION_LEVEL] = args.compression

    logging.info(f"Backup destination: {dest_location}")
    with Backup(
        backup_type=backup_type,
        deduplication_option=deduplication_option,
        compression_settings=compression_settings,
        sneaky_corruption_detection=sneaky_corruption_detection,
        primary_backup_info_dir=backup_info_dirs[0],
        secondary_backup_info_dirs=backup_info_dirs[1:],
        source_file_info_list=file_info_list,
        storage_def=storage_def,
    ) as backup:
        backup.backup_files()

    if backup.is_completely_successful():
        logging.info(f"Success, no errors detected.")
        return 0
    else:
        logging.info(
            f"Some errors were detected. See prior messages and/or logs for details."
        )
        return 1
