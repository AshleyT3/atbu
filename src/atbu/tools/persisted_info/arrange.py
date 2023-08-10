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
r"""Persistent file information 'arrange' command handling. Arrange a
drive's target by using a source drive's template to determine where to
move files from the target directory to a new (destiation) directory on
the same target drive.
"""

import os
import logging
from collections import deque
from dataclasses import field
from enum import Enum, auto
import json


from atbu.common.util_helpers import (
    rel_path,
    get_subdir_distance,
)
from atbu.common.multi_json_enc_dec import (
    create_dataclass_json_encoder,
    create_dataclass_json_decoder,
)

from ..backup.exception import *
from ..backup.constants import ATBU_PERSISTENT_INFO_EXTENSION
from ..backup.global_hasher import GlobalHasherDefinitions
from .file_info import (
    FileInformationPersistent,
    is_file_info_list_bad_state,
)
from .database import (
    FileInformationDatabaseCollection,
    flatten_location_info_to_path_sorted_list,
)


_verbosity_level = 0


def _is_debug_logging():
    return logging.getLogger().getEffectiveLevel() >= logging.DEBUG


def _is_verbose_debug_logging():
    return _verbosity_level >= 1 and _is_debug_logging()


@dataclass
class _ArrangeOperationInfo:
    template_fi: FileInformationPersistent
    target_source_fi: FileInformationPersistent
    target_source_full_path: str
    target_dest_rel_path: str
    target_dest_full_path: str


@dataclass
class _FileInfoRelPathInfo:
    fi_list: list[FileInformationPersistent]
    fi: FileInformationPersistent


@dataclass
class _ArrangeUndoInfo:
    source_full_path: str
    dest_full_path: str
    is_move_successful: bool
    error_msg: str

    @staticmethod
    def get_json_encoder() -> json.JSONEncoder:
        return create_dataclass_json_encoder(data_cls=__class__, is_strict=True)

    @staticmethod
    def get_json_decoder() -> json.JSONDecoder:
        return create_dataclass_json_decoder(data_cls=__class__, is_strict=True)


class _PathMatchType(Enum):
    EXACT = auto()
    SAME_LEVEL = auto()
    COMMON_SUBPATH = auto()
    ANYWHERE = auto()


@dataclass
class _MatchCharacteristics:
    path_match_type: _PathMatchType
    is_date_match_required: bool
    is_basename_match_required: bool


class _ArrangeMatchFinder:
    def __init__(
        self,
        template_root: str,
        template_info: dict[str, list[FileInformationPersistent]],
        target_source_root: str,
        target_source_info: dict[str, list[FileInformationPersistent]],
        target_dest_root: str,
    ) -> None:
        self.targ_src_path_match_set: set[str] = set()
        self.targ_src_path_no_match_set: set[str] = set()
        self.targ_src_path_match_exhausted_set: set[str] = set()
        self.arrange_oper_info_list: list[_ArrangeOperationInfo] = []
        self.hasher_name = GlobalHasherDefinitions().get_primary_hashing_algo_name()
        self.template_root = template_root
        self.template_info = template_info
        self.target_source_root = target_source_root
        self._target_source_fi_deque = deque(
            flatten_location_info_to_path_sorted_list(
                location_info=target_source_info,
            )
        )
        self.target_dest_root = target_dest_root
        for _, template_fi_list in self.template_info.items():
            template_fi_list.sort(key=lambda fi: fi.nc_path)
        self._match_characteristics_list = [
            _MatchCharacteristics(
                path_match_type=_PathMatchType.EXACT,
                is_date_match_required=False,
                is_basename_match_required=True,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.SAME_LEVEL,
                is_date_match_required=True,
                is_basename_match_required=False,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.SAME_LEVEL,
                is_date_match_required=False,
                is_basename_match_required=False,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.COMMON_SUBPATH,
                is_date_match_required=True,
                is_basename_match_required=True,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.COMMON_SUBPATH,
                is_date_match_required=True,
                is_basename_match_required=False,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.COMMON_SUBPATH,
                is_date_match_required=False,
                is_basename_match_required=True,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.COMMON_SUBPATH,
                is_date_match_required=False,
                is_basename_match_required=False,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.ANYWHERE,
                is_date_match_required=True,
                is_basename_match_required=True,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.ANYWHERE,
                is_date_match_required=True,
                is_basename_match_required=False,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.ANYWHERE,
                is_date_match_required=False,
                is_basename_match_required=True,
            ),
            _MatchCharacteristics(
                path_match_type=_PathMatchType.ANYWHERE,
                is_date_match_required=False,
                is_basename_match_required=False,
            ),
        ]

    def _add_operation(
        self,
        template_rpi: _FileInfoRelPathInfo,
        targ_src_fi: FileInformationPersistent,
    ):
        # Mark target source for move to target dest using discovered template rel path.
        template_rel_path, target_dest_full_path = self._get_dest_paths(
            template_full_path=template_rpi.fi.path
        )
        arrange_info = _ArrangeOperationInfo(
            template_fi=template_rpi.fi,
            target_source_fi=targ_src_fi,
            target_source_full_path=targ_src_fi.path,
            target_dest_rel_path=template_rel_path,
            target_dest_full_path=target_dest_full_path,
        )
        self.arrange_oper_info_list.append(arrange_info)

        logging.debug(
            f"Arrange operation added to list: "
            f"{self.hasher_name}: "
            f"{arrange_info.target_source_fi.primary_digest}: "
            f"{arrange_info.target_source_full_path} --> "
            f"{arrange_info.target_dest_full_path}"
        )

        if targ_src_fi.info_data_file_exists():
            # Add operation for sidecar .atbu file.
            template_info_data_rel_path, target_dest_info_data_full_path = self._get_dest_paths(
                template_full_path=template_rpi.fi.info_data_file_path
            )
            arrange_info = _ArrangeOperationInfo(
                template_fi=template_rpi.fi,
                target_source_fi=targ_src_fi,
                target_source_full_path=targ_src_fi.info_data_file_path,
                target_dest_rel_path=template_info_data_rel_path,
                target_dest_full_path=target_dest_info_data_full_path,
            )
            self.arrange_oper_info_list.append(arrange_info)
            logging.debug(
                f"Arrange operation added to list: "
                f"{self.hasher_name}: "
                f"{arrange_info.target_source_fi.primary_digest}: "
                f"{arrange_info.target_source_full_path} --> "
                f"{arrange_info.target_dest_full_path}"
            )

    def _match_func_primitive(
        self,
        template_fi_list: list[FileInformationPersistent],
        targ_src_fi: FileInformationPersistent,
        path_match_type: _PathMatchType,
        is_date_match_required: bool,
        is_basename_match_required: bool,
    ) -> _FileInfoRelPathInfo:

        targ_src_rel_path = rel_path(
            top_level_dir=self.target_source_root,
            path=targ_src_fi.path,
        )
        targ_src_rel_path_nc = os.path.normcase(targ_src_rel_path)
        targ_src_rel_dir_nc, targ_src_basename_nc = os.path.split(targ_src_rel_path_nc)

        best_match_rpi: _FileInfoRelPathInfo = None
        best_match_subdir_distance: str = None

        for template_fi in template_fi_list:
            if template_fi.size_in_bytes != targ_src_fi.size_in_bytes:
                if _is_verbose_debug_logging():
                    logging.debug(
                        f"VETO: size mismatch: "
                        f"{template_fi.size_in_bytes} != {targ_src_fi.size_in_bytes}: "
                        f"pmt={path_match_type} "
                        f"date_req={is_date_match_required} "
                        f"basename_req={is_basename_match_required} "
                        f"dig={targ_src_fi.primary_digest} "
                        f"template={template_fi.path} source={targ_src_fi.path}"
                    )
                continue

            if is_date_match_required and (
                template_fi.modified_time_posix is None
                or template_fi.modified_time_posix != targ_src_fi.modified_time_posix
            ):
                if _is_verbose_debug_logging():
                    logging.debug(
                        f"VETO: date mismatch: "
                        f"{template_fi.modified_time_posix} != {targ_src_fi.modified_time_posix}: "
                        f"pmt={path_match_type} "
                        f"date_req={is_date_match_required} "
                        f"basename_req={is_basename_match_required} "
                        f"dig={targ_src_fi.primary_digest} "
                        f"template={template_fi.path} source={targ_src_fi.path}"
                    )
                continue

            template_fi_rel_path = self._get_template_rel_path(template_full_path=template_fi.path)
            template_fi_rel_path_nc = os.path.normcase(template_fi_rel_path)
            template_fi_rel_dir_nc, template_fi_basename_nc = os.path.split(
                template_fi_rel_path_nc
            )

            if (
                is_basename_match_required
                and targ_src_basename_nc != template_fi_basename_nc
            ):
                if _is_verbose_debug_logging():
                    logging.debug(
                        f"VETO: basename mismatch: "
                        f"'{template_fi_basename_nc}' != '{targ_src_basename_nc}': "
                        f"pmt={path_match_type} "
                        f"date_req={is_date_match_required} "
                        f"basename_req={is_basename_match_required} "
                        f"dig={targ_src_fi.primary_digest} "
                        f"template={template_fi.path} source={targ_src_fi.path}"
                    )
                continue

            if (
                path_match_type == _PathMatchType.EXACT
                and targ_src_rel_path_nc != template_fi_rel_path_nc
            ):
                if _is_verbose_debug_logging():
                    logging.debug(
                        f"VETO: not exact match: "
                        f"'{template_fi_rel_path_nc}' != '{targ_src_rel_path_nc}': "
                        f"pmt={path_match_type} "
                        f"date_req={is_date_match_required} "
                        f"basename_req={is_basename_match_required} "
                        f"dig={targ_src_fi.primary_digest} "
                        f"template={template_fi.path} source={targ_src_fi.path}"
                    )
                continue

            if (
                path_match_type == _PathMatchType.SAME_LEVEL
                and targ_src_rel_dir_nc != template_fi_rel_dir_nc
            ):
                if _is_verbose_debug_logging():
                    logging.debug(
                        f"VETO: not same level: "
                        f"'{template_fi_rel_dir_nc}' != '{targ_src_rel_dir_nc}': "
                        f"pmt={path_match_type} "
                        f"date_req={is_date_match_required} "
                        f"basename_req={is_basename_match_required} "
                        f"dig={targ_src_fi.primary_digest} "
                        f"template={template_fi.path} source={targ_src_fi.path}"
                    )
                continue

            if path_match_type == _PathMatchType.COMMON_SUBPATH:
                try:
                    common_path_nc = os.path.commonpath(
                        [targ_src_rel_dir_nc, template_fi_rel_dir_nc]
                    )
                except ValueError:
                    if _is_verbose_debug_logging():
                        logging.debug(
                            f"VETO: no common path: "
                            f"['{targ_src_rel_dir_nc}', '{template_fi_rel_dir_nc}']: "
                            f"pmt={path_match_type} "
                            f"date_req={is_date_match_required} "
                            f"basename_req={is_basename_match_required} "
                            f"dig={targ_src_fi.primary_digest} "
                            f"template={template_fi.path} source={targ_src_fi.path}"
                        )
                    continue

                # If either targ_src_rel_dir_nc or template_fi_rel_dir_nc is empty, it
                # means they are on the root of the respective tree, which is common
                # with all other paths. Ignore empty common_path_nc in that case, else veto.
                if targ_src_rel_dir_nc and template_fi_rel_dir_nc and not common_path_nc:
                    if _is_verbose_debug_logging():
                        logging.debug(
                            f"VETO: empty common path: "
                            f"['{targ_src_rel_dir_nc}', '{template_fi_rel_dir_nc}']: "
                            f"pmt={path_match_type} "
                            f"date_req={is_date_match_required} "
                            f"basename_req={is_basename_match_required} "
                            f"dig={targ_src_fi.primary_digest} "
                            f"template={template_fi.path} source={targ_src_fi.path}"
                        )
                    continue

                if (
                    len(targ_src_rel_dir_nc) <= len(template_fi_rel_dir_nc)
                    and len(common_path_nc) < len(targ_src_rel_dir_nc)
                ):
                    if _is_verbose_debug_logging():
                        logging.debug(
                            f"VETO: common path above: "
                            f"cp='{common_path_nc}' "
                            f"['{targ_src_rel_dir_nc}', '{template_fi_rel_dir_nc}']: "
                            f"pmt={path_match_type} "
                            f"date_req={is_date_match_required} "
                            f"basename_req={is_basename_match_required} "
                            f"dig={targ_src_fi.primary_digest} "
                            f"template={template_fi.path} source={targ_src_fi.path}"
                        )
                    continue

                if (
                    len(template_fi_rel_dir_nc) <= len(targ_src_rel_dir_nc)
                    and len(common_path_nc) < len(template_fi_rel_dir_nc)
                ):
                    if _is_verbose_debug_logging():
                        logging.debug(
                            f"VETO: common path above: "
                            f"cp='{common_path_nc}' "
                            f"['{targ_src_rel_dir_nc}', '{template_fi_rel_dir_nc}']: "
                            f"pmt={path_match_type} "
                            f"date_req={is_date_match_required} "
                            f"basename_req={is_basename_match_required} "
                            f"dig={targ_src_fi.primary_digest} "
                            f"template={template_fi.path} source={targ_src_fi.path}"
                        )
                    continue

                subdir_distance = get_subdir_distance(template_fi_rel_dir_nc, targ_src_rel_dir_nc)
                if best_match_rpi is not None and subdir_distance >= best_match_subdir_distance:
                    if _is_verbose_debug_logging():
                        logging.debug(
                            f"VETO: subdir distance not improved: "
                            f"subdir_dist={subdir_distance}"
                            f"pmt={path_match_type} "
                            f"date_req={is_date_match_required} "
                            f"basename_req={is_basename_match_required} "
                            f"dig={targ_src_fi.primary_digest} "
                            f"template={template_fi_rel_path} "
                            f"source={targ_src_rel_path} "
                        )
                    continue
                best_match_subdir_distance = subdir_distance

            best_match_rpi = _FileInfoRelPathInfo(
                fi_list=template_fi_list,
                fi=template_fi,
            )
            if _is_verbose_debug_logging():
                logging.debug(
                    f"CANDIDATE: "
                    f"pmt={path_match_type} "
                    f"date_req={is_date_match_required} "
                    f"basename_req={is_basename_match_required} "
                    f"dig={targ_src_fi.primary_digest} "
                    f"template={template_fi_rel_path} "
                    f"source={targ_src_rel_path} "
                )

        if best_match_rpi is not None:
            self.targ_src_path_match_set.add(targ_src_fi.path)
            logging.debug(
                f"MATCH: "
                f"pmt={path_match_type} "
                f"date_req={is_date_match_required} "
                f"f={is_basename_match_required} "
                f"dig={targ_src_fi.primary_digest} "
                f"template={template_fi_rel_path} "
                f"source={targ_src_rel_path} "
            )

        return best_match_rpi

    def _find_target_source_match(
        self,
        targ_src_fi: FileInformationPersistent,
        match_characteristics: _MatchCharacteristics,
    ) -> _FileInfoRelPathInfo:
        # Find template match.
        template_fi_list = self.template_info.get(targ_src_fi.primary_digest)
        if template_fi_list is None:
            self.targ_src_path_no_match_set.add(targ_src_fi.path)
            logging.info(
                f"Template match not found for target source: "
                f"{self.hasher_name}: "
                f"digest={targ_src_fi.primary_digest} "
                f"file_info[0]={targ_src_fi.path}"
            )
            return None

        if len(template_fi_list) == 0:
            self.targ_src_path_match_exhausted_set.add(targ_src_fi.path)
            logging.warning(
                f"Template match found but has been exhausted by other arrange operations: "
                f"{self.hasher_name}: "
                f"digest={targ_src_fi.primary_digest} "
                f"file_info[0]={targ_src_fi.path}"
            )
            return None

        # Sanity check.
        if is_file_info_list_bad_state(self.hasher_name, template_fi_list):
            message = (
                f"Template root file_info list bad state causes "
                f"target source file_info not to be arranged."
            )
            logging.error(message)
            raise InvalidStateError(message)

        # Sanity check.
        if template_fi_list[0].primary_digest != targ_src_fi.primary_digest:
            message = (
                f"Target source and template root digests do not match "
                f"when expected: {self.hasher_name}: "
                f"target={targ_src_fi.primary_digest} "
                f"template={template_fi_list[0].primary_digest} "
                f"target_path={targ_src_fi.path} "
                f"template_path={template_fi_list[0].path}"
            )
            logging.error(message)
            raise InvalidStateError(message)

        logging.debug(
            f"Target source and template root digests match: "
            f"target={targ_src_fi.primary_digest} "
            f"template={template_fi_list[0].primary_digest} "
            f"target_path={targ_src_fi.path} "
            f"template_path={template_fi_list[0].path}"
        )

        template_rpi_found = self._match_func_primitive(
            template_fi_list=template_fi_list,
            targ_src_fi=targ_src_fi,
            path_match_type=match_characteristics.path_match_type,
            is_date_match_required=match_characteristics.is_date_match_required,
            is_basename_match_required=match_characteristics.is_basename_match_required,
        )

        return template_rpi_found

    def _get_template_rel_path(self, template_full_path: str):
        return rel_path(
            top_level_dir=self.template_root,
            path=template_full_path,
        )

    def _get_dest_paths(self, template_full_path: str) -> tuple[str, str]:
        the_rel_path = self._get_template_rel_path(template_full_path)
        the_full_path = os.path.join(self.target_dest_root, the_rel_path)
        return the_rel_path, the_full_path

    def _clean_template_info(self):
        for digest, template_fi_list in self.template_info.items():
            updated_template_fi_list: list[FileInformationPersistent] = []
            for template_fi in template_fi_list:
                _, target_dest_full_path = self._get_dest_paths(template_fi.path)
                if os.path.exists(target_dest_full_path):
                    logging.warning(
                        f"Target destination already exists, ignoring template: "
                        f"template={template_fi.path} "
                        f"existing destination={target_dest_full_path} "
                        f"digest={digest}"
                    )
                    # Prune template_fi from list.
                    continue

                _, target_dest_info_data_full_path = self._get_dest_paths(
                    template_fi.info_data_file_path
                )
                if os.path.exists(target_dest_info_data_full_path):
                    logging.warning(
                        f"Target destination info file already exists, ignoring template: "
                        f"template={template_fi.info_data_file_path} "
                        f"existing destination={target_dest_info_data_full_path} "
                        f"digest={digest}"
                    )
                    # Prune template_fi from list.
                    continue

                # Move to destination possible, keep template_if.
                updated_template_fi_list.append(template_fi)
            template_fi_list[:] = updated_template_fi_list

    def find_target_all_matches(self):
        self._clean_template_info()
        for match_characteristics in self._match_characteristics_list:

            if _is_verbose_debug_logging():
                logging.debug("---")
                logging.debug(
                    f"next characteristics: "
                    f"pmt={match_characteristics.path_match_type} "
                    f"date_req={match_characteristics.is_date_match_required} "
                    f"basename_req={match_characteristics.is_basename_match_required}"
                )
                logging.debug("---")

            visited_src_fi_deque: deque[FileInformationPersistent] = deque()
            while self._target_source_fi_deque:
                targ_src_fi = self._target_source_fi_deque.popleft()

                template_rpi_found = self._find_target_source_match(
                    targ_src_fi=targ_src_fi,
                    match_characteristics=match_characteristics,
                )

                if template_rpi_found is None:
                    visited_src_fi_deque.append(targ_src_fi)
                else:
                    self._add_operation(
                        template_rpi=template_rpi_found,
                        targ_src_fi=targ_src_fi,
                    )
                    template_rpi_found.fi_list.remove(template_rpi_found.fi)

            self._target_source_fi_deque = visited_src_fi_deque


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
        [
            (2 if fi.info_data_file_exists() else 1)
            for _, l in target_source_info.items()
            for fi in l
        ]
    )
    try:
        # Ensure undo file can be created, readied for writing after completing arrange operations.
        if undo_file_path is not None:
            undofile = open(file=undo_file_path, mode="w", encoding="utf-8")
            logging.info(f"Undo file opened: {undo_file_path}")
        else:
            logging.info(f"Undo file will not be used.")

        amf = _ArrangeMatchFinder(
            template_root=template_root,
            template_info=template_info,
            target_source_root=target_source_root,
            target_source_info=target_source_info,
            target_dest_root=target_dest_root,
        )
        amf.find_target_all_matches()
        if len(amf.arrange_oper_info_list) == 0:
            logging.info(
                f"No arrangement operations could be determined. Nothing to do."
            )
            return

        logging.info(
            f"Discovered {len(amf.arrange_oper_info_list)} move target source to dest operations."
        )

        for arrange_oper_info in amf.arrange_oper_info_list:
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
                        source_full_path=arrange_oper_info.target_source_full_path,
                        dest_full_path=arrange_oper_info.target_dest_full_path,
                        is_move_successful=True,
                        error_msg=None if not is_dryrun else "<dryrun>",
                    )
                )
                logging.info(
                    f"Move successful{' (dry run)' if is_dryrun else ''}: "
                    f"{arrange_oper_info.target_source_full_path}"
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
                ),
            )
        )
        raise
    finally:
        if undofile is not None:
            logging.info(
                f"Writing"
                f"{' (dry run) ' if is_dryrun else ' '}"
                f"undo information to undo file '{undo_file_path}' ..."
            )
            undofile.write(
                json.dumps(
                    obj=arrange_undo_info,
                    indent=4,
                    cls=_ArrangeUndoInfo.get_json_encoder(),
                )
            )
            undofile.close()

    dryrun_str = "(--dryrun) " if is_dryrun else " "

    logging.info(
        f"{'Total target source files ' + dryrun_str:.<65} "
        f"{target_source_file_count} (includes any sidecar {ATBU_PERSISTENT_INFO_EXTENSION} files)"
    )
    logging.info(
        f"{'Total arrange operations ' + dryrun_str:.<65} "
        f"{len(amf.arrange_oper_info_list)} (includes any sidecar {ATBU_PERSISTENT_INFO_EXTENSION} files)"
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
        f"{'Total target to template matches ' + dryrun_str:.<65} "
        f"{len(amf.targ_src_path_match_set)} (1 count for each file and accompanying sidecar file)"
    )
    logging.info(
        f"{'Total target to template not found ' + dryrun_str:.<65} "
        f"{len(amf.targ_src_path_no_match_set)}"
    )
    logging.info(
        f"{'Total target to template exhausted ' + dryrun_str:.<65} "
        f"{len(amf.targ_src_path_match_exhausted_set)}"
    )
    logging.info(
        f"{'Undo file ' + dryrun_str:.<65} "
        f"{'<none>' if undo_file_path is None else undo_file_path}"
    )

    logging.info(f"Arrange complete.")


def handle_arrange_undo(args):
    is_dryrun=args.dryrun
    with open(file=args.undofile, mode="rt", encoding="utf-8") as undofile:
        undofile_contents = undofile.read()
    undo_operation_list: list[_ArrangeUndoInfo] = json.loads(
        s=undofile_contents,
        cls=_ArrangeUndoInfo.get_json_decoder()
    )
    source_never_moved_count = 0
    dest_does_not_exist_count = 0
    source_exists_count = 0
    successful_undo_count = 0
    failed_undo_count = 0
    undo_operation: _ArrangeUndoInfo
    for undo_operation in undo_operation_list:
        if not undo_operation.is_move_successful:
            source_never_moved_count += 1
            error_message = "unknown"
            if undo_operation.error_msg is not None:
                error_message = undo_operation.error_msg
            logging.warning(
                f"Skipping item 'arrange' never moved: "
                f"orig source={undo_operation.source_full_path} "
                f"orig dest={undo_operation.dest_full_path} "
                f"reason never moved={undo_operation.error_msg}"
            )
            continue
        if not os.path.isfile(undo_operation.dest_full_path):
            dest_does_not_exist_count += 1
            logging.error(
                f"Skipping item, move destination (undo source) not found: "
                f"orig dest={undo_operation.dest_full_path} "
                f"orig source={undo_operation.source_full_path}"
            )
            continue
        if os.path.isfile(undo_operation.source_full_path):
            source_exists_count += 1
            logging.error(
                f"Skipping item, original source (undo dest) file exists, will not overwrite: "
                f"orig dest={undo_operation.dest_full_path} "
                f"orig source={undo_operation.source_full_path}"
            )
            continue

        #
        # Try to undo (move back) the file...
        #
        try:
            if os.path.exists(undo_operation.source_full_path):
                # While os.renames will throw the same exception on destination file already
                # existing, it is exlicity thrown here to simply avoid the call to os.renames.
                raise FileExistsError(
                    f"ERROR: The destination file already exists: "
                    f"{undo_operation.source_full_path}"
                )
            if not is_dryrun:
                os.renames(
                    old=undo_operation.dest_full_path,
                    new=undo_operation.source_full_path,
                )
            successful_undo_count += 1
            logging.info(
                f"Undo successful{' (dry run)' if is_dryrun else ''}: "
                f"{undo_operation.dest_full_path}"
                f" --> UNDO --> "
                f"{undo_operation.source_full_path}"
            )
        except OSError as ex:
            failed_undo_count += 1
            if isinstance(ex, FileExistsError):
                source_never_moved_count += 1
            error_message = (
                f"Undo failed{' (dry run)' if is_dryrun else ''}: "
                f"{undo_operation.dest_full_path}"
                f" --> UNDO --> "
                f"{undo_operation.source_full_path}"
                f"{exc_to_string(ex)}"
            )
            logging.error(error_message)

    dryrun_str = "(--dryrun) " if is_dryrun else " "
    logging.info("--- Undo Summary Report ---")
    logging.info(
        f"{'Total undo operations considered ' + dryrun_str:.<75} "
        f"{len(undo_operation_list)} (includes operations never originally completed due to error)"
    )
    logging.info(
        f"{'Total successful undo operations ' + dryrun_str:.<75} "
        f"{successful_undo_count} undo operations completed."
    )
    logging.info(
        f"{'Count of source files arrange never moved ' + dryrun_str:.<75} "
        f"{source_never_moved_count} skipped undo operations because 'arrange' had skipped these."
    )
    logging.info(
        f"{'Count of nonexistent original destination (undo source) files ' + dryrun_str:.<75} "
        f"{dest_does_not_exist_count} skipped undo operations."
    )
    logging.info(
        f"{'Count of existing original source (undo destination) files ' + dryrun_str:.<75} "
        f"{source_exists_count} skipped undo operations."
    )
    logging.info(
        f"{'Total failed attempted undo operations ' + dryrun_str:.<75} "
        f"{failed_undo_count} unexpectedly failed undo operations."
    )
    logging.info(
        f"{'Undo file ' + dryrun_str:.<75} "
        f"{args.undofile}"
    )

    logging.info(f"Undo complete.")

def handle_arrange(args):
    global _verbosity_level
    if hasattr(args, "verbosity") and args.verbosity is not None:
        _verbosity_level = args.verbosity

    if not args.no_undo and args.undofile is None:
        raise InvalidCommandLineArgument(
            f"Either --no-undo or --undofile <path> must be specified."
        )
    loc_template_root = args.template_dir[0][1]
    loc_template_root_per_type = args.template_dir[0][0]
    if not os.path.exists(loc_template_root):
        raise InvalidCommandLineArgument(
            f"The template root path does not exist: {loc_template_root}"
        )

    loc_target_source_root = args.source_dir[0][1]
    loc_target_source_root_per_type = args.source_dir[0][0]
    if not os.path.exists(loc_target_source_root):
        raise InvalidCommandLineArgument(
            f"The target source root does not exist: {loc_target_source_root}"
        )

    loc_target_dest_root = args.destination_dir[0][1]
    loc_target_dest_root_per_type = args.destination_dir[0][0]

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
        source_path=loc_target_source_root,
        persist_types=loc_target_source_root_per_type,
    )

    logging.info(f"{'Template root directory ':.<45} {loc_template_root}")
    logging.info(f"{'Template root persist type ':.<45} {loc_template_root_per_type}")
    logging.info(f"{'Target source root directory ':.<45} {loc_target_source_root}")
    logging.info(
        f"{'Target source root persist type ':.<45} {loc_target_source_root_per_type}"
    )
    logging.info(
        f"{'Target source destination directory ':.<45} {loc_target_dest_root}"
    )
    logging.info(
        f"{'Target source destination persist type ':.<45} {loc_target_dest_root_per_type}"
    )

    logging.info(f"-" * 65)
    logging.info(f"Searching template root directory: {loc_template_root}")
    updaterA = loc_template_DBs.update(
        change_detection_type=args.change_detection_type,
        update_stale=args.update_stale,
        dryrun=args.dryrun,
    )
    loc_template_info = loc_template_DBs.get_dict_digest_to_fi()
    loc_template_info_skipped = updaterA.skipped_files

    logging.info(f"-" * 65)
    logging.info(f"Searching target source directory: {loc_target_source_root}")
    updaterB = loc_target_source_DBs.update(
        change_detection_type=args.change_detection_type,
        update_stale=args.update_stale,
        dryrun=args.dryrun,
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
        is_dryrun=args.dryrun,
    )
