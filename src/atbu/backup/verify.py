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
r"""Verify backups.
"""
import io
import logging
from pathlib import Path
from concurrent import futures
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor

from ..common.exception import (
    CompareBytesMistmatchError,
    InvalidStateError,
    VerifyFailure,
    VerifyFilePathNotFoundError,
    exc_to_string,
    AlreadyUsedError,
)
from ..common.hasher import DEFAULT_HASH_ALGORITHM, HasherDefinitions
from ..common.mp_global import (
    get_process_pool_exec_init_func,
    get_process_pool_exec_init_args,
)
from .backup_core import (
    DEFAULT_MAX_SIMULTANEOUS_FILE_BACKUPS,
    Anomaly,
    log_anomalies_report,
    StorageDefinition,
    BackupFileInformation,
    StorageFileRetriever,
    file_operation_futures_to_results,
)
from .backup_selections import (
    SpecificBackupSelection,
    get_all_specific_backup_file_info,
    user_specifiers_to_selections,
    verify_specific_backup_selection_list,
)


class VerifyFile(StorageFileRetriever):
    def __init__(
        self,
        storage_def: StorageDefinition,
        file_info: BackupFileInformation,
        is_perform_local_compare: bool = False,
        local_compare_root_location: str = None,
    ):
        super().__init__(file_info=file_info, storage_def=storage_def)
        #
        # No local compare: local_compare=False local_compare_root_location=N/A
        # Local compare against orig location: local_compare=True local_compare_root_location=None
        # Local compare against specified location: local_compare=True local_compare_root_location=<specified_location>
        #
        self.is_perform_local_compare = is_perform_local_compare
        self.local_compare_root_location = None
        self.local_compare_path = None
        self.local_compare_path_str = None
        if self.is_perform_local_compare:
            if local_compare_root_location:
                # Some location off a specified root location.
                self.local_compare_root_location = Path(local_compare_root_location)
                self.local_compare_path = (
                    self.local_compare_root_location
                    / self._file_info.path_without_discovery_path
                )
                self.local_compare_path_str = str(self.local_compare_path)
            else:
                # Original backup path.
                self.local_compare_path = Path(self._file_info.path)
                self.local_compare_path_str = self._file_info.path
        self.local_compare_file: io.FileIO = None
        self.total_compare_bytes: int = 0
        self.hasher_defs = HasherDefinitions([DEFAULT_HASH_ALGORITHM])

    @property
    def path_for_logging(self) -> str:
        if self.local_compare_path_str is not None:
            return self.local_compare_path_str
        return super().path_for_logging

    def prepare_destination(self):
        if not self.is_perform_local_compare:
            return
        if not self.local_compare_path.exists():
            raise VerifyFilePathNotFoundError(
                f"The verify file destination path was not found: {str(self.local_compare_path)}"
            )
        self.local_compare_file = open(self.local_compare_path_str, "rb")

    def attempt_failed_cleanup(self):
        if self.local_compare_file:
            self.local_compare_file.close()
            self.local_compare_file = None

    def report_progress(self, percent: int):
        logging.info(f"{percent: >3}% completed of {self._file_info.path_without_root}")

    def process_decrypted_chunk(self, decrypted_chunk: bytes):
        if not self.is_perform_local_compare:
            return
        if not self.local_compare_file:
            raise InvalidStateError(
                f"VerifyFile: Expected self.dest_file to be set/open."
            )
        cur_pos = self.local_compare_file.tell()
        local_chunk = self.local_compare_file.read(len(decrypted_chunk))
        if decrypted_chunk != local_chunk:
            raise VerifyFailure(
                f"VerifyFile: The file verification failed: "
                f"cur_pos={cur_pos} "
                f"storage_chunk_size={len(decrypted_chunk)} "
                f"local_chunk_size={len(local_chunk)} "
                f"path={self.local_compare_path_str}"
            )
        self.total_compare_bytes += len(decrypted_chunk)

    def download_completed(self):

        if self.local_compare_file:
            self.local_compare_file.close()
            self.local_compare_file = None

        self.perform_common_checks(
            log_msg_prefix_str="VerifyFile",
            local_file_path_str=self.path_for_logging,
            orig_file_info=self._file_info,
        )

        if (
            self.is_perform_local_compare
            and self.total_compare_bytes != self._file_info.size_in_bytes
        ):
            raise CompareBytesMistmatchError(
                f"VerifyFile: Bytes compared with local file are mismatched to file size: "
                f"compare_bytes={self.total_compare_bytes} local_bytes={self._file_info.size_in_bytes}"
            )

    def final_cleanup(self):
        if self.local_compare_file:
            self.local_compare_file.close()
            self.local_compare_file = None


class Verify:
    MAX_SIMULTANEOUS_FILES = DEFAULT_MAX_SIMULTANEOUS_FILE_BACKUPS

    def __init__(
        self,
        verify_selections: list[SpecificBackupSelection],
        local_compare: bool = False,
        local_compare_root_location: str = None,
    ) -> None:
        if len(verify_selections) == 0:
            raise InvalidStateError(
                f"VerifyFile requires sbs_list to have at least one SpecificBackupSelection instance."
            )
        self.verify_selections = verify_selections
        if not isinstance(self.verify_selections[0].storage_def, StorageDefinition):
            raise ValueError(f"The storage_def must be a StorageDefinition.")
        self._storage_def = self.verify_selections[0].storage_def
        self.selected_files: list[BackupFileInformation] = None
        self.local_compare = local_compare
        self.local_compare_root_location = local_compare_root_location
        self._process_exec = ProcessPoolExecutor(
            max_workers=Verify.MAX_SIMULTANEOUS_FILES,
            initializer=get_process_pool_exec_init_func(),
            initargs=get_process_pool_exec_init_args(),
        )
        self.anomalies: list[Anomaly] = []
        self.success_count = 0
        self._is_used = False

    @property
    def storage_def(self) -> StorageDefinition:
        return self._storage_def

    @property
    def is_failed(self):
        return len(self.anomalies) > 0

    def _schedule_verify_file_process(self, file_info: BackupFileInformation):
        """Schedule the file_info for verify, return a Future."""
        future: Future = self._process_exec.submit(
            VerifyFile.run,
            VerifyFile(
                storage_def=self.storage_def,
                file_info=file_info,
                is_perform_local_compare=self.local_compare,
                local_compare_root_location=self.local_compare_root_location,
            ),
        )
        return future

    def _verify_files(self):
        if self._is_used:
            raise AlreadyUsedError(f"This instance has already been used.")
        self._is_used = True
        logging.info(f"Starting verify from '{self.storage_def.storage_def_name}'...")
        pending_verifications = set()
        try:
            logging.info(f"Scheduling verification jobs...")
            for file_info in self.selected_files:
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
                future = self._schedule_verify_file_process(file_info=file_info)
                pending_verifications.add(future)
        except Exception as ex:
            logging.error(
                f"Unexpected exception during _verify_files. {exc_to_string(ex)}"
            )
            raise
        finally:
            logging.info(f"Wait for verify file operations to complete...")
            while len(pending_verifications) > 0:
                done, pending_verifications = futures.wait(
                    fs=pending_verifications, return_when=FIRST_COMPLETED
                )
                num_completed = len(done)
                fi_complete = []
                new_anomalies: list[Anomaly] = []
                file_operation_futures_to_results(
                    fs=done,
                    fi_list=fi_complete,
                    anomalies=new_anomalies,
                    the_operation="Verify",
                )
                self.success_count += num_completed - len(new_anomalies)
                self.anomalies.extend(new_anomalies)

    def verify_files(self):
        self.selected_files = get_all_specific_backup_file_info(
            sbs_list=self.verify_selections
        )
        self._verify_files()
        logging.info(f"All file verify operations have completed.")
        if len(self.anomalies) == 0:
            logging.info(f"***************")
            logging.info(f"*** SUCCESS ***")
            logging.info(f"***************")
            logging.info(f"No errors detected during verify.")
        else:
            log_anomalies_report(anomalies=self.anomalies)
        logging.info(f"{'Total files ':.<45} {len(self.selected_files)}")
        logging.info(f"{'Total errors ':.<45} {len(self.anomalies)}")
        logging.info(f"{'Total success ':.<45} {self.success_count}")


def verify_storage(
    sbs_list: list[SpecificBackupSelection],
    local_compare: bool,
    local_compare_root_location: str,
):
    verify_specific_backup_selection_list(sbs_list=sbs_list)
    verify = Verify(
        verify_selections=sbs_list,
        local_compare=local_compare,
        local_compare_root_location=local_compare_root_location,
    )
    verify.verify_files()
    return not verify.is_failed


def handle_verify(args):
    logging.debug(f"handle_verify")
    source_specifiers: list[str] = args.source_storage_specifiers
    sbs_list_list = user_specifiers_to_selections(specifiers=source_specifiers)
    for sbs_list in sbs_list_list:
        sbs_fi_count = 0
        for sbs in sbs_list:
            sbs_fi_count += len(sbs.selected_fi)
        logging.info(
            f"Will verify {sbs_fi_count} files in '{sbs_list[0].storage_def_name}'"
        )

    # No selections is failure.
    is_overall_success = len(sbs_list_list) > 0
    for sbs_list in sbs_list_list:
        is_this_successful = verify_storage(
            sbs_list=sbs_list,
            local_compare=args.compare,
            local_compare_root_location=args.compare_root,
        )
        if not is_this_successful:
            is_overall_success = False
    if is_overall_success:
        logging.info(f"Finished... no errors detected.")
        return 0
    else:
        logging.info(f"Finished... errors were detected.")
        return 1
