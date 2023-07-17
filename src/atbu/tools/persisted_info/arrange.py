# Copyright 2022, 2023 Ashley R. Thomas
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
r"""Persistent file information arranging a target using a template.
"""

import json
import logging
import os
from dataclasses import field


from ..backup.exception import *
from ..backup.constants import ATBU_PERSISTENT_INFO_EXTENSION
from ..backup.global_hasher import GlobalHasherDefinitions
from .file_info import (
    FileInformationPersistent,
    is_file_info_list_bad_state,
)
from .database import (
    FileInformationDatabaseCollection,
    extract_location_info,
    flatten_location_info_to_path_sorted_list,
    rel_path,
)


@dataclass
class _ArrangeOperationInfo:
    template_fi: FileInformationPersistent
    target_source_fi: FileInformationPersistent
    target_source_full_path: str
    target_dest_rel_path: str
    target_dest_full_path: str


@dataclass
class _FileInfoRelPathInfo:

    fi: FileInformationPersistent
    rel_path: str
    rel_path_nc: str = field(init=False)

    def __post_init__(self):
        self.rel_path_nc = os.path.normcase(self.rel_path)


@dataclass
class _ArrangeUndoInfo:

    source_full_path: str
    dest_full_path: str
    is_move_successful: bool
    error_msg: str

    def to_serialization_dict(self) -> dict:
        d = {
            "_type": "_ArrangeUndoInfo",
            "source_full_path": self.source_full_path,
            "dest_full_path": self.dest_full_path,
            "is_move_successful": self.is_move_successful,
            "error_msg": self.error_msg,
        }
        return d

    @staticmethod
    def get_json_encoder() -> json.JSONEncoder:
        class ArrangeUndoInfoEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, _ArrangeUndoInfo):
                    return o.to_serialization_dict()
                return json.JSONEncoder.default(self, o)
        return ArrangeUndoInfoEncoder


def _build_arrange_operation_list(
    template_root: str,
    template_info: dict[str, list[FileInformationPersistent]],
    target_source_root: str,
    target_source_info: dict[str, list[FileInformationPersistent]],
    target_dest_root: str,
) -> tuple[int, int, int, list[_ArrangeOperationInfo]]:
    primary_hasher_name = GlobalHasherDefinitions().get_primary_hashing_algo_name()

    target_source_fi_list = flatten_location_info_to_path_sorted_list(
        location_info=target_source_info,
    )
    arrange_oper_info_list: list[_ArrangeOperationInfo] = []
    template_match_count = 0
    template_no_match_count = 0
    template_match_exhausted_count = 0
    
    for targ_src_fi in target_source_fi_list:

        # Find template match.
        template_fi_list = template_info.get(targ_src_fi.primary_digest)
        if template_fi_list is None:
            template_no_match_count += 1
            logging.info(
                f"Template match not found for target source: "
                f"{primary_hasher_name}: "
                f"digest={targ_src_fi.primary_digest} "
                f"file_info[0]={targ_src_fi.path}"
            )
            continue

        if len(template_fi_list) == 0:
            template_match_exhausted_count += 1
            logging.warning(
                f"WARNING: Template match found but has been exhausted by other arrange operations: "
                f"{primary_hasher_name}: "
                f"digest={targ_src_fi.primary_digest} "
                f"file_info[0]={targ_src_fi.path}"
            )
            continue

        # Sanity checks:

        if is_file_info_list_bad_state(primary_hasher_name, template_fi_list):
            message = (
                f"ERROR: Template root file_info list bad state causes "
                f"target source file_info not to be arranged."
            )
            logging.error(message)
            raise InvalidStateError(message)

        if template_fi_list[0].primary_digest != targ_src_fi.primary_digest:
            message = (
                f"ERROR: Target source and template root digests do not match "
                f"when expected: {primary_hasher_name}: "
                f"target={targ_src_fi.primary_digest} "
                f"template={template_fi_list[0].primary_digest} "
                f"target_path={targ_src_fi.path} "
                f"template_path={template_fi_list[0].path}"
            )
            logging.error(message)
            raise InvalidStateError(message)

        template_match_count += 1

        logging.debug(
            f"Target source and template root digests match: "
            f"target={targ_src_fi.primary_digest} "
            f"template={template_fi_list[0].primary_digest} "
            f"target_path={targ_src_fi.path} "
            f"template_path={template_fi_list[0].path}"
        )

        template_fi_list.sort(key=lambda fi: fi.nc_path)

        # Determine relative path for target source.
        targ_src_rel_path = rel_path(
            top_level_dir=target_source_root,
            path=targ_src_fi.path,
        )
        targ_src_rel_path_nc = os.path.normcase(targ_src_rel_path)

        # Build relative path info list for all template candidates.
        template_rpi_list: list[_FileInfoRelPathInfo] = []
        for template_fi in template_fi_list:
            template_rpi_list.append(
                _FileInfoRelPathInfo(
                    fi=template_fi,
                    rel_path = rel_path(
                        top_level_dir=template_root,
                        path=template_fi.path,
                    ),
                )
            )

        # Find closest equal/greater lexicographic match.
        template_rpi_found = template_rpi_list[0]
        if len(template_rpi_list) > 1:
            for idx, template_rpi in enumerate(template_rpi_list):
                if targ_src_rel_path_nc >= template_rpi.rel_path_nc:
                    template_rpi_found = template_rpi
                    if targ_src_rel_path_nc > template_rpi.rel_path_nc and idx > 0:
                        template_rpi_found = template_rpi_list[idx - 1]
                    break

        # Mark target source for move to target dest using discovered template rel path.
        arrange_info = _ArrangeOperationInfo(
            template_fi=template_rpi_found.fi,
            target_source_fi=targ_src_fi,
            target_source_full_path=targ_src_fi.path,
            target_dest_rel_path=template_rpi_found.rel_path,
            target_dest_full_path=os.path.join(target_dest_root, template_rpi_found.rel_path),
        )
        arrange_oper_info_list.append(arrange_info)

        logging.debug(
            f"Arrange operation added to list: "
            f"{primary_hasher_name}: "
            f"{arrange_info.target_source_fi.primary_digest}: "
            f"{arrange_info.target_source_full_path} --> "
            f"{arrange_info.target_dest_full_path}"
        )

        if targ_src_fi.info_data_file_exists():
            # Add operation for sidecar .atbu file.
            template_info_data_rel_path = rel_path(
                top_level_dir=template_root,
                path=template_rpi_found.fi.info_data_file_path,
            )
            arrange_info = _ArrangeOperationInfo(
                template_fi=template_rpi_found.fi,
                target_source_fi=targ_src_fi,
                target_source_full_path=targ_src_fi.info_data_file_path,
                target_dest_rel_path=template_info_data_rel_path,
                target_dest_full_path=os.path.join(target_dest_root, template_info_data_rel_path),
            )
            arrange_oper_info_list.append(arrange_info)
            logging.debug(
                f"Arrange operation added to list: "
                f"{primary_hasher_name}: "
                f"{arrange_info.target_source_fi.primary_digest}: "
                f"{arrange_info.target_source_full_path} --> "
                f"{arrange_info.target_dest_full_path}"
            )

        # Remove selected template file info from candidates.
        template_fi_list.remove(template_rpi_found.fi)

    return (
        template_match_count,
        template_no_match_count,
        template_match_exhausted_count,
        arrange_oper_info_list
    )

def arrange_target(
    template_root: str,
    template_info: dict[str, list[FileInformationPersistent]],
    target_source_root: str,
    target_source_info: dict[str, list[FileInformationPersistent]],
    target_dest_root: str,
    undo_file_path: str,
    is_dryrun: bool,
):
    undofile = None
    arrange_undo_info: list[_ArrangeUndoInfo] = []
    successful_move_count = 0
    failed_move_count = 0
    target_dest_file_exists_count = 0
    target_source_file_count = sum(
        [(2 if fi.info_data_file_exists() else 1) for _, l in target_source_info.items() for fi in l]
    )
    try:
        # Ensure undo file can be created, readied for writing after completing arrange operations.
        if undo_file_path is not None:
            undofile = open(
                file=undo_file_path,
                 mode="w",
                 encoding="utf-8")
            logging.info(f"Undo file opened: {undo_file_path}")
        else:
            logging.info(f"Undo file will not be used.")

        (
            template_match_count,
            template_no_match_count,
            template_match_exhausted_count,
            arrange_oper_info_list,
        ) = _build_arrange_operation_list(
            template_root=template_root,
            template_info=template_info,
            target_source_root=target_source_root,
            target_source_info=target_source_info,
            target_dest_root=target_dest_root,
        )

        if len(arrange_oper_info_list) == 0:
            logging.info(
                f"No arrangement operations could be determined. Nothing to do."
            )
            return

        logging.info(
            f"Discovered {len(arrange_oper_info_list)} move target source to dest operations."
        )

        for arrange_oper_info in arrange_oper_info_list:
            try:
                if os.path.exists(arrange_oper_info.target_dest_full_path):
                    # While os.renames will throw the same exception on destination file already
                    # existing, it is exlicity thrown here to simply avoid the call to os.renames.
                    raise FileExistsError(
                        f"ERROR: The destination file already exists: "
                        f"{arrange_oper_info.target_dest_full_path}"
                    )
                if not is_dryrun:
                    os.renames(
                        old=arrange_oper_info.target_source_full_path,
                        new=arrange_oper_info.target_dest_full_path,
                    )
                successful_move_count += 1
                arrange_undo_info.append(
                    _ArrangeUndoInfo(
                        source_full_path=arrange_oper_info.target_source_fi.path,
                        dest_full_path=arrange_oper_info.target_dest_full_path,
                        is_move_successful=True,
                        error_msg=None if not is_dryrun else "<dryrun>",
                    )
                )
                logging.info(
                    f"Move successful{' (dry run)' if is_dryrun else ''}: "
                    f"{arrange_oper_info.target_source_fi.path}"
                    f" --> "
                    f"{arrange_oper_info.target_dest_full_path}"
                )
            except OSError as ex:
                failed_move_count += 1
                if isinstance(ex, FileExistsError):
                    target_dest_file_exists_count += 1
                error_message = (
                    f"Move failed{' (dry run)' if is_dryrun else ''}: "
                    f"{arrange_oper_info.target_source_fi.path}"
                    f" --> "
                    f"{arrange_oper_info.target_dest_full_path} "
                    f"{exc_to_string(ex)}"
                )
                logging.error(error_message)
                arrange_undo_info.append(
                    _ArrangeUndoInfo(
                        source_full_path=arrange_oper_info.target_source_fi.path,
                        dest_full_path=arrange_oper_info.target_dest_full_path,
                        is_move_successful=False,
                        error_msg=error_message,
                    )
                )
    except Exception as ex:
        arrange_undo_info.append(
            _ArrangeUndoInfo(
                source_full_path="<uncaught_exception>",
                dest_full_path="<uncaught_exception>",
                is_move_successful=False,
                error_msg=(
                    f"Arrange processing ended abruptly, undo information may be incomplete "
                    f"{' (dry run)' if is_dryrun else ''}: "
                    f"{exc_to_string(ex)}"
                )
            )
        )
        raise
    finally:
        if undofile is not None:
            logging.info(
                f"Writing"
                f"{' (dry run) ' if is_dryrun else ' '}"
                f"undo information to undo file '{undo_file_path}' ...")
            undofile.write(
                json.dumps(
                    obj=arrange_undo_info,
                    indent=4,
                    cls=_ArrangeUndoInfo.get_json_encoder(),
                )
            )
            undofile.close()

    dryrun_str = "(--whatif) " if is_dryrun else " "

    logging.info(
        f"{'Total target source files ' + dryrun_str:.<65} "
        f"{target_source_file_count} (includes any sidecar {ATBU_PERSISTENT_INFO_EXTENSION} files)"
    )
    logging.info(
        f"{'Total arrange operations ' + dryrun_str:.<65} "
        f"{len(arrange_oper_info_list)} (includes any sidecar {ATBU_PERSISTENT_INFO_EXTENSION} files)"
    )
    logging.info(
        f"{'Successful move operations ' + dryrun_str:.<65} "
        f"{successful_move_count} (includes any sidecar {ATBU_PERSISTENT_INFO_EXTENSION} files)"
    )
    logging.info(
        f"{'Failed move operations ' + dryrun_str:.<65} "
        f"{failed_move_count}"
    )
    logging.info(
        f"{'Failures due to destination already exists ' + dryrun_str:.<65} "
        f"{target_dest_file_exists_count}"
    )
    logging.info(
        f"{'Total target source files not moved ' + dryrun_str:.<65} "
        f"{target_source_file_count - successful_move_count} (includes any sidecar {ATBU_PERSISTENT_INFO_EXTENSION} files)"
    )
    logging.info(
        f"{'Total template digest matches ' + dryrun_str:.<65} "
        f"{template_match_count} (1 count for each file and accompanying sidecar file)"
    )
    logging.info(
        f"{'Total template digest matches not found ' + dryrun_str:.<65} "
        f"{template_no_match_count}"
    )
    logging.info(
        f"{'Total template digest matches exhausted ' + dryrun_str:.<65} "
        f"{template_match_exhausted_count}"
    )
    logging.info(
        f"{'Undo file ' + dryrun_str:.<65} "
        f"{'<none>' if undo_file_path is None else undo_file_path}"
    )

    logging.info(
        f"Arrange complete."
    )

def handle_arrange(args):
    if not args.no_undo and args.undofile is None:
        raise InvalidCommandLineArgument(
            f"Either --no-undofile or --undofile <path> must be specified."
        )
    locations = extract_location_info(
        args.locations,
        min_required=3,
        max_allowed=3,
        must_exist=False
    )
    loc_template_root = locations[0][0]
    loc_template_root_per_type = locations[0][1]
    if not os.path.exists(loc_template_root):
        raise InvalidCommandLineArgument(
            f"The template root path does not exist: {loc_template_root}"
        )

    loc_target_source_root = locations[1][0]
    loc_target_source_root_per_type = locations[1][1]
    if not os.path.exists(loc_target_source_root):
        raise InvalidCommandLineArgument(
            f"The target source root does not exist: {loc_target_source_root}"
        )

    loc_target_dest_root = locations[2][0]
    loc_target_dest_root_per_type = locations[2][1]

    sr_target_source = os.stat(loc_target_source_root)
    if not os.path.exists(loc_target_dest_root):
        os.makedirs(loc_target_dest_root, exist_ok=True)
    sr_target_dest = os.stat(loc_target_dest_root)
    if sr_target_source.st_dev != sr_target_dest.st_dev:
        raise ValueError(
            f"The target source root and destination must be located on the same drive. "
            f"target source "
            f"st_dev=0x{hex(sr_target_source.st_dev)} "
            f"dest st_dev=0x{hex(sr_target_dest.st_dev)}"
        )

    loc_template_DBs = FileInformationDatabaseCollection(
        source_path=loc_template_root, persist_types=loc_template_root_per_type
    )

    loc_target_source_DBs = FileInformationDatabaseCollection(
        source_path=loc_target_source_root, persist_types=loc_target_source_root_per_type
    )

    logging.info(f"{'Template root directory ':.<45} {loc_template_root}")
    logging.info(f"{'Template root persist type ':.<45} {loc_template_root_per_type}")
    logging.info(f"{'Target source root directory ':.<45} {loc_target_source_root}")
    logging.info(f"{'Target source root persist type ':.<45} {loc_target_source_root_per_type}")
    logging.info(f"{'Target source destination directory ':.<45} {loc_target_dest_root}")
    logging.info(f"{'Target source destination persist type ':.<45} {loc_target_dest_root_per_type}")

    logging.info(f"-" * 65)
    logging.info(f"Searching template root directory: {loc_template_root}")
    updaterA = loc_template_DBs.update(
        change_detection_type=args.change_detection_type,
        update_stale=args.update_stale,
        whatif=args.whatif,
    )
    loc_template_info = loc_template_DBs.get_dict_digest_to_fi()
    loc_template_info_skipped = updaterA.skipped_files

    logging.info(f"-" * 65)
    logging.info(f"Searching target source directory: {loc_target_source_root}")
    updaterB = loc_target_source_DBs.update(
        change_detection_type=args.change_detection_type,
        update_stale=args.update_stale,
        whatif=args.whatif,
    )
    loc_target_source_info = loc_target_source_DBs.get_dict_digest_to_fi()
    loc_target_source_skipped = updaterB.skipped_files

    arrange_target(
        template_root=loc_template_DBs.source_path,
        template_info=loc_template_info,
        target_source_root=loc_target_source_DBs.source_path,
        target_source_info=loc_target_source_info,
        target_dest_root=loc_target_dest_root,
        undo_file_path=args.undofile,
        is_dryrun=args.whatif,
    )
