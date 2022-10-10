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
r"""Classes/functions related to backup-related selections.
"""

from dataclasses import dataclass, field
from fnmatch import fnmatchcase, fnmatch
import logging
import os
from pathlib import Path
import platform
import re

from atbu.common.exception import (
    InvalidStateError,
)
from atbu.common.util_helpers import (
    iwalk_fnmatch,
)
from .exception import *
from .constants import *
from .config import (
    AtbuConfig,
    is_existing_filesystem_storage_path,
)
from .backup_core import (
    StorageDefinition,
    SpecificBackupInformation,
    BackupInformationDatabase,
)
from .backup_core import BackupFileInformation

DEFAULT_PLATFORM_EXCLUDE = {
    "Windows": {
        re.compile(os.path.normcase(r"^[a-zA-Z]:\\System Volume Information" "\\\\")),
        re.compile(os.path.normcase(r"^[a-zA-Z]:\\$Recycle.Bin" "\\\\")),
    }
}

SELECTION_SCOPE_BACKUP = "backup"
SELECTION_SCOPE_FILE = "files"
SELECTION_SCOPE_ALL = "all"
SELECTION_SCOPES = [SELECTION_SCOPE_ALL, SELECTION_SCOPE_BACKUP, SELECTION_SCOPE_FILE]

SELECTION_BACKUP_LAST = "last"


class SelectionPattern:
    def __init__(self, raw_command_line_specifier: str):
        parts = raw_command_line_specifier.split(":", maxsplit=1)
        scope = None
        pattern = parts
        if len(parts) > 1:
            scope = parts[0]
            pattern = parts[1]
        if scope not in SELECTION_SCOPES:
            raise BackupSelectionError(
                f"The scope '{scope}' is invalid, must be one of {SELECTION_SCOPES}."
            )
        self.scope = scope
        self.original_pattern = pattern
        self.normcase_pattern = os.path.normcase(pattern)

    @staticmethod
    def is_valid_selection_pattern(arg_to_test: str):
        parts = arg_to_test.split(":", maxsplit=1)
        return len(parts) == 2 and parts[0] in SELECTION_SCOPES


@dataclass
class StorageSelectionInfo:
    location: str
    location_derivation_source_arg: str
    storage_def_name: str
    storage_def: dict
    backup_info_dir: Path
    selection_patterns: list[SelectionPattern]


@dataclass
class SpecificBackupSelection:
    storage_def_name: str
    specific_backup_name: str
    specific_backup_info: SpecificBackupInformation
    storage_def: StorageDefinition
    backup_info_dir: Path
    backup_history: BackupInformationDatabase
    sel_info: StorageSelectionInfo
    selected_fi: dict[str, BackupFileInformation] = field(default_factory=dict)


def parse_storage_def_specifiers_patterns(
    raw_arguments: list[str], resolve_storage_def_secrets: bool = False
) -> list[StorageSelectionInfo]:
    sel_info_dict: dict[str, StorageSelectionInfo] = {}
    result: list[StorageSelectionInfo] = []
    cur_storage_selections: list[StorageSelectionInfo] = None
    for raw_arg in raw_arguments:
        if SelectionPattern.is_valid_selection_pattern(arg_to_test=raw_arg):
            #
            # Valid selection pattern, apply it to cur_storage_selections.
            #
            if not cur_storage_selections:
                raise StorageDefinitionNotSpecifiedError(
                    f"No storage selection to apply pattern '{raw_arg}' to."
                )
            for (
                cur_storage_selection
            ) in cur_storage_selections:  # pylint: disable=not-an-iterable
                cur_storage_selection.selection_patterns.append(
                    SelectionPattern(raw_command_line_specifier=raw_arg)
                )
            continue

        storage_pattern = raw_arg.lower()
        raw_arg_split = raw_arg.split(":", maxsplit=1)
        if (
            raw_arg_split[0]
            == CONFIG_SECTION_STORAGE_DEFINITION_SPECIFIER_PREFIX[
                : len(raw_arg_split[0])
            ]
        ):
            storage_pattern = raw_arg_split[1]

        storage_specifiers = [
            f"{CONFIG_SECTION_STORAGE_DEFINITION_SPECIFIER_PREFIX}:{n}"
            for n in AtbuConfig.get_user_storage_def_names(fnmatch_pattern=storage_pattern)
        ]

        if not storage_specifiers:
            if not is_existing_filesystem_storage_path(storage_location=raw_arg):
                raise StorageDefinitionNotFoundError(
                    f"The specifier '{raw_arg}' did not "
                    f"yield any storage definitions or "
                    f"filesystem backups."
                )
            # The raw_arg is a directory, set it to the specifier to allow following
            # to try to find a configuration.
            storage_specifiers = [raw_arg]

        #
        # Fall through, raw_arg is not a selection pattern,
        # should be storage definition specifier...
        #

        # Per-iteration storage selections.
        cur_storage_selections: list[StorageSelectionInfo] = []

        # For each specifier, find a storage, add to cur_storage_selections
        # for extracting any patterns.
        for storage_specifier in storage_specifiers:
            atbu_cfg_to_use: AtbuConfig
            (
                atbu_cfg_to_use,
                storage_def_name,
                storage_def_dict,
            ) = AtbuConfig.resolve_storage_location(
                storage_location=storage_specifier,
                resolve_storage_def_secrets=resolve_storage_def_secrets,
                create_if_not_exist=False,
            )
            if not atbu_cfg_to_use or not storage_def_name or not storage_def_dict:
                raise StorageDefinitionNotFoundError(
                    f"WARNING: Storage definition for '{storage_specifier}' not found, skipping."
                )

            storage_sel_info: StorageSelectionInfo = sel_info_dict.get(storage_def_name)
            if not storage_sel_info:
                storage_def = StorageDefinition.storage_def_from_dict(
                    storage_def_name=storage_def_name, storage_def_dict=storage_def_dict
                )

                storage_sel_info = StorageSelectionInfo(
                    location=storage_specifier,
                    location_derivation_source_arg=raw_arg,
                    storage_def_name=storage_def_name,
                    storage_def=storage_def,
                    backup_info_dir=atbu_cfg_to_use.get_backup_info_dir(),
                    selection_patterns=[],
                )
                # Add to ordered list of StorageSelectionInfo instance results.
                result.append(storage_sel_info)

            # Add to the StorageSelectionInfo instances related to
            # the upcoming SelectionPattern instances (further above).
            # A single StorageSelectionInfo instance could be added to
            # cur_storage_selections twice if perhaps the same storage def
            # was specified twice in the overall options.
            cur_storage_selections.append(storage_sel_info)

    # Resulting list should only have any given storage defintion once,
    # with any patterns extracted per above.
    return result


def get_selections_from_file_info_dict(
    sel_pat: SelectionPattern, nc_path_to_fi_dict: dict[str, BackupFileInformation]
) -> list[BackupFileInformation]:
    r: list[BackupFileInformation] = []
    # Check each normcase'ed path against the glob-like pattern.
    for normcase_path, fi in nc_path_to_fi_dict.items():
        # path and pattern are already normcase so using fnmatchcase is fine.
        if not fnmatchcase(normcase_path, sel_pat.normcase_pattern):
            continue
        # Sanity check state, ensure file is resolved with backing_fi.
        if fi.is_unchanged_since_last and not fi.backing_fi:
            # If unchanged file has unresolved backing_fi, fail.
            raise BackingFileInformationNotFound(
                f"An unchanged since last file has no backing file information: "
                f"fi={fi.path}"
            )
        r.append(fi)
    return r


def get_specific_backup_selections(
    sel_info_list: list[StorageSelectionInfo],
) -> list[list[SpecificBackupSelection]]:
    result: list[list[SpecificBackupSelection]] = []
    history_dict: dict[str, BackupInformationDatabase] = {}
    # For each storage definition being filtered...
    for si in sel_info_list:
        if not si.selection_patterns:
            # No filters, skip.
            # TODO: Should this default to none or * all ? (TBD)
            # For now, create a dummy SpecificBackupSelection to allow
            # querying of storage defintions via this code path.
            specific_backup_sel = SpecificBackupSelection(
                storage_def_name=si.storage_def_name,
                specific_backup_name=None,
                specific_backup_info=None,
                storage_def=si.storage_def,
                backup_info_dir=si.backup_info_dir,
                backup_history=None,
                sel_info=si,
            )
            result.append([specific_backup_sel])
            continue
        # For the si storage definition, extract all selected specific backup instances.
        specific_backup_selections: list[SpecificBackupSelection] = []
        for sp in si.selection_patterns:
            if sp.scope not in [SELECTION_SCOPE_BACKUP]:
                continue
            #
            # Share the same storage definition history with SpecificBackupSelection
            # instances of the same storage definition as follows.
            #
            history_key = f"{si.storage_def_name}:{si.backup_info_dir}"
            backup_history = history_dict.get(history_key)
            if not backup_history:
                backup_history = BackupInformationDatabase.create_from_file(
                    backup_base_name=si.storage_def_name,
                    backup_info_dir=si.backup_info_dir,
                )
            # For each specific backup, from newest to oldest...
            for sbi in backup_history.get_specific_backups():
                # If user specified SELECTION_BACKUP_LAST, always match and
                # select the first most recent specific backup.
                # If the user specified something actual fnmatch criteria and
                # it matches, select the backup.
                # All other cases skip this specific backup.
                if (
                    not sp.original_pattern.lower() == SELECTION_BACKUP_LAST
                    and not fnmatch(sbi.specific_backup_name, sp.normcase_pattern)
                ):
                    continue
                # Match, backup selections.
                specific_backup_sel = SpecificBackupSelection(
                    storage_def_name=si.storage_def_name,
                    specific_backup_name=sbi.specific_backup_name,
                    specific_backup_info=sbi,
                    storage_def=si.storage_def,
                    backup_info_dir=si.backup_info_dir,
                    backup_history=backup_history,
                    sel_info=si,
                )
                specific_backup_selections.append(specific_backup_sel)
                if sp.original_pattern.lower() == SELECTION_BACKUP_LAST:
                    # With selector SELECTION_BACKUP_LAST skip backups
                    # older than the last one (the most recent one).
                    break
        for sp in si.selection_patterns:
            if sp.scope != SELECTION_SCOPE_FILE:
                continue
            specific_backup_sel: SpecificBackupSelection
            # For each selected specific backup, from newest to oldest...
            for specific_backup_sel in specific_backup_selections:
                # Place all specific backup file info into a dict keyed w/normcase path.
                sb_nc_path_to_fi_dict: dict[str, BackupFileInformation] = {}
                for sb_fi in specific_backup_sel.specific_backup_info.all_file_info:
                    sb_nc_path_to_fi_dict[sb_fi.nc_path_without_root] = sb_fi
                # Determine which specific backup file info matches the file selection pattern.
                list_sel_fi = get_selections_from_file_info_dict(
                    sel_pat=sp, nc_path_to_fi_dict=sb_nc_path_to_fi_dict
                )
                # For each matching specific backup file info, if it has not already
                # matched the same path with a newer file info, add it to the selection.
                # There should not be duplicate paths per specific backup.
                # Callers will use functions like get_all_specific_backup_file_info to
                # reduce all selections across all specific backups to a single of duplicates
                # where applicable. That is not what the following does. The following is a
                # sanity check.
                for sel_fi in list_sel_fi:
                    if not specific_backup_sel.selected_fi.get(
                        sel_fi.nc_path_without_root
                    ):
                        specific_backup_sel.selected_fi[
                            sel_fi.nc_path_without_root
                        ] = sel_fi
        if specific_backup_selections:
            result.append(specific_backup_selections)
    return result


def verify_specific_backup_selection_list(sbs_list: list[SpecificBackupSelection]):
    storage_def_name = None
    backup_info_dir = None
    for sbs in sbs_list:
        if not storage_def_name:
            storage_def_name = sbs.storage_def_name
            backup_info_dir = sbs.backup_info_dir
        elif (
            storage_def_name != sbs.storage_def_name
            or backup_info_dir != sbs.backup_info_dir
        ):
            raise InvalidStateError(
                f"All SpecificBackupSelection instances in the list "
                f"must target the same storage definition."
            )


def get_all_specific_backup_file_info(
    sbs_list: list[SpecificBackupSelection],
) -> list[BackupFileInformation]:
    sb_nc_path_to_fi_dict: dict[str, BackupFileInformation] = {}
    # The sbs_list contains SpecificBackupSelection instances from
    # the most recent to oldest specific backup examined as part of
    # the selection process. For each SpecificBackupSelection instance
    # in that order...
    for sbs in sbs_list:
        # Go through the SpecificBackupSelection instance's items, if an item
        # is not in the result sb_nc_path_to_fi_dict, add it. This means
        # newest BackupFileInformation wins.
        for _, sbs_fi in sbs.selected_fi.items():
            if not sb_nc_path_to_fi_dict.get(sbs_fi.nc_path_without_root):
                sb_nc_path_to_fi_dict[sbs_fi.nc_path_without_root] = sbs_fi
    # Return a list of BackupFileInformation instances sorted by normcase path.
    # The sorting is not essential but during operations it can be nice to see
    # files processed with in an order making sense. Being nonessential, this
    # can be changed if needed.
    return sorted(
        [v for _, v in sb_nc_path_to_fi_dict.items()],
        key=lambda sb_fi: sb_fi.nc_path_without_root,
    )


def user_specifiers_to_selections(
    specifiers: list[str], no_selections_ok: bool = False
) -> list[list[SpecificBackupSelection]]:

    # Get selection information from all specifiers.
    sel_info_list = parse_storage_def_specifiers_patterns(
        raw_arguments=specifiers, resolve_storage_def_secrets=True
    )

    # Validate selection information.
    if not no_selections_ok:
        for sel_info in sel_info_list:
            if len(sel_info.selection_patterns) == 0:
                raise BackupSelectionError(
                    f"You must have at least one storage, backup, and file specifier. "
                    f"Example: storage:<storage_def_name> backup:last files:*"
                )

    # Get selections using selection information.
    sbs_list_list = get_specific_backup_selections(sel_info_list)

    if not no_selections_ok:
        # Validate selections.
        for sbs_list in sbs_list_list:
            file_info_count = 0
            for sbs in sbs_list:
                file_info_count += len(sbs.selected_fi)
            if file_info_count == 0:
                raise BackupSelectionError(
                    f"No selected files for {sbs_list[0].storage_def_name}. "
                    f"You must have at least one storage, backup, and file specifier. "
                    f"Example: storage:<storage_def_name> backup:last files:*"
                )

    # Everything seems OK, return selections to caller.
    return sbs_list_list


def get_storage_defintions_from_sbs_list_list(
    sbs_list_list: list[list[SpecificBackupSelection]],
) -> list[StorageDefinition]:
    storage_def_dict: dict[str, StorageDefinition] = {}
    for sbs_list in sbs_list_list:
        for sbs in sbs_list:
            storage_def_dict[sbs.storage_def_name] = sbs.storage_def
    storage_def_list: list[StorageDefinition] = sorted(
        storage_def_dict.values(), key=lambda sd: sd.storage_def_name
    )
    return storage_def_list


def is_system_excluded_path(path):
    platform_excludes = DEFAULT_PLATFORM_EXCLUDE.get(platform.system())
    if platform_excludes is not None:
        for pe in platform_excludes:
            if pe.match(os.path.normcase(path)):
                return True
    return False


RE_FIND_GLOB_CHARS = re.compile(r"[?\[\]*]")
PATH_SEP_CHARS = r"\/"
RE_CONTAINS_GLOB_CHARS = re.compile(".*[*?[].*")


def get_largest_path_without_wildcards(path: str):
    m = RE_FIND_GLOB_CHARS.search(path)
    if m:
        index = m.start()
        while path[index] not in PATH_SEP_CHARS:
            index -= 1
        if index >= 0:
            path = path[: index + 1]
    return path


def get_dirs_without_wildcards(locations: list[str]):
    results: list[str] = []
    for location in locations:
        location = get_largest_path_without_wildcards(location)
        results.append(os.path.abspath(location))
    return results


def ensure_glob_pattern_for_dir(dir_wc: str):
    """For a directory, if no glob pattern is present, ensure
    the glob "**" pattern is joined.
    """
    nc_dir_wc = os.path.normcase(dir_wc)
    nc_drive = os.path.splitdrive(nc_dir_wc)[0]
    if not RE_CONTAINS_GLOB_CHARS.match(dir_wc) and (
        os.path.isdir(dir_wc) or nc_dir_wc == nc_drive
    ):
        dir_wc = os.path.join(dir_wc, "**")
    return dir_wc


@dataclass
class SourceSpecifierDiscoveries:
    source_dir: str
    source_dir_wc: str
    discovered_paths: list[BackupFileInformation]


def get_local_file_information(
    src_dirs_wc: list[str], exclude_patterns: list[str]
) -> list[BackupFileInformation]:
    r"""Given locations containing one or more paths to search, return a list
    of discovered files.

    Each path in src_dirs_wc may or may not contain glob patterns. If a path in
    src_dirs_wc is a directory without a glob pattern, the '**' glob pattern
    will be appened. For example, "c:\abc" will become "c:\\abc\\**" to
    cause a recursive search of all files.

    This function will return a list of file information each of which will
    have its file_info.discovery_path set to the src_dirs_wc leading to its
    discovery.
    """

    exclude_patterns = list(map(os.path.normcase, exclude_patterns))

    def is_ignored(path):
        if is_system_excluded_path(path):
            logging.debug(f"Ignoring platform-excluded path: {path}")
            return True
        nonlocal exclude_patterns
        if len(exclude_patterns) == 0:
            return False
        path_nc = os.path.normcase(path)
        if any(map(lambda pat: fnmatchcase(name=path_nc, pat=pat), exclude_patterns)):
            logging.info(f"Ignoring user-excluded path: {path}")
            return True
        return False

    # Both src_dirs_wc and src_dirs_no_wc can be correlated by index.
    # Start by sorting caller's selections by length/normcase. Length
    # means discovery by shortest selector wins.
    src_dirs_wc.sort(key=lambda p: (len(p), os.path.normcase(p)))
    src_dirs_no_wc: list[str] = get_dirs_without_wildcards(locations=src_dirs_wc)

    # Ensure no duplicate paths in final selection.
    all_paths = set()

    # Track which src_dirs_wc selector discovered which file path.
    srcspec_to_disc: dict[str, SourceSpecifierDiscoveries] = {}

    # For each caller selection...
    for idx, src_dir_wc in enumerate(src_dirs_wc):

        # Get corresponding path without any glob patterns ("wildcards" or "wc").
        src_dir_no_wc = src_dirs_no_wc[idx]
        src_dir_no_wc_nc = os.path.normcase(src_dir_no_wc)

        # If location is either a directory or drive letter alone without
        # any glob patterns, then add glob pattern '**'.
        nc_location = os.path.normcase(src_dir_wc)
        nc_drive = os.path.splitdrive(nc_location)[0]
        if not RE_CONTAINS_GLOB_CHARS.match(src_dir_wc) and (
            os.path.isdir(src_dir_wc) or nc_location == nc_drive
        ):
            src_dir_wc = os.path.join(src_dir_wc, "**")

        # If user specified a single path/file, search dir is it's dir.
        src_dir_to_search = src_dir_no_wc
        if os.path.isfile(src_dir_no_wc) and src_dir_no_wc == src_dir_wc:
            src_dir_to_search, _ = os.path.split(src_dir_no_wc)
        # Search, removing anything already found.
        discovered = set(
            iwalk_fnmatch(
                root_no_wildcards=src_dir_to_search,
                fnmatch_pat=src_dir_wc,
            )
        ).difference(all_paths)

        # Refine further, retaining only files which are not ignored.
        discovered = [v for v in discovered if not is_ignored(v)]

        if len(discovered) == 0:
            # Nothing left, next item.
            continue

        # For the given search root folder (without glob pattern),
        # find an existing SourceSpecifierDiscoveries instance, if
        # non found, create one.
        src_spec_disc = srcspec_to_disc.get(src_dir_no_wc_nc)
        if not src_spec_disc:
            src_spec_disc = SourceSpecifierDiscoveries(
                source_dir=src_dir_no_wc, source_dir_wc=src_dir_wc, discovered_paths=[]
            )
            srcspec_to_disc[src_dir_no_wc_nc] = src_spec_disc

        # Add discovered files to instance, assocating them with
        # root path used to find the selections themselves.
        src_spec_disc.discovered_paths.extend(discovered)

        # Track files added, do not add more than once.
        all_paths.update(discovered)

    # Create results for caller by processing each SourceSpecifierDiscoveries instance.
    disc_list = sorted(
        srcspec_to_disc.values(), key=lambda d: os.path.normcase(d.source_dir)
    )
    file_info_list: list[BackupFileInformation] = []
    # For each caller-specified search path...
    for idx, disc in enumerate(disc_list):
        # For each file discovered by caller's search path...
        for p in disc.discovered_paths:
            if not os.path.normcase(p).startswith(os.path.normcase(disc.source_dir)):
                raise InvalidStateError(
                    f"Expected file to have path starting with discovery source: "
                    f"source_dir_wc={disc.source_dir_wc} "
                    f"file_info.path={p.path}"
                )
            # Create the result list with file info
            # indicating discovery source dir.
            file_info_list.append(
                BackupFileInformation(path=p, discovery_path=disc.source_dir)
            )
    return file_info_list
