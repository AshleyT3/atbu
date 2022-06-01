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
r"""Recover-related command line handlers.
"""

from concurrent.futures import Future
from concurrent import futures
from concurrent.futures import ALL_COMPLETED, ProcessPoolExecutor
from datetime import datetime
import glob
import os
import logging
import re
from shutil import copy2

from ..common.exception import (
    BackupInformationFileTimestampNotFound,
    BackupInformationRecoveryFailed,
    InvalidCommandLineArgument,
    StorageDefinitionNotFoundError,
)
from ..common.util_helpers import prompt_YN
from .config import (
    AtbuConfig,
)
from .restore import RestoreFile
from .backup_core import (
    ANOMALY_KIND_UNEXPECTED_STATE,
    BACKUP_INFO_EXTENSION,
    BACKUP_INFO_TIME_STAMP_FORMAT,
    Anomaly,
    BackupFileInformation,
    StorageDefinition,
    file_operation_future_result,
)


def sort_backup_info_filename_list(filename_list: list[str]):
    re_match_time_stamp = re.compile(rf"(.*)-(\d{{8}}-\d{{6}}){BACKUP_INFO_EXTENSION}")
    temp_list: list[str] = []
    for filename in filename_list:
        m = re_match_time_stamp.match(string=filename)
        if not m:
            continue
        date_time_stamp_str = m.groups()[1]
        dt = datetime.strptime(date_time_stamp_str, BACKUP_INFO_TIME_STAMP_FORMAT)
        temp_list.append(
            (
                filename,
                dt,
            )
        )
    temp_list.sort(key=lambda t: t[1])
    return list(map(lambda t: t[0], temp_list))


def remove_timestamp_from_backupinfo_filename(filename: str):
    re_match_time_stamp = re.compile(
        rf"(.*)(-\d{{8}}-\d{{6}})({BACKUP_INFO_EXTENSION})"
    )
    m = re_match_time_stamp.match(filename)
    if not m:
        raise BackupInformationFileTimestampNotFound(
            f"The backup information timestamp was not found: {filename}"
        )
    return f"{m.groups()[0]}{m.groups()[2]}"


def handle_restore_backup_info(
    storage_def_name: str,
    atbu_cfg: AtbuConfig = None,
    prompt_if_exists: bool = True,
):
    if atbu_cfg is None:
        atbu_cfg = AtbuConfig.access_default_config()
    backup_info_dir = atbu_cfg.get_backup_info_dir()
    storage_def_dict = atbu_cfg.get_storage_def_with_resolved_secrets_deep_copy(
        storage_def_name=storage_def_name
    )
    sd = StorageDefinition.storage_def_from_dict(
        storage_def_name=storage_def_name, storage_def_dict=storage_def_dict
    )
    existing_backup_info_pat = backup_info_dir / f"{storage_def_name}*"
    existing_backup_info = glob.glob(pathname=str(existing_backup_info_pat))
    if prompt_if_exists and len(existing_backup_info) > 0:
        print(f"Found existing local backup info for {storage_def_name}:")
        for ebi in existing_backup_info:
            print(f"  {ebi}")
        print(
            f"""
The recover operation may need to overwrite some or all of the backup information files
listed above. If you are uncertain, you may want to backup those files before proceeding.
"""
        )
        a = prompt_YN(
            prompt_msg=f"You are about to overwrite local backup information.",
            prompt_question=f"Are you certain you want to overwrite local backup information? ",
            default_enter_ans="n",
        )
        if a != "y":
            print("The local backup information will not be overwritten.")
            print("The recovery will be aborted.")
            return
    logging.info(f"Restoring backup information...")
    interface = sd.create_storage_interface()
    c = interface.get_container(container_name=sd.container_name)
    restore_fi_list: list[RestoreFile] = []
    backup_info_objects = c.list_objects(prefix=sd.storage_def_name)
    for bio in backup_info_objects:
        print("Building file information for storage objects...")
        print(f"    {bio.name}")
        fi_bi = BackupFileInformation(path=str(backup_info_dir / bio.name))
        fi_bi.implicit_refresh_allowed = False
        fi_bi.populate_from_header = True
        fi_bi.size_in_bytes = bio.size  # Use storage size until header read.
        fi_bi.restore_path_override = str(backup_info_dir / bio.name)
        fi_bi.storage_object_name = str(bio.name)
        restore_file_bi = RestoreFile(
            file_info=fi_bi,
            dest_root_location=str(backup_info_dir),
            allow_overwrite=True,
            storage_def=sd,
        )
        restore_fi_list.append(restore_file_bi)
    anomalies: list[Anomaly] = []
    ppe = ProcessPoolExecutor()
    fut_list: list[Future] = []
    for r_fi in restore_fi_list:
        fut_list.append(ppe.submit(r_fi.run))
    done, not_done = futures.wait(set(fut_list), return_when=ALL_COMPLETED)
    if len(done) != len(fut_list):
        msg = (
            f"Expected len(fut_list) restores to be completed but got {len(done)} instead. "
            f"Processing whatever is done but you should resolves this issue for proper recovery. "
            f"done={len(done)} not_done={len(not_done)}"
        )
        logging.error(msg)
        anomalies.append(
            Anomaly(
                kind=ANOMALY_KIND_UNEXPECTED_STATE,
                message=msg,
            )
        )
    for f in done:
        fi = file_operation_future_result(
            f=f, anomalies=anomalies, the_operation="Recover backup info"
        )
        if fi is not None and fi.is_successful:
            logging.info(f"Successfully restored {fi.path}")
    existing_backup_info_pat = (
        backup_info_dir / f"{storage_def_name}*{BACKUP_INFO_EXTENSION}"
    )
    existing_backup_info = glob.glob(pathname=str(existing_backup_info_pat))
    existing_backup_info = sort_backup_info_filename_list(
        filename_list=existing_backup_info
    )
    newest_backup_info = existing_backup_info[-1]
    newest_backup_info_wo_stamp = remove_timestamp_from_backupinfo_filename(
        filename=newest_backup_info
    )
    logging.info(f"Copying {newest_backup_info} to {newest_backup_info_wo_stamp}...")
    copy2(src=newest_backup_info, dst=newest_backup_info_wo_stamp)


def handle_recover(args):
    logging.debug(f"handle_recover")
    storage_def_name = None
    storage_def_config_filename = None
    for arg in args.storage_def_cred_cfg:
        if os.path.isfile(arg):
            if storage_def_config_filename is not None:
                raise InvalidCommandLineArgument(
                    f"Expecting one filename maximum but got two: "
                    f"1={storage_def_config_filename} 2={arg}"
                )
            storage_def_config_filename = arg
        else:
            if storage_def_name is not None:
                raise InvalidCommandLineArgument(
                    f"Expecting one storage definition name but got two: "
                    f"1={storage_def_name} 2={arg}"
                )
            storage_def_name = arg

    # A storage def name which is a folder is always a filesystem storage...
    if storage_def_name and os.path.isdir(storage_def_name):
        filesystem_dir = os.path.abspath(storage_def_name)
        atbu_cfg, storage_def_name, _ = AtbuConfig.access_filesystem_config(
            storage_location_path=filesystem_dir,
            create_if_not_exist=True,
            prompt_to_create=args.prompt,
        )
        # If a config/cred backup file was supplied, import.
        if storage_def_config_filename is not None:
            storage_def_name = atbu_cfg.restore_storage_def(
                storage_def_new_name=None,
                backup_file_path=storage_def_config_filename,
                prompt_if_exists=args.prompt,
            )
            if storage_def_name is None:
                raise BackupInformationRecoveryFailed(
                    f"Could not recover the configuration from {storage_def_config_filename}"
                )
        if not atbu_cfg.is_storage_def_exists(storage_def_name=storage_def_name):
            raise StorageDefinitionNotFoundError(
                f"The storage definition was not found: {storage_def_name}"
            )
        # Restore backup information.
        handle_restore_backup_info(
            storage_def_name=storage_def_name,
            atbu_cfg=atbu_cfg,
            prompt_if_exists=args.prompt,
        )
    else:
        # Non-filesystem (cloud) case.
        if storage_def_name is not None:
            storage_def_name = storage_def_name.lower()
        atbu_cfg = AtbuConfig.access_default_config()
        if storage_def_config_filename is not None:
            # Import config/cred file.
            storage_def_name = atbu_cfg.restore_storage_def(
                storage_def_new_name=storage_def_name,
                backup_file_path=storage_def_config_filename,
                prompt_if_exists=args.prompt,
            )
            if storage_def_name is None:
                raise BackupInformationRecoveryFailed(
                    f"Could not recover the configuration from {storage_def_config_filename}"
                )
        if not atbu_cfg.is_storage_def_exists(storage_def_name=storage_def_name):
            raise StorageDefinitionNotFoundError(
                f"The storage definition was not found: {storage_def_name}"
            )
        handle_restore_backup_info(
            storage_def_name=storage_def_name,
            atbu_cfg=atbu_cfg,
            prompt_if_exists=args.prompt,
        )
    logging.info(f"Completed.")
