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
r"""Restore files.
"""
from concurrent import futures
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor
import glob
import os
import logging
from pathlib import Path
import re
from typing import Iterator

from ..common.constants import (
    ATBU_FILE_BACKUP_EXTENSION,
    ATBU_FILE_BACKUP_EXTENSION_ENCRYPTED,
)
from ..common.exception import *
from ..common.hasher import DEFAULT_HASH_ALGORITHM, HasherDefinitions
from .chunk_reader import ChunkSizeFileReader
from .config import (
    AtbuConfig,
    is_existing_filesystem_storage_path,
    parse_storage_def_specifier,
)
from .storage_interface.base import DEFAULT_MAX_SIMULTANEOUS_FILE_BACKUPS
from .backup_core import (
    StorageDefinition,
    BackupFileInformation,
    StorageFileRetriever,
    file_operation_futures_to_results,
    Anomaly,
    log_anomalies_report,
)
from .backup_selections import (
    ensure_glob_pattern_for_dir,
    get_all_specific_backup_file_info,
    verify_specific_backup_selection_list,
    user_specifiers_to_selections,
)
from ..common.mp_global import (
    get_process_pool_exec_init_func,
    get_process_pool_exec_init_args,
)


class RestoreFile(StorageFileRetriever):
    def __init__(
        self,
        file_info: BackupFileInformation,
        dest_root_location: str,
        allow_overwrite: bool,
        storage_def: StorageDefinition,
    ):
        super().__init__(file_info=file_info, storage_def=storage_def)
        self.dest_root_location = Path(dest_root_location)
        self.allow_overwrite = allow_overwrite
        self.dest_path = self.dest_root_location / self._file_info.restore_path
        self.dest_path_str = str(self.dest_path)
        self.dest_path_existed_beforehand: bool = (
            None  # For sanity check against allow_overwrite.
        )
        self.dest_file = None
        self.hasher_defs = HasherDefinitions([DEFAULT_HASH_ALGORITHM])

    def get_download_iterator(self) -> tuple[Iterator[bytes], tuple[Exception]]:
        if not self._file_info.is_decrypt_operation:
            return super().get_download_iterator()
        iterator = ChunkSizeFileReader(
            path=self._file_info.path,
            chunk_size=self._storage_def.download_chunk_size,
            user_func=None,
        )
        iterator.open()
        retry_exception_types = ()
        return (
            iterator,
            retry_exception_types,
        )

    def prepare_destination(self):
        if self.dest_path_existed_beforehand is None:
            # This is the existence state before any of our efforts.
            self.dest_path_existed_beforehand = self.dest_path.exists()
        # Given attempt_failed_cleanup cleans up any file created by
        # our efforts, the following should always pass first, even
        # on a retry attempt.
        if self.dest_path.exists() and not self.allow_overwrite:
            raise RestoreFilePathAlreadyExistsError(
                f"The restore file destination path already exists and allow_overwrite={self.allow_overwrite}: {str(self.dest_path)}"
            )
        if self._file_info.is_decrypt_operation:
            self.dest_path = self.dest_root_location / self.preamble_path_without_root
            self.dest_path_str = str(self.dest_path)
        self.dest_path.parent.mkdir(parents=True, exist_ok=True)
        self.dest_file = open(self.dest_path_str, "wb")

    def attempt_failed_cleanup(self):
        """Called after failed attempt. State at this point
        is either allow_overwrite==True or the dest file did
        exist to begin with. Either way, cleanup for next
        retry attempt.
        """
        if self.dest_file:
            self.dest_file.close()
            self.dest_file = None
        if self.dest_path_existed_beforehand is None:
            # Must be set by prepare.
            raise InvalidStateError(
                f"The self.dest_path_existed_beforehand flag "
                f"should not be None at this point."
            )
        if self.dest_path.exists() and (
            self.allow_overwrite or not self.dest_path_existed_beforehand
        ):
            logging.info(
                f"Deleting file as part of retry prep: "
                f"allow_overwrite={self.allow_overwrite} "
                f"dest_path_existed_beforehand={self.dest_path_existed_beforehand} "
                f"path={self.dest_path_str}"
            )
            # Delete file after a failed attempt only if either overwrite
            # is allowed or the file was not there to begin with.
            os.unlink(path=self.dest_path_str)

    def report_progress(self, percent: int):
        logging.info(f"{percent: >3}% completed of {self.dest_path_str}")

    def process_decrypted_chunk(self, decrypted_chunk: bytes):
        if not self.dest_file:
            raise InvalidStateError(
                f"RestoreFile: Expected self.dest_file to be set/open."
            )
        self.dest_file.write(decrypted_chunk)

    def download_completed(self):

        if self.dest_file:
            self.dest_file.close()
            self.dest_file = None

        os.utime(
            path=self.dest_path_str,
            times=(
                self._file_info.accessed_time_posix,
                self._file_info.modified_time_posix,
            ),
        )

        self.perform_common_checks(
            log_msg_prefix_str="RestoreFile",
            local_file_path_str=self.dest_path_str,
            orig_file_info=self._file_info,
        )

    def download_failed(self):
        if self.dest_file:
            self.dest_file.close()
            self.dest_file = None
            try:
                os.unlink(path=self.dest_path_str)
            except FileNotFoundError:
                pass

    def final_cleanup(self):
        if self.dest_file:
            self.dest_file.close()
            self.dest_file = None


class Restore:
    MAX_SIMULTANEOUS_FILES = DEFAULT_MAX_SIMULTANEOUS_FILE_BACKUPS

    def __init__(
        self,
        storage_def: StorageDefinition,
        selections: list[BackupFileInformation],
        dest_root_location: str,
        allow_overwrite: bool,
        auto_path_mapping: bool,
    ) -> None:
        if not isinstance(storage_def, StorageDefinition):
            raise ValueError(f"The storage_def must be a StorageDefinition.")
        self._storage_def = storage_def
        if len(selections) == 0:
            raise InvalidStateError(
                f"RestoreFile requires sbs_list to have at least one SpecificBackupSelection instance."
            )
        self._selected_files: list[BackupFileInformation] = selections
        self.dest_root_location = dest_root_location
        self._allow_overwrite = allow_overwrite
        self._auto_path_mapping = auto_path_mapping
        self._hasher_defs = HasherDefinitions()
        self._process_exec = ProcessPoolExecutor(
            max_workers=Restore.MAX_SIMULTANEOUS_FILES,
            initializer=get_process_pool_exec_init_func(),
            initargs=get_process_pool_exec_init_args(),
        )
        self.success_count = 0
        self.anomalies: list[Anomaly] = []
        self._is_used = False

    @property
    def storage_def(self) -> StorageDefinition:
        return self._storage_def

    @property
    def is_failed(self):
        return len(self.anomalies) > 0

    def _schedule_restore_file_process(self, file_info: BackupFileInformation):
        """Schedule the file_info for restore, return a Future for the backup work."""
        future: Future = self._process_exec.submit(
            RestoreFile.run,
            RestoreFile(
                file_info=file_info,
                dest_root_location=self.dest_root_location,
                allow_overwrite=self._allow_overwrite,
                storage_def=self.storage_def,
            ),
        )
        return future

    def _restore_files(self):
        if self._is_used:
            raise AlreadyUsedError(f"This instance has already been used.")
        self._is_used = True
        logging.info(f"Starting restore from '{self.storage_def.storage_def_name}'...")
        pending_restores = set()
        try:
            logging.info(f"Scheduling restore jobs...")
            for file_info in self._selected_files:
                if file_info.is_unchanged_since_last:
                    logging.debug(
                        f"unchanged: path={file_info.path} "
                        f"path_wo_root={file_info.path_without_root} "
                        f"backing={file_info.backing_fi.path}"
                    )
                else:
                    logging.debug(
                        f"changed: path={file_info.path} "
                        f"path_wo_root={file_info.path_without_root} "
                        f"backing={file_info.backing_fi is not None}"
                    )
                logging.debug(f"")
                future = self._schedule_restore_file_process(file_info=file_info)
                pending_restores.add(future)
        except Exception as ex:
            logging.error(
                f"Unexpected exception during _restore_files. {exc_to_string(ex)}"
            )
            raise
        finally:
            logging.info(f"Wait for restore file operations to complete...")
            while len(pending_restores) > 0:
                done, pending_restores = futures.wait(
                    fs=pending_restores, return_when=FIRST_COMPLETED
                )
                num_completed = len(done)
                fi_complete = []
                new_anomalies: list[Anomaly] = []
                file_operation_futures_to_results(
                    fs=done,
                    fi_list=fi_complete,
                    anomalies=new_anomalies,
                    the_operation="Restore",
                )
                self.success_count += num_completed - len(new_anomalies)
                self.anomalies.extend(new_anomalies)

    def _get_unique_discovery_paths(self):
        # Create a list with unique discovery paths of the entire set of selected files.
        # Drop the drive letter and initial separator, while adding a add a trailing
        # separator for the 'startswith' check further below.
        all_disc_paths: set[str] = set(
            [
                f"{os.path.normcase(os.path.splitdrive(fi.discovery_path)[1][1:])}{os.path.sep}"
                for fi in self._selected_files
            ]
        )
        all_disc_paths = sorted(all_disc_paths)
        sel_disc_paths: list[str] = []
        cur_disc_path = None
        # Retain only the shortest path of all discovery paths.
        for d_path in all_disc_paths:
            if cur_disc_path is None or not d_path.startswith(cur_disc_path):
                cur_disc_path = d_path
                sel_disc_paths.append(d_path)
                continue
        return sel_disc_paths

    def _perform_restore_path_auto_mapping(self):
        re_split_sep = re.compile(rf"[\\\/\{os.path.sep}]")
        sel_disc_paths = self._get_unique_discovery_paths()
        if len(sel_disc_paths) == 1:
            sel_disc_path = sel_disc_paths[0]
            num_to_remove = max(len(re_split_sep.split(sel_disc_path)) - 1, 0)
        else:
            sel_disc_paths_parts = list(map(re_split_sep.split, sel_disc_paths))
            min_part_count = min(
                map(
                    lambda pa: len(pa), sel_disc_paths_parts
                )  # pylint: disable=unnecessary-lambda
            )  # pylint: disable=unnecessary-lambda
            part_ele_idx = 0
            fin = False
            while not fin and part_ele_idx < min_part_count:
                v = sel_disc_paths_parts[0][part_ele_idx]
                for pa in sel_disc_paths_parts[1:]:
                    if v == pa[part_ele_idx]:
                        part_ele_idx += 1
                        continue
                    fin = True
                    break
            num_to_remove = part_ele_idx
        for fi in self._selected_files:
            parts = re_split_sep.split(fi.path_without_root)
            parts = parts[num_to_remove:]
            fi.restore_path_override = os.path.join(*parts)

    def restore_files(self):
        if self._auto_path_mapping:
            self._perform_restore_path_auto_mapping()
        self._restore_files()
        logging.info(f"All restore file operations have completed.")
        if len(self.anomalies) == 0:
            logging.info(f"***************")
            logging.info(f"*** SUCCESS ***")
            logging.info(f"***************")
            logging.info(f"No errors detected during restore.")
        else:
            log_anomalies_report(anomalies=self.anomalies)
        logging.info(f"{'Total files ':.<45} {len(self._selected_files)}")
        logging.info(f"{'Total errors ':.<45} {len(self.anomalies)}")
        logging.info(f"{'Total success ':.<45} {self.success_count}")


def restore_from_storage(
    storage_def: StorageDefinition,
    selections: list[BackupFileInformation],
    dest_root_location: str,
    allow_overwrite: bool,
    auto_path_mapping: bool,
) -> bool:
    restore = Restore(
        storage_def=storage_def,
        selections=selections,
        dest_root_location=dest_root_location,
        allow_overwrite=allow_overwrite,
        auto_path_mapping=auto_path_mapping,
    )
    restore.restore_files()
    return not restore.is_failed


def handle_decrypt(args):
    storage_def_name: str = args.private_key_storage_specifier
    source_files_dir: str = args.source_files_dir
    dest_root_location: str = args.restore_dir
    allow_overwrite = args.overwrite

    storage_atbu_cfg: AtbuConfig
    storage_def_dict: dict = None
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
        storage_def_dict = (
            storage_atbu_cfg.get_storage_def_with_resolved_secrets_deep_copy(
                storage_def_name=storage_def_name,
                keep_secrets_base64_encoded=False,
            )
        )
    else:
        #
        # Filesystem storage.
        #
        (
            storage_atbu_cfg,
            storage_def_name,
            storage_def_dict,
        ) = AtbuConfig.access_filesystem_config(
            storage_location_path=storage_def_name,
            resolve_storage_def_secrets=True,
            create_if_not_exist=False,
            prompt_to_create=False,
        )

    storage_def = StorageDefinition.storage_def_from_dict(
        storage_def_name=storage_def_name,
        storage_def_dict=storage_def_dict,
    )

    source_files_dir = ensure_glob_pattern_for_dir(dir_wc=source_files_dir)

    path_list = glob.glob(pathname=source_files_dir, recursive=True)

    if len(path_list) == 0:
        raise InvalidCommandLineArgument(f"No files found for '{source_files_dir}'.")

    path_list = list(
        filter(
            lambda p: os.path.isfile(p)
            and (
                p.endswith(ATBU_FILE_BACKUP_EXTENSION_ENCRYPTED)
                or p.endswith(ATBU_FILE_BACKUP_EXTENSION)
            ),
            path_list,
        )
    )

    if len(path_list) == 0:
        raise InvalidCommandLineArgument(
            f"No {ATBU_FILE_BACKUP_EXTENSION_ENCRYPTED} or {ATBU_FILE_BACKUP_EXTENSION} files found for '{source_files_dir}'."
        )

    selections = list(
        map(
            lambda p: BackupFileInformation(path=p),
            path_list,
        )
    )

    for fi in selections:
        fi.is_decrypt_operation = True
        fi.populate_from_header = True

    is_this_successful = restore_from_storage(
        storage_def=storage_def,
        selections=selections,
        dest_root_location=dest_root_location,
        allow_overwrite=allow_overwrite,
        auto_path_mapping=False,
    )
    if is_this_successful:
        logging.info(f"Finished... no errors detected.")
        return 0
    else:
        logging.info(f"Finished... errors were detected.")
        return 1


def handle_restore(args):
    source_specifiers: str = args.source_storage_specifiers
    dest_root_location: str = args.restore_dir
    allow_overwrite = args.overwrite
    auto_path_mapping = args.auto_mapping

    sbs_list_list = user_specifiers_to_selections(specifiers=source_specifiers)
    for sbs_list in sbs_list_list:
        sbs_fi_count = 0
        for sbs in sbs_list:
            sbs_fi_count += len(sbs.selected_fi)
        logging.info(
            f"Will restore {sbs_fi_count} files from '{sbs_list[0].storage_def_name}'"
        )

    # No selections is failure.
    is_overall_success = len(sbs_list_list) > 0
    for sbs_list in sbs_list_list:

        verify_specific_backup_selection_list(sbs_list=sbs_list)
        if not isinstance(sbs_list[0].storage_def, StorageDefinition):
            raise InvalidStateError(f"The storage_def must be a StorageDefinition.")
        storage_def = sbs_list[0].storage_def
        selections = get_all_specific_backup_file_info(sbs_list=sbs_list)

        is_this_successful = restore_from_storage(
            storage_def=storage_def,
            selections=selections,
            dest_root_location=dest_root_location,
            allow_overwrite=allow_overwrite,
            auto_path_mapping=auto_path_mapping,
        )
        if not is_this_successful:
            is_overall_success = False
    if is_overall_success:
        logging.info(f"Finished... no errors detected.")
        return 0
    else:
        logging.info(f"Finished... errors were detected.")
        return 1
