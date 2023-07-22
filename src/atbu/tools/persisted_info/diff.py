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
r"""Persistent file information diff'ing.
"""

# pylint: disable=line-too-long

import os
import logging
import re
import time

from atbu.common.util_helpers import is_platform_path_case_sensitive
from atbu.mp_pipeline.mp_global import get_verbosity_level

from ..backup.constants import *
from ..backup.exception import *
from ..backup.global_hasher import GlobalHasherDefinitions
from .database import (
    FileInformationDatabaseCollection,
    extract_location_info,
    rel_path,
)
from .file_info import (
    CHANGE_DETECTION_TYPE_DATESIZE,
    FileInformationPersistent,
    is_file_info_list_bad_state,
)

DIFF_COMMAND_MOVE_DUPLICATES = "move-duplicates"
DIFF_COMMAND_REMOVE_DUPLICATES = "remove-duplicates"
DIFF_COMMAND_CHOICES = [
    DIFF_COMMAND_MOVE_DUPLICATES,
    DIFF_COMMAND_REMOVE_DUPLICATES,
]


def remove_empty_directorires(
    root_dir_paths: set[str],
    whatif: bool,
):
    """Remove empty directories within the specified root_dir_paths."""
    whatif_str = "(what_if)" if whatif else ""
    directory_removal_attempts = 3
    retry_directory_removal = True
    while directory_removal_attempts > 0 and retry_directory_removal:
        logging.info(f"Removing empty directories...")
        retry_directory_removal = False
        directory_removal_attempts -= 1
        for directory_affected in root_dir_paths:
            if os.path.isdir(directory_affected):
                try:
                    if not whatif:
                        if len(os.listdir(directory_affected)) == 0:
                            os.removedirs(directory_affected)
                    logging.info(
                        f"Successfully removed{whatif_str} {directory_affected}"
                    )
                except OSError:
                    retry_directory_removal = True
                    logging.info(f"Failed to remove {directory_affected}")
        if retry_directory_removal and directory_removal_attempts >= 1:
            logging.info(f"Some directories were not removed, trying again.")
            logging.info(f"If issue persists, check directory permissions/attributes.")
            time.sleep(2)
    directories_removed = 0
    for directory_affected in root_dir_paths:
        if not os.path.isdir(directory_affected):
            directories_removed += 1
    return directories_removed


class FileInformationCommandBase:
    def __init__(
        self,
        root_source_dir: str,
        file_info_to_affect: list[FileInformationPersistent],
        whatif: bool = False,
    ):
        self.whatif = whatif
        if root_source_dir is None or not os.path.isdir(root_source_dir):
            raise LocationDoesNotExistException(
                f"The location is not a directory: {root_source_dir}"
            )
        self.root_source_dir = root_source_dir
        self._file_info_to_affect = file_info_to_affect
        self.directories_affected = set()
        if self.whatif:
            self.whatif_str = "(--whatif) "
        else:
            self.whatif_str = ""
        self.unique_files_affected = 0
        self.physical_files_total = 0
        self.physical_files_affected = 0
        self.config_files_total = 0
        self.config_files_affected = 0
        self.directories_removed = 0

    @property
    def file_info_to_affect(self) -> list[FileInformationPersistent]:
        """The file information upon which to perform the comand."""
        return self._file_info_to_affect

    @file_info_to_affect.setter
    def file_info_to_affect(self, value: list[FileInformationPersistent]):
        if value is None:
            raise ValueError(f"file_info_to_affect must be specified.")
        self._file_info_to_affect = value


class MoveFileInformationCommand(FileInformationCommandBase):
    def __init__(
        self,
        root_source_dir: str,
        file_info_to_affect: list[FileInformationPersistent],
        move_destination: str,
        whatif: bool = False,
    ):
        super().__init__(
            root_source_dir=root_source_dir,
            file_info_to_affect=file_info_to_affect,
            whatif=whatif,
        )
        if move_destination is None:
            raise ValueError(
                "move_destination is None but must be an absolute path to an existing directory."
            )
        if os.path.abspath(move_destination).strip("\\/") != move_destination.strip(
            "\\/"
        ):
            raise ValueError(
                "move_destination must be an absolute path to an existing directory."
            )
        self.move_destination = move_destination

    def _get_file_info_move_dest_path(
        self,
        file_info: FileInformationPersistent,
        root_source_dir: str,
        root_dest_dir: str,
    ):
        flags = 0
        if not is_platform_path_case_sensitive():
            flags = re.IGNORECASE
        actual_root_source_dir = os.path.commonpath(
            [file_info.dirname, root_source_dir]
        )
        rel_file_info_path = re.sub(
            f"^{re.escape(actual_root_source_dir)}", "", file_info.dirname, flags=flags
        ).lstrip("\\/")
        return os.path.join(
            root_dest_dir, rel_file_info_path, file_info.basename
        ), os.path.join(root_dest_dir, rel_file_info_path, file_info.config_basename)

    def _move_file_to_dest_path(
        self,
        file_info: FileInformationPersistent,
        root_source_dir: str,
        root_dest_dir: str,
        whatif: bool,
    ):
        """Move a file and its FileInformationPersistent from
        a source path to a destination path, retaining the same
        directory structure for non-root portions of the paths.
        """
        file_moved = False
        config_file_moved = False
        (
            destination_file_path,
            destination_config_file_path,
        ) = self._get_file_info_move_dest_path(
            file_info, root_source_dir, root_dest_dir
        )
        if file_info.is_loaded_from_db:
            destination_config_file_path = None
        logging.info(
            f"Moving{self.whatif_str} {file_info.path} "
            f"---to--> "
            f"{destination_file_path} digest={file_info.get_current_digest()}"
        )
        if not whatif:
            os.makedirs(os.path.split(destination_file_path)[0], exist_ok=True)
            os.renames(file_info.path, destination_file_path)
            file_moved = True
            if not file_info.is_loaded_from_db:
                logging.info(
                    f"Moving{self.whatif_str} "
                    f"{file_info.info_data_file_path} "
                    f"---to--> "
                    f"{destination_config_file_path}"
                )
                try:
                    os.makedirs(
                        os.path.split(destination_config_file_path)[0], exist_ok=True
                    )
                    os.renames(
                        file_info.info_data_file_path, destination_config_file_path
                    )
                    config_file_moved = True
                except Exception as ex:
                    try:
                        # Undo the successful user data file move.
                        os.renames(destination_file_path, file_info.path)
                    except Exception:
                        pass
                    logging.error(
                        f"Failure moving config file: "
                        f"path={file_info.info_data_file_path} "
                        f"{exc_to_string(ex)}"
                    )
                    raise
            if get_verbosity_level() > 0:
                logging.info(f"Move successful.")
        else:
            logging.info(
                f"Moving{self.whatif_str} "
                f"{file_info.path} "
                f"---to--> "
                f"{destination_file_path} "
                f"digest={file_info.get_current_digest()}"
            )
            logging.info(
                f"Moving{self.whatif_str} "
                f"{file_info.info_data_file_path} "
                f"---to--> "
                f"{destination_config_file_path}"
            )
            if get_verbosity_level() > 0:
                logging.info(f"Move successful.")
            file_moved = True
            config_file_moved = True
        return file_moved, config_file_moved

    def perform_command(self):
        """Move relevant files and associated config
        files from a source tree to a destination tree.
        """

        logging.info(
            f"======================================================================"
        )
        logging.info(
            f"                                MOVING                                "
        )
        logging.info(
            f"======================================================================"
        )
        logging.info(f"Moving duplicates in Location A: {self.root_source_dir}")

        unique_file_counter_hash_set = set()
        file_info_to_process: FileInformationPersistent
        for file_info_to_process in self.file_info_to_affect:
            unique_file_counter_hash_set.add(file_info_to_process.get_current_digest())
            self.physical_files_total += 1
            is_file_moved, is_config_file_moved = self._move_file_to_dest_path(
                file_info_to_process,
                self.root_source_dir,
                self.move_destination,
                whatif=self.whatif,
            )
            if is_file_moved:
                self.directories_affected.add(file_info_to_process.dirname)
                self.physical_files_affected += 1
            self.config_files_total += 1
            if is_config_file_moved:
                self.config_files_affected += 1
        self.unique_files_affected += len(unique_file_counter_hash_set)
        remove_empty_directorires(
            root_dir_paths=self.directories_affected,
            whatif=self.whatif,
        )
        self.directories_removed = sum(
            [1 for rd in self.directories_affected if not os.path.isdir(rd)]
        )

class RemoveFileInformationCommand(FileInformationCommandBase):
    def __init__(
        self,
        root_source_dir: str,
        file_info_to_affect: list[FileInformationPersistent],
        whatif: bool = False,
    ):
        super().__init__(
            root_source_dir=root_source_dir,
            file_info_to_affect=file_info_to_affect,
            whatif=whatif,
        )

    def _log_remove_error(
        self,
        is_config_remove_error: bool,
        file_info: FileInformationPersistent,
        exception: Exception,
    ) -> bool:
        """The a removal error, returns True if error
        should be raised, else do not raise.
        """
        file_path = file_info.path
        if is_config_remove_error:
            file_path = file_info.info_data_file_path
        logging.error(f"Removal failed: {file_path} error={exception}")
        if isinstance(exception, OSError):
            logging.error(
                f"Ensure the file is read/write, is not held/locked, "
                f"and that you have permission to remove the file."
            )
        elif isinstance(exception, FileNotFoundError):
            logging.error(f"The file was not found.")
        elif isinstance(exception, IsADirectoryError):
            logging.error(f"The path is a directory not a file.")
        else:
            logging.error(f"Unexpected exception.")
            return True
        if is_config_remove_error:
            logging.error(f"The config file could not be removed, raising exception.")
            return True  # Raise the exception.
        return False  # Do not raise the exception.

    def _remove_file(
        self,
        is_remove_config: bool,
        file_info_to_remove: FileInformationPersistent,
    ):
        if is_remove_config and file_info_to_remove.is_loaded_from_db:
            return
        path_to_remove = (
            file_info_to_remove.path
            if not is_remove_config
            else file_info_to_remove.info_data_file_path
        )
        if not is_remove_config:
            logging.info(
                f"Removing{self.whatif_str} {path_to_remove} "
                f"digest={file_info_to_remove.primary_digest}"
            )
        else:
            logging.info(f"Removing{self.whatif_str} {path_to_remove}")

        try:
            os.remove(path_to_remove)
            if get_verbosity_level() > 0:
                logging.info(f"Remove successful.")
        except OSError as err:
            raise_exception = self._log_remove_error(
                is_config_remove_error=is_remove_config,
                file_info=path_to_remove,
                exception=err,
            )
            if raise_exception:
                raise
            #
            # TODO: Add switch for selection to try to
            # remove read only (but not make that default)
            #
            # logging.warning(f"    OSError: {err}")
            # logging.warning(
            #     f"    Trying to remove read-only attribute: "
            #     f"chmod(""{file_info_to_remove.path}"",stat.S_IWRITE)"
            # )
            # os.chmod(file_info_to_remove.path, stat.S_IWRITE)
            # os.remove(file_info_to_remove.path)
            # file_removed = True
            #
        except BaseException as err:
            raise_exception = self._log_remove_error(
                is_config_remove_error=False,
                file_info=file_info_to_remove,
                exception=err,
            )
            if raise_exception:
                raise

    def _remove_file_and_file_info(
        self, file_info_to_remove: FileInformationPersistent, whatif: bool
    ) -> tuple[bool, bool]:
        file_removed = False
        config_file_removed = False
        is_loaded_from_db = file_info_to_remove.is_loaded_from_db
        if not is_loaded_from_db and not os.path.isfile(
            file_info_to_remove.info_data_file_path
        ):
            raise InvalidStateError(
                f"Unexpected state: {ATBU_ACRONUM_U} configuration file note found: "
                f"{file_info_to_remove.info_data_file_path}"
            )
        if not whatif:
            # Remove main user data file.
            self._remove_file(
                is_remove_config=False,
                file_info_to_remove=file_info_to_remove,
            )
            file_removed = True

            if not is_loaded_from_db:
                # Remove .atbu config file.
                self._remove_file(
                    is_remove_config=True,
                    file_info_to_remove=file_info_to_remove,
                )
                config_file_removed = True
        else:
            # For 'whatif' case, send feedback of successful removal if the file exists.
            if os.path.isfile(file_info_to_remove.path):
                logging.info(
                    f"Removing{self.whatif_str} "
                    f"{file_info_to_remove.path} "
                    f"digest={file_info_to_remove.get_current_digest()}"
                )
                if not is_loaded_from_db:
                    logging.info(
                        f"Removing{self.whatif_str} {file_info_to_remove.info_data_file_path}"
                    )
                    if get_verbosity_level() > 0:
                        logging.info(f"Remove successful.")
                file_removed = True
                config_file_removed = True
            else:
                logging.error(f"    File not found error.")
        return file_removed, config_file_removed

    def perform_command(self):
        logging.info(
            f"======================================================================"
        )
        logging.info(
            f"                                REMOVING                              "
        )
        logging.info(
            f"======================================================================"
        )
        logging.info(f"Removing duplicates in Location A: {self.root_source_dir}")
        unique_file_counter_hash_set = set()
        file_info_to_process: FileInformationPersistent
        for file_info_to_process in self.file_info_to_affect:
            unique_file_counter_hash_set.add(file_info_to_process.get_current_digest())
            self.physical_files_total += 1
            is_file_removed, is_config_files_removed = self._remove_file_and_file_info(
                file_info_to_remove=file_info_to_process,
                whatif=self.whatif,
            )
            if is_file_removed:
                self.directories_affected.add(file_info_to_process.dirname)
                self.physical_files_affected += 1
            self.config_files_total += 1
            if is_config_files_removed:
                self.config_files_affected += 1
        self.unique_files_affected += len(unique_file_counter_hash_set)
        self.directories_removed += remove_empty_directorires(
            root_dir_paths=self.directories_affected,
            whatif=self.whatif,
        )


def diff_locations(
    locationA_path: str,
    locationA_info: dict[str, list[FileInformationPersistent]],
    locationB_path: str,
    locationB_info: dict[str, list[FileInformationPersistent]],
    enforce_rel_path_match: bool,
):
    primary_hasher_name = GlobalHasherDefinitions().get_primary_hashing_algo_name()
    logging.info(f"Logging A unique objects ..... {len(locationA_info)}")
    logging.info(f"Logging B unique objects ..... {len(locationB_info)}")
    if len(locationA_info) == 0:
        logging.warning(f"No file info found for Location A")
    if len(locationB_info) == 0:
        logging.warning(f"No file info found for Location B")
    # Start with all items in Location A being in Location B, prune below,
    # whatever is left is result.
    locA_not_in_locB = dict(locationA_info)
    locA_in_locB = {}
    for digest, file_info_list_locA in locationA_info.items():
        if is_file_info_list_bad_state(
            primary_hasher_name=primary_hasher_name,
            file_info_list=file_info_list_locA,
        ):
            continue
        primary_digest_locA = file_info_list_locA[0].primary_digest
        if primary_digest_locA is None:
            logging.error(f"No primary digest found: {file_info_list_locA[0].path}")
            continue
        if digest != primary_digest_locA:
            raise DigestMistmatchError(
                f"Key digest does not match item in list. {digest} {primary_digest_locA}"
            )
        file_info_list_locB = locationB_info.get(primary_digest_locA)
        if file_info_list_locB is None:
            logging.debug(
                f"Location A file_info not in Location B: {primary_hasher_name} "
                f"digest={primary_digest_locA} "
                f"file_info[0]={file_info_list_locA[0].path}"
            )
            continue
        if is_file_info_list_bad_state(primary_hasher_name, file_info_list_locB):
            logging.warning(
                f"Location B file_info list bad state causes "
                f"location A file_info to be considered not in B."
            )
            continue
        # Sanity check
        primary_digest_locB = file_info_list_locB[0].primary_digest
        if primary_digest_locA != primary_digest_locB:
            logging.error(
                f"Location A and B primary digests do not match "
                f"when expected: {primary_hasher_name}_locA={primary_digest_locA} "
                f"{primary_hasher_name}_locB={primary_digest_locB} "
                f"pathA={file_info_list_locA[0].path} "
                f"pathB={file_info_list_locB[0].path}"
            )
            continue
        logging.debug(
            f"Location A and B digests match: "
            f"{primary_hasher_name}_locA={primary_digest_locA} "
            f"{primary_hasher_name}_locB={primary_digest_locB} "
            f"pathA={file_info_list_locA[0].path} "
            f"pathB={file_info_list_locB[0].path}"
        )
        logging.info(
            f"Location A and B digests match: "
            f"{primary_hasher_name}={primary_digest_locA} "
            f"{file_info_list_locA[0].basename}"
        )
        if enforce_rel_path_match:
            is_all_locA_matching = True
            for fi_a in file_info_list_locA:
                is_match_found = False
                rp_a = rel_path(top_level_dir=locationA_path, path=fi_a.nc_path)
                for fi_b in file_info_list_locB:
                    rp_b = rel_path(top_level_dir=locationB_path, path=fi_b.nc_path)
                    if rp_a == rp_b:
                        is_match_found = True
                        break
                if not is_match_found:
                    is_all_locA_matching = False
                    logging.debug(
                        f"Location A relative path not found in location B: "
                        f"pathA={rp_a}"
                    )
                    for fi_b in file_info_list_locB:
                        rp_b = rel_path(top_level_dir=locationB_path, path=fi_b.nc_path)
                        logging.debug(f"    Location B non-match: pathB={rp_b}")
                    break
            if not is_all_locA_matching:
                # Not considered found in both A and B given enforce_rel_path_match.
                continue
        # Item found in both Location A and B
        # Transfer item from "not in" dict to "in" dict, then delete from "not in" dict.
        locA_in_locB[primary_digest_locA] = locA_not_in_locB[primary_digest_locA]
        del locA_not_in_locB[primary_digest_locA]
    if len(locA_not_in_locB) == 0:
        logging.info("All items in Location A were found in Location B")
    else:
        logging.info(
            f"======================================== RESULTS ============================================="
        )
        logging.info(f"Files in Location A *not* found in Location B:")
        for digest, file_info_list in locA_not_in_locB.items():
            for file_info in file_info_list:
                logging.info(f"File in A *not* in B: {file_info.path}")
                if get_verbosity_level() > 0:
                    logging.info(file_info)
            logging.info("----------------------------------------")
    return locA_not_in_locB, locA_in_locB


def handle_diff(args):
    locations = extract_location_info(args.locations, min_required=2, max_allowed=2)
    locationA = locations[0][0]
    locationA_persist_types = locations[0][1]
    locationB = locations[1][0]
    locationB_persist_types = locations[1][1]

    locationA_DBs = FileInformationDatabaseCollection(
        source_path=locationA, persist_types=locationA_persist_types
    )

    locationB_DBs = FileInformationDatabaseCollection(
        source_path=locationB, persist_types=locationB_persist_types
    )

    logging.info(f"{'Location A ':.<40} {locationA}")
    logging.info(f"{'Location A persist types ':.<40} {locationA_persist_types}")
    logging.info(f"{'Location B ':.<40} {locationB}")
    logging.info(f"{'Location B persist types ':.<40} {locationB_persist_types}")

    whatif_str = " (--whatif)" if args.whatif else " "

    post_diff_command = None
    command_line_action_str = None
    if hasattr(args, "action"):
        command_line_action_str = args.action
        logging.debug(f"action_str={command_line_action_str}")
    if command_line_action_str == "move-duplicates":
        past_tense_verb = "moved"
        if not hasattr(args, "move_destination") or not args.move_destination:
            raise InvalidCommandLineArgument(
                "The --move-destination location has not been specified."
            )
        post_diff_command = MoveFileInformationCommand(
            root_source_dir=locationA,
            file_info_to_affect=None,
            move_destination=args.move_destination,
            whatif=args.whatif,
        )
    elif command_line_action_str == "remove-duplicates":
        past_tense_verb = "removed"
        if not os.path.isdir(locationA):
            raise InvalidCommandLineArgument(
                f"When --remove-duplicates is specified, "
                f"location A must be a directory. "
                f"Duplicates are removed from location A."
            )
        post_diff_command = RemoveFileInformationCommand(
            root_source_dir=locationA,
            file_info_to_affect=None,
            whatif=args.whatif,
        )
    elif command_line_action_str is None:
        pass
    else:
        raise InvalidCommandLineArgument(
            f"Unknown action specified: {command_line_action_str}"
        )

    logging.info(f"-" * 65)
    logging.info(f"Searching location A: {locationA}")
    updaterA = locationA_DBs.update(
        change_detection_type=args.change_detection_type,
        update_stale=args.update_stale,
        whatif=args.whatif,
    )
    locationA_info = locationA_DBs.get_dict_digest_to_fi()
    locationA_skipped = updaterA.skipped_files

    logging.info(f"-" * 65)
    logging.info(f"Searching location B: {locationB}")
    updaterB = locationB_DBs.update(
        change_detection_type=args.change_detection_type,
        update_stale=args.update_stale,
        whatif=args.whatif,
    )
    locationB_info = locationB_DBs.get_dict_digest_to_fi()
    locationB_skipped = updaterB.skipped_files

    locA_not_in_locB: dict[str, list[FileInformationPersistent]]
    locA_in_locB: dict[str, list[FileInformationPersistent]]
    locA_not_in_locB, locA_in_locB = diff_locations(
        locationA_path=locationA_DBs.source_path,
        locationA_info=locationA_info,
        locationB_path=locationB_DBs.source_path,
        locationB_info=locationB_info,
        enforce_rel_path_match=args.relpath_match,
    )

    locationA_skipped_item: tuple[FileInformationPersistent, str]
    for locationA_skipped_item in locationA_skipped:
        logging.warning(
            f"Skipped: {locationA_skipped_item[1]}: {locationA_skipped_item[0].path}"
        )
    locationB_skipped_item: tuple[FileInformationPersistent, str]
    for locationB_skipped_item in locationB_skipped:
        logging.warning(
            f"Skipped: {locationB_skipped_item[1]}: {locationB_skipped_item[0].path}"
        )

    try:
        if post_diff_command is not None:
            locA_in_locB_flattened = sorted(
                [file_info for v in locA_in_locB.values() for file_info in v],
                key=lambda x: x.path,
            )
            post_diff_command.file_info_to_affect = locA_in_locB_flattened
            post_diff_command.perform_command()

            if not args.whatif:
                # After performing the command, update the DBs.
                # Use CHANGE_DETECTION_TYPE_DATESIZE regardless of user
                # choice because this update is merely to filter out
                # what no longer exists from per-dir .json DB files.
                logging.info(f"Starting post-command location A update...")
                post_command_updaterA = locationA_DBs.update(
                    change_detection_type=CHANGE_DETECTION_TYPE_DATESIZE,
                    update_stale=args.update_stale,
                    whatif=args.whatif,
                )
                if len(post_command_updaterA.skipped_files) > 0:
                    logging.warning(
                        f"{'Total Location A post-command skipped files ':.<65}"
                        f" {len(post_command_updaterA.skipped_files)}"
                    )
    except Exception as ex:
        logging.info("")
        logging.error(
            f"ERROR: The post-diff command failed: {os.linesep}{exc_to_string_with_newlines(ex)}"
        )
        logging.info("")
    finally:
        if len(updaterA.sneaky_corruption_potentials) > 0:
            logging.info(f"=" * 65)
            logging.info(f"Potential sneaky corruption Location A: {locationA}")
            for scp in updaterA.sneaky_corruption_potentials:
                logging.info(f"        path={scp.file_info.path}")
                logging.info(f"        old_size={scp.old_size_in_bytes}")
                logging.info(f"        cur_size={scp.cur_size_in_bytes}")
                logging.info(f"        old_time={scp.old_modified_time}")
                logging.info(f"        cur_time={scp.cur_modified_time}")
                logging.info(f"        old_digest={scp.old_digest}")
                logging.info(f"        cur_digest={scp.cur_digest}")
                logging.info(f"-" * 65)
            logging.info(
                f"    Total potential sneaky corruption Location A: "
                f"{len(updaterA.sneaky_corruption_potentials)}"
            )
            logging.info(f"=" * 65)
        if len(updaterB.sneaky_corruption_potentials) > 0:
            logging.info(f"=" * 65)
            logging.info(f"Potential sneaky corruption Location B: {locationB}")
            for scp in updaterB.sneaky_corruption_potentials:
                logging.info(f"        path={scp.file_info.path}")
                logging.info(f"        old_size={scp.old_size_in_bytes}")
                logging.info(f"        cur_size={scp.cur_size_in_bytes}")
                logging.info(f"        old_time={scp.old_modified_time}")
                logging.info(f"        cur_time={scp.cur_modified_time}")
                logging.info(f"        old_digest={scp.old_digest}")
                logging.info(f"        cur_digest={scp.cur_digest}")
                logging.info(f"-" * 65)
            logging.info(
                f"{'Total potential sneaky corruption Location B:':.<65} "
                f"{len(updaterB.sneaky_corruption_potentials)} (see details above)"
            )
            logging.info(f"=" * 65)
        logging.info(f"{'Location A ':.<65} {locationA}")
        logging.info(f"{'Location B ':.<65} {locationB}")
        logging.info(f"{'Total Location A unique files ':.<65} {len(locationA_info)}")
        logging.info(
            f"{'Total Location A skipped files ':.<65} {len(locationA_skipped)}"
        )
        logging.info(f"{'Total Location B unique files ':.<65} {len(locationB_info)}")
        logging.info(
            f"{'Total Location B skipped files ':.<65} {len(locationB_skipped)}"
        )
        logging.info(
            f"{'Total Location A unique files also in Location B ':.<65} "
            f"{len(locA_in_locB)}"
        )
        logging.info(
            f"{'Total Location A unique files not found in Location B ':.<65} "
            f"{len(locA_not_in_locB)}"
        )
        if post_diff_command is not None:
            logging.info(f"Summary '{command_line_action_str}'...")
            whatif_str = " (--whatif)" if post_diff_command.whatif else " "
            past_tense_verb_whatif = f"{past_tense_verb}{whatif_str}"
            logging.info(
                f"{'Total Location A unique files ' + past_tense_verb_whatif:.<65} "
                f"{post_diff_command.unique_files_affected}"
            )
            logging.info(
                f"{'Total Location A physical files ' + past_tense_verb_whatif:.<65} "
                f"{post_diff_command.physical_files_affected}"
            )
            if locationA_DBs.has_per_file_persistence:
                logging.info(
                    f"{'Total Location A config files ' + past_tense_verb_whatif:.<65} "
                    f"{post_diff_command.config_files_affected}"
                )
                logging.info(
                    f"{'Total Location A config files not ' + past_tense_verb_whatif:.<65} "
                    f"{post_diff_command.config_files_total - post_diff_command.config_files_affected}"
                )
            logging.info(
                f"{'Total Location A affected directories ':.<65} "
                f"{len(post_diff_command.directories_affected)}"
            )
            logging.info(
                f"{'Total Location A affected directories emptied/removed ':.<65} "
                f"{post_diff_command.directories_removed}"
            )
