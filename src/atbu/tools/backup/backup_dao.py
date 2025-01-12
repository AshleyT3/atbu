# Copyright 2022-2024 Ashley R. Thomas
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
r"""Backup configuration/data access objects.
"""

from fnmatch import fnmatchcase
import os
from pathlib import Path
import logging
from enum import Enum
import re
import json
from collections import defaultdict
from datetime import datetime
import threading
from time import perf_counter
from typing import Union

from atbu.common.util_helpers import (
    convert_to_pathlib_path,
    create_numbered_backup_of_file,
)
from atbu.common.multi_json_enc_dec import MultiEncoderDecoder

from .constants import *
from .exception import *
from .backup_entities import (
    BackupFileInformationEntity,
    BackupInformationDatabaseEntity,
    SpecificBackupInformationEntity,
    find_duplicate_in_list,
    is_bfi_modiifed,
)

from .backup_constants import *
from .db_api import (
    DbAppApi,
    BackupInfoRetriever,
    BackupInfoRetrieverResult,
)


class DetectedFileType(Enum):
    UNKNOWN = 0
    NOTFOUND = 1
    JSON = 2
    GZIP = 3
    SQLITE = 4


_GZIP_MAGIC = b"\x1f\x8b"
_SQLITE_MAGIC = b"SQLite format 3\x00"


def is_apparent_json_history_db(path):
    with open(path, "rt", encoding="utf-8") as f:
        header = f.read(1024)
        m = re.search(
            rf'[ \t\n]*{{[ \t\n]*"name"[ \t\n]*\:[ \t\n]*"{BACKUP_DATABASE_DEFAULT_NAME}".*',
            header,
            re.MULTILINE,
        )
    return m is not None


def get_file_type(path):
    try:
        with open(path, "rb") as f:
            header = f.read(20)
        if header[: len(_SQLITE_MAGIC)] == _SQLITE_MAGIC:
            return DetectedFileType.SQLITE
        if header[: len(_GZIP_MAGIC)] == _GZIP_MAGIC:
            return DetectedFileType.GZIP
        if is_apparent_json_history_db(path):
            return DetectedFileType.JSON
        return DetectedFileType.UNKNOWN
    except FileNotFoundError:
        return DetectedFileType.NOTFOUND


_DBAPI_INSTANCES = threading.local()


def get_db_api(db_file_path) -> DbAppApi:
    if not hasattr(_DBAPI_INSTANCES, "db_api"):
        _DBAPI_INSTANCES.db_api = DbAppApi.open_db(db_file_path=db_file_path)
    return _DBAPI_INSTANCES.db_api


def close_db_api():
    if not hasattr(_DBAPI_INSTANCES, "db_api"):
        return
    _DBAPI_INSTANCES.db_api.close()
    delattr(_DBAPI_INSTANCES, "db_api")


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


def remove_timestamp_from_backupinfo_filename(
    filename: str, timestamp_required: bool = True
) -> str:
    re_match_time_stamp = re.compile(
        rf"(.*)(-\d{{8}}-\d{{6}})({BACKUP_INFO_EXTENSION})"
    )
    m = re_match_time_stamp.match(filename)
    if not m:
        if not timestamp_required:
            return filename
        raise BackupInformationFileTimestampNotFound(
            f"The backup information timestamp was not found: {filename}"
        )
    return f"{m.groups()[0]}{m.groups()[2]}"


class BackupFileInformation(BackupFileInformationEntity):
    def __init__(
        self,
        path: str,
        discovery_path: str = None,
        sb_id: int = None,
        bfi_id: int = None,
    ):
        super().__init__(
            path=path, discovery_path=discovery_path, sb_id=sb_id, bfi_id=bfi_id
        )

    def insert_into_db(
        self,
        db_api: DbAppApi,
        specific_backup_id,
    ) -> int:
        return db_api.insert_specific_backup_file_info(
            specific_backup_id=specific_backup_id,
            path=self.path,
            last_modified=self.modified_time_posix,
            last_accessed=self.accessed_time_posix,
            lastmodified_stamp=self.modified_date_stamp_ISO8601_utc,
            size_in_bytes=self.size_in_bytes,
            digests=self.digests,
            discovery_path=self.discovery_path,
            is_successful=self.is_successful,
            exception=None if self.exception is None else str(self.exception),
            ciphertext_hash=self._ciphertext_hash_during_backup,
            encryption_iv=self.encryption_IV,
            storage_object_name=self.storage_object_name,
            is_unchanged_since_last=self.is_unchanged_since_last,
            is_backing_fi_digest=self.is_backing_fi_digest,
            deduplication_option=self.deduplication_option,
        )

    def to_serialization_dict(self) -> dict:
        d = super().to_serialization_dict()
        d = d | {
            "_type": "BackupFileInformation",
            "_discovery_path": self._discovery_path,
            "is_successful": self.is_successful,
            "exception": (
                self.exception if self.exception is None else str(self.exception)
            ),
            "ciphertext_hash": self._ciphertext_hash_during_backup,
            "encryption_IV": self.encryption_IV.hex() if self.encryption_IV else None,
            "storage_object_name": self.storage_object_name,
            "is_unchanged_since_last": self.is_unchanged_since_last,
            "is_backing_fi_digest": self.is_backing_fi_digest,
            "deduplication_option": self.deduplication_option,
        }
        return d

    def from_serialization_dict(self, d: dict):
        super().from_serialization_dict(d)
        self._discovery_path = d["_discovery_path"]
        self.is_successful = d["is_successful"]
        self.exception = d["exception"]
        self._ciphertext_hash_during_backup = d["ciphertext_hash"]
        self.storage_object_name = d["storage_object_name"]
        self.is_unchanged_since_last = d["is_unchanged_since_last"]
        self.is_backing_fi_digest = d["is_backing_fi_digest"]
        self.deduplication_option = d["deduplication_option"]
        if isinstance(d["encryption_IV"], str):
            self.encryption_IV = bytes.fromhex(d["encryption_IV"])
            self._is_backup_encrypted = True
        else:
            self.encryption_IV = None
            self._is_backup_encrypted = False


class SpecificBackupInformation(SpecificBackupInformationEntity):
    """Represents information of a specific backup session, which includes a list
    BackupFileInformation instances representing files that were backed up.
    """

    def __init__(
        self,
        is_persistent_db_conn: bool = False,
        backup_database_file_path: str = None,
        backup_base_name: str = None,
        specific_backup_name: str = None,
        backup_start_time_utc: datetime = None,
        object_name_hash_salt: bytes = None,
        backup_type: str = None,
        sbi_id: int = None,
    ):
        super().__init__(
            is_persistent_db_conn=is_persistent_db_conn,
            backup_database_file_path=backup_database_file_path,
            backup_base_name=backup_base_name,
            specific_backup_name=specific_backup_name,
            backup_start_time_utc=backup_start_time_utc,
            object_name_hash_salt=object_name_hash_salt,
            backup_type=backup_type,
            sbi_id=sbi_id,
        )

    def save_to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as backup_info_file:
            backup_info_file.write(
                json.dumps(
                    self,
                    cls=backup_info_json_enc_dec.get_json_encoder_class(),
                )
            )

    @staticmethod
    def create_from_file(backup_info_filename: str) -> list:
        backup_info_filename = convert_to_pathlib_path(backup_info_filename)
        if not isinstance(backup_info_filename, Path):
            raise ValueError(f"backup_info_path should be a str or Path.")
        try:
            # Open/parse...
            with open(str(backup_info_filename), "r", encoding="utf-8") as file:
                backup_info: SpecificBackupInformation = json.load(
                    fp=file, cls=backup_info_json_enc_dec.get_json_decoder_class()
                )
            return backup_info
        except Exception as ex:
            raise BackupInformationError(
                f"Error parsing backup information file: "
                f"filename={backup_info_filename} {exc_to_string(ex)}"
            ).with_traceback(ex.__traceback__) from ex

    def to_serialization_dict(self) -> dict:
        self.all_file_info.sort(key=lambda f: f.path)
        d = {
            BACKUP_INFO_BASE_NAME: self.backup_base_name,
            BACKUP_INFO_SPECIFIC_NAME: self.specific_backup_name,
            BACKUP_INFO_START_TIME_NAME: self.backup_start_time_utc.isoformat(
                timespec="seconds"
            ),
            BACKUP_INFO_STORAGE_OBJECT_NAME_SALT: self.object_name_hash_salt.hex(),
            BACKUP_INFO_BACKUP_TYPE_NAME: self.backup_type,
            BACKUP_INFO_ALL_SECTION_NAME: self.all_file_info,
        }
        return d

    def from_serialization_dict(self, d: dict):
        self.backup_base_name = d[BACKUP_INFO_BASE_NAME]
        self.specific_backup_name = d[BACKUP_INFO_SPECIFIC_NAME]
        self.backup_start_time_utc = datetime.fromisoformat(
            d[BACKUP_INFO_START_TIME_NAME]
        )
        self.object_name_hash_salt = bytes.fromhex(
            d[BACKUP_INFO_STORAGE_OBJECT_NAME_SALT]
        )
        self.backup_type = d[BACKUP_INFO_BACKUP_TYPE_NAME]
        self.all_file_info = d.get(BACKUP_INFO_ALL_SECTION_NAME)

    def insert_into_db(
        self,
        backups_root_id: int,
        db_api: DbAppApi,
    ) -> int:
        if db_api is None:
            raise ValueError(f"db_api cannot be None.")
        return db_api.insert_specific_backup(
            parent_backups_id=backups_root_id,
            backup_specific_name=self.specific_backup_name,
            backup_start_time_utc=self.backup_start_time_utc.isoformat(timespec="seconds"),
            object_name_hash_salt=self.object_name_hash_salt,
            backup_type=self.backup_type,
        )

    def select_from_db(
        self,
        db_api: DbAppApi,
        resolve_backing_fi: bool = False,
    ):
        if db_api is None:
            raise ValueError(f"db_api cannot be None.")
        self.all_file_info = db_api.get_specific_backup_file_info(
            specific_backup_id=self.sbi_id,
            resolve_backing_fi=resolve_backing_fi,
            cls_entity=BackupFileInformation,
        )
        pass

    def get_bfi_matching_fnpat(
        self,
        normcase_pattern: str,
    ) -> list[BackupFileInformation]:

        nc_path_to_fi_dict: dict[str, BackupFileInformation] = {}
        if self.all_file_info is not None:
            for sb_fi in self.all_file_info:
                nc_path_to_fi_dict[sb_fi.nc_path_without_root] = sb_fi

        if self.is_persistent_db_conn:
            db_api = get_db_api(db_file_path=self.backup_database_file_path)
            fi_list = db_api.get_bfi_matching_fn_pat(
                specific_backup_id=self.sbi_id,
                fn_pat=normcase_pattern,
                cls_entity=BackupFileInformation,
            )
            if self.all_file_info is None:
                self.all_file_info = fi_list
                nc_path_to_fi_dict = {
                    sb_fi.nc_path_without_root: sb_fi for sb_fi in fi_list
                }
            else:
                for sb_fi in fi_list:
                    if nc_path_to_fi_dict.get(sb_fi.nc_path_without_root) is None:
                        nc_path_to_fi_dict[sb_fi.nc_path_without_root] = sb_fi
                        self.all_file_info.append(sb_fi)

        result: list[BackupFileInformation] = []

        # Check each normcase'ed path against the glob-like pattern.
        for normcase_path, fi in nc_path_to_fi_dict.items():

            # path and pattern are already normcase so using fnmatchcase is fine.
            if not self.is_persistent_db_conn and not fnmatchcase(
                normcase_path, normcase_pattern
            ):
                continue

            # Sanity check state, ensure file is resolved with backing_fi.
            if fi.is_unchanged_since_last and not fi.backing_fi:
                # If unchanged file has unresolved backing_fi, fail.
                raise BackingFileInformationNotFound(
                    f"An unchanged since last file has no backing file information: "
                    f"fi={fi.path}"
                )
            result.append(fi)

        return result


class BackupInformationDatabase(BackupInformationDatabaseEntity):
    def __init__(
        self,
        is_persistent_db_conn: bool = False,
        backup_base_name: str = None,
        backup_info_dir: Union[str, Path] = None,
        force_db_type: DatabaseFileType = DatabaseFileType.DEFAULT,
    ):
        super().__init__(
            is_persistent_db_conn=is_persistent_db_conn,
            backup_base_name=backup_base_name,
            backup_info_dir=backup_info_dir,
        )
        self.force_db_type = force_db_type
        self.loaded_backup_db_file_path = None
        self.loaded_backup_db_file_type = DatabaseFileType.DEFAULT
        self._bir: BackupInfoRetriever = None

    def populate_backup_info_cache(
        self,
        backup_file_list: list[BackupFileInformation],
    ):
        if self.is_persistent_db_conn and self._bir is None:
            logging.info(f"Populating backup history cache...")
            start_populate = perf_counter()
            self._bir = BackupInfoRetriever(
                get_db_api(
                    db_file_path=self.primary_db_full_path,
                ),
                BackupFileInformation
            )
            self._bir.populate_backup_info(
                backup_file_list=backup_file_list,
            )
            logging.info(
                f"Populating backup history cache completed in "
                f"{perf_counter()-start_populate:.3f} seconds."
            )

    @property
    def is_most_recent_backup_cache_valid(self):
        return self._bir is not None and self._bir.is_populated

    def get_cached_most_recent_backup_of_path(
        self,
        path: str,
    ) -> BackupFileInformation:
        if not self.is_most_recent_backup_cache_valid:
            return None
        return self._bir.get_cached_most_recent_backup_of_path(
            path=path,
        )

    def get_file_date_size_modified_state(
        self, cur_fi: BackupFileInformation
    ) -> tuple[bool, BackupFileInformation]:
        """For path, last backup info, if any, and related change status."""
        existing_fi = self.get_most_recent_backup_of_path(fi=cur_fi)
        is_changed = is_bfi_modiifed(
            cur_bfi=cur_fi,
            most_recent_backup_bfi=existing_fi,
            check_digests=False,
        )
        return is_changed, existing_fi

    def get_primary_digest_changed_info(
        self, cur_fi: BackupFileInformation
    ) -> tuple[bool, BackupFileInformation]:
        """For path, last backup info, if any, and related digest-based change status."""
        existing_fi = self.get_most_recent_backup_of_path(fi=cur_fi)
        is_changed = True
        if (
            existing_fi is not None
            and existing_fi.is_backed_up
            and cur_fi.primary_digest == existing_fi.primary_digest
        ):
            is_changed = False
        return is_changed, existing_fi

    def is_phys_backup_dup_exist(
        self,
        cur_fi: BackupFileInformation,
    ) -> bool:
        if self.is_persistent_db_conn:
            db_api = get_db_api(db_file_path=self.primary_db_full_path)
            dup_list = db_api.get_phys_backup_dup_list(cur_fi=cur_fi)
        else:
            dup_list = self.digest_to_bfi_list.get(cur_fi.primary_digest)
        return dup_list is not None and len(dup_list) > 0

    def get_potential_bitrot_or_sneaky_corruption_info(
        self,
        cur_fi: BackupFileInformation,
    ) -> tuple[bool, BackupFileInformation]:
        """So-called sneaky corruption is when the the prior backup for the same
        path location as cur_fi has the same date/time and size, but the digests
        are different. In such a case, the file content has been modified while
        its date/time and size have not changed. This could be bitrot or a
        normal/malicious program updating the modified date/time after changing
        file content.

        Args:
            cur_fi (BackupFileInformation): The file info whose location will be
                used to find existing sneaky corruption info.

        Returns:
            tuple[bool, BackupFileInformation]: Tuple (is_potential,
                BackupFileInformation) where is_potential is True if there is
                potential sneaky corruption, else False. BackupFileInformation
                is the prior backup for the same path location as cur_fi.
        """
        # Get change state for same path location.
        is_changed, existing_fi = self.get_file_date_size_modified_state(cur_fi=cur_fi)
        if is_changed or existing_fi is None:
            return (False, existing_fi)
        # File date/time and size are not changed.
        # If digests are mismatched, potentially sneaky corruption exists.
        return (cur_fi.primary_digest != existing_fi.primary_digest, existing_fi)

    def get_duplicate_file(
        self,
        deduplication_option: str,
        bfi: BackupFileInformation,
    ) -> BackupFileInformation:
        if self.is_persistent_db_conn:
            db_api = get_db_api(db_file_path=self.primary_db_full_path)
            return db_api.get_duplicate_file(
                deduplication_option=deduplication_option, bfi=bfi,
                cls_entity=BackupFileInformation,
            )

        dup_list = self.digest_to_bfi_list.get(bfi.primary_digest)
        return find_duplicate_in_list(
            deduplication_option=deduplication_option,
            bfi=bfi,
            dup_list=dup_list,
        )

    def get_most_recent_backup_of_path(
        self, fi: BackupFileInformation
    ) -> BackupFileInformation:
        if self.is_persistent_db_conn:
            if self.is_most_recent_backup_cache_valid:
                fi_most_recent = self.get_cached_most_recent_backup_of_path(
                    path=fi.path,
                )
            else:
                db_api = get_db_api(db_file_path=self.primary_db_full_path)
                fi_most_recent = db_api.get_most_recent_backup_of_path(
                    path_to_find=fi.path,
                    cls_entity=BackupFileInformation,
                )
        else:
            fi_most_recent = self.path_to_most_recent_bfi.get(
                os.path.normcase(fi.path_without_root)
            )
        return fi_most_recent

    def has_backup(self, backup_base_name: str, specific_backup_name: str) -> bool:
        if (
            self.backup_base_name is not None
            and self.backup_base_name != backup_base_name
        ):
            raise ValueError(
                f"Backup basename mismatch: db={self.backup_base_name} bn={backup_base_name}"
            )
        if self.backups.get(backup_base_name) is None:
            return False
        return specific_backup_name in self.backups[backup_base_name]

    def append(self, sbi: SpecificBackupInformation, rebuild_hashes: bool = False):
        if self.backups.get(sbi.backup_base_name) is None:
            if len(self.backups) > 0:
                # Multiple backup definitions could be supported per
                # file but current expectation is 1 per file.
                first_key = next(iter(self.backups.keys()))
                raise BackupInformationError(
                    f"The backup '{sbi.backup_base_name}' is mismatched "
                    f"to existing backup name '{first_key}'."
                )
            self.backups[sbi.backup_base_name] = {}
        if self.backups[sbi.backup_base_name].get(sbi.specific_backup_name) is not None:
            raise BackupInformationError(
                f"The backup information for '{sbi.specific_backup_name}' already exists."
            )
        self.backups[sbi.backup_base_name][sbi.specific_backup_name] = sbi
        if rebuild_hashes:
            self._rebuild_hashes()

    def get_specific_backup(
        self, specific_backup_name: str
    ) -> SpecificBackupInformation:
        """Returns a specific backup instance."""
        return self.backups[self.backup_base_name].get(specific_backup_name)

    def get_specific_backups(self, descending=True) -> list[SpecificBackupInformation]:
        """Returns a list of specific backup instances in descending
        chronological order (most recent first).
        """
        b = sorted(
            [*self.backups[self.backup_base_name].values()],
            key=lambda s: s.backup_start_time_utc,
            reverse=descending,
        )
        return b

    def _rebuild_hashes(self):

        self.path_to_most_recent_bfi: dict[str, BackupFileInformationEntity] = {}
        self.digest_to_bfi_list: defaultdict[str, list[BackupFileInformationEntity]] = (
            defaultdict(list[BackupFileInformationEntity])
        )

        if len(self.backups) == 0:
            return
        # From most recent to oldest backup, build path_to_info. First set in path_to_info[path]
        # for given path wins (i.e., newest is reachable via the index).
        specific_backups: list[SpecificBackupInformation] = self.get_specific_backups()
        needs_backing_fi_dict: defaultdict[str, list[BackupFileInformation]] = (
            defaultdict(list[BackupFileInformation])
        )
        needs_backing_fi_from_dedup: list[BackupFileInformation] = []
        for sb in specific_backups:
            sb_fi: BackupFileInformation
            for sb_fi in sb.all_file_info:

                # The backup info file currently tracks unsuccessful backups.
                # Do not use unsuccessful backup information.
                # Check is_unchanged_since_last because unchanged files do not
                # track success status given no operation occurs at time of
                # backup though they are not failed items.
                # TODO: Review whether or not to continue to track unnsuccessful
                # backup file information.
                if not sb_fi.is_successful and not sb_fi.is_unchanged_since_last:
                    continue

                #
                # Two things performed in this 'for' ...
                #   A) try to resolve any wanting fi using this sb_fi.
                #   B) add the sb_fi to the digest_to_bfi_list (for later
                #      digest-based lookups, such as deduplication).
                #   C) track via dict/structs (see below) this sb_fi as needed.
                #

                #
                # A) Resolve any wanting fi:
                #
                # A normcase path_without_location_root is needed for dict below.
                nc_path_wo_root = sb_fi.nc_path_without_root
                # If this sb_fi needs resolving, add to "to be resolved" dict.
                if sb_fi.is_unchanged_since_last and sb_fi.backing_fi is None:
                    if not sb_fi.deduplication_option:
                        needs_backing_fi_dict[nc_path_wo_root].append(sb_fi)
                    else:
                        needs_backing_fi_from_dedup.append(sb_fi)
                # If this sb_fi does not need resolving, perhaps it can help resolve...
                if not sb_fi.is_unchanged_since_last:
                    # Any fi needing this fi for resolution?
                    needs_backing_fi_list = needs_backing_fi_dict.get(nc_path_wo_root)
                    if needs_backing_fi_list:
                        # Yes, then resolve all of them to this sb_fi.
                        for wanting_fi in needs_backing_fi_list:
                            wanting_fi.backing_fi = sb_fi
                        # The wanting fi are no longer wanting.
                        del needs_backing_fi_dict[nc_path_wo_root]
                    # B) Track (via dict) the digest for all sb_fi representing physical backups.
                    # For all sb_fi representing backups (is_unchanged_since_last==False),
                    # track (via dict) its digest, add it to the digest's list.
                    self.digest_to_bfi_list[sb_fi.primary_digest].append(sb_fi)

                #
                # C) Track (via dict) this sb_fi as needed:
                #
                if not self.path_to_most_recent_bfi.get(nc_path_wo_root):
                    # This path not tracked already, so it is the first most recent, track it.
                    self.path_to_most_recent_bfi[nc_path_wo_root] = sb_fi
        if len(needs_backing_fi_from_dedup) > 0:
            needs_backing_fi: BackupFileInformation
            for needs_backing_fi in list(needs_backing_fi_from_dedup):
                # Find the duplicate using the same approach used when this file was backed up.
                dup_fi = self.get_duplicate_file(
                    deduplication_option=needs_backing_fi.deduplication_option,
                    bfi=needs_backing_fi,
                )
                if dup_fi:
                    if needs_backing_fi.backing_fi is not None:
                        raise InvalidStateError(
                            f"Unexpected state: BackupFileInformation.backing_fi must be None: "
                            f"{needs_backing_fi.path}"
                        )
                    needs_backing_fi.backing_fi = dup_fi
                    needs_backing_fi_from_dedup.remove(needs_backing_fi)
        if len(needs_backing_fi_dict) > 0:
            failing_paths = list(needs_backing_fi_dict.keys())
            raise InvalidStateError(
                f"Unexpected state: BackupFileInformation instances still "
                f"require backing BackupFileInformation: {failing_paths}"
            )
        if len(needs_backing_fi_from_dedup) > 0:
            failing_paths = [fi.path for fi in needs_backing_fi_from_dedup]
            raise InvalidStateError(
                f"Unexpected state: BackupFileInformation instances for dedup "
                f"still require backing BackupFileInformation: {failing_paths}"
            )

    @staticmethod
    def _resolve_backup_names_dirs(
        backup_database_file_path: Union[str, Path],
        backup_base_name: str,
        backup_info_dir: Union[str, Path],
    ) -> tuple[Path, str, Path]:
        """Resolve values relating to the location of the backup history DB file.
        All 3 values can be supplied, or at least backup_database_file_path alone or
        both backup_info_dir/backup_base_name as a pair must be supplied. Either
        can derive the other. Originally, there was a backup name (backup_base_name)
        which had its information placed within a dedicated directory (backup_info_dir).
        However, there are times (i.e., features, testing) where a path (backup_database_file_path)
        is known. The path essentially contains the backup dir and backup name, though
        getting at the backup name requires removing, for, the extension from the filename,
        and any timestamps if revelant.
        """
        if not backup_database_file_path and (
            not backup_info_dir or not backup_base_name
        ):
            raise ValueError(
                "Either backup_database_file_path or "
                "both backup_info_dir/backup_base_name required."
            )
        if backup_database_file_path and not isinstance(
            backup_database_file_path, (str, Path)
        ):
            raise ValueError(
                "backup_database_file_path, if specified, must be str or Path."
            )
        if backup_info_dir and not isinstance(backup_info_dir, (str, Path)):
            raise ValueError("backup_info_dir, if specified, must be str or Path.")
        if backup_base_name and not isinstance(backup_base_name, str):
            raise ValueError("backup_base_name, if specified, must be str or Path.")

        if backup_database_file_path:
            backup_database_file_path = Path(backup_database_file_path)

        if not backup_info_dir:
            # If not backup_info_dir, backup_database_file_path is valid (see above).
            backup_info_dir = backup_database_file_path.parent
        backup_info_dir = Path(backup_info_dir)

        if not backup_base_name:
            # If not backup_base_name, backup_database_file_path is valid (see above).
            filename_no_ts = remove_timestamp_from_backupinfo_filename(
                filename=backup_database_file_path.name,
                timestamp_required=False,
            )
            backup_base_name = Path(filename_no_ts).stem
        backup_base_name = str(backup_base_name).lower()

        if not backup_database_file_path:
            # If not backup_database_file_path, both backup_info_dir and backup_base_name are valid.
            backup_database_file_path = backup_info_dir / backup_base_name
            backup_database_file_path = backup_database_file_path.with_suffix(
                BACKUP_INFO_EXTENSION
            )

        return backup_database_file_path, backup_base_name, backup_info_dir

    def _insert_sbi_into_db(
        self,
        db_api: DbAppApi,
        sbi: SpecificBackupInformation,
    ) -> int:
        logging.info(f"Inserting backup into database: {sbi.specific_backup_name}")
        backups_root_id, _ = db_api.get_backups_root()
        sbi.sbi_id = sbi.insert_into_db(
            backups_root_id=backups_root_id,
            db_api=db_api,
        )
        fi: BackupFileInformation
        for fi in sbi.all_file_info:
            fi.bfi_id = fi.insert_into_db(
                db_api=db_api, specific_backup_id=sbi.sbi_id
            )
        return sbi.sbi_id
    
    def save_backup_into_db(
        self,
        sbi: SpecificBackupInformation,
        db_file_path: Union[str, Path] = None,
    ):
        close_db_api()
        db_api = get_db_api(db_file_path=db_file_path)
        try:
            self._insert_sbi_into_db(
                db_api=db_api,
                sbi=sbi,
            )
            db_api.commit()
        except:
            db_api.rollback()
        finally:
            close_db_api()

    def create_db(
        self,
        db_file_path: Union[str, Path],
        overwrite: bool = False,
    ):
        logging.info(f"Creating new SQL database: {db_file_path}")
        with DbAppApi.create_new_db(
            db_file_path,
            self.backup_base_name,
            overwrite=overwrite,
        ) as db_api:
            for sbi in self.get_specific_backups(descending=False):
                self._insert_sbi_into_db(
                    db_api=db_api,
                    sbi=sbi,
                )
            db_api.commit()

    def _load_backup_info_from_db(self, db_api: DbAppApi):

        _, db_name, db_ver = db_api.get_backup_db_root()

        self.all_backup_info[CONFIG_VALUE_NAME_CONFIG_NAME] = db_name
        self.all_backup_info[CONFIG_VALUE_NAME_VERSION] = db_ver

        _, self.backup_base_name = db_api.get_backups_root()

        # Currently only one backup config per DB.
        # Remove anything present, replace it with this DB's backup config.
        self.backups.clear()

        sbi_list = db_api.get_specific_backups(
            is_persistent_db_conn=self.is_persistent_db_conn,
            backup_database_file_path=self.primary_db_full_path,
            backup_base_name=self.backup_base_name,
            cls_entity=SpecificBackupInformation,
        )

        self.backups[self.backup_base_name] = sbi_list

        if not self.is_persistent_db_conn:
            sbi: SpecificBackupInformation
            for sbi_name, sbi in self.backups[self.backup_base_name].items():
                sbi.select_from_db(db_api=db_api, resolve_backing_fi=False)

    def _open_db_persistent(self, db_file_path: Union[str, Path]):
        if not self.is_persistent_db_conn:
            raise InvalidStateError("The db.open_db_persistent must be True.")
        db_api = get_db_api(db_file_path=db_file_path)
        self._load_backup_info_from_db(db_api=db_api)

    def _open_db_load_entire_db(self, db_file_path: Union[str, Path]):
        if self.is_persistent_db_conn:
            raise InvalidStateError("The db.open_db_persistent must be False.")
        with DbAppApi.open_db(db_file_path=db_file_path) as db_api:
            self._load_backup_info_from_db(db_api=db_api)
        self._rebuild_hashes()

    def save(
        self,
        dest_backup_info_dir: Union[str, Path] = None,
        backup_database_file_path: Union[str, Path] = None,
        json_indent: int = None,
        create_numbered_backup: bool = True,
        sbi_to_insert_hint: SpecificBackupInformation = None,
    ):
        backup_database_file_path, _, _ = (
            BackupInformationDatabase._resolve_backup_names_dirs(
                backup_database_file_path=backup_database_file_path,
                backup_base_name=self.backup_base_name,
                backup_info_dir=dest_backup_info_dir,
            )
        )

        if create_numbered_backup:
            create_numbered_backup_of_file(
                path=backup_database_file_path, not_exist_ok=True
            )

        current_file_type = get_file_type(path=backup_database_file_path)
        if current_file_type == DetectedFileType.UNKNOWN:
            raise BackupInformationError(
                f"The existing file was of an unknown type: {backup_database_file_path}"
            )

        if self.force_db_type == DatabaseFileType.JSON or (
            self.force_db_type == DatabaseFileType.DEFAULT
            and current_file_type == DetectedFileType.JSON
        ):
            with open(
                backup_database_file_path, "w", encoding="utf-8"
            ) as backup_info_file:
                json.dump(
                    obj=self,
                    fp=backup_info_file,
                    cls=backup_info_json_enc_dec.get_json_encoder_class(),
                    indent=json_indent,
                )
        else:
            if not sbi_to_insert_hint or current_file_type != DetectedFileType.SQLITE:
                self.create_db(
                    db_file_path=backup_database_file_path,
                    overwrite=True,
                )
            else:
                self.save_backup_into_db(
                    sbi=sbi_to_insert_hint,
                    db_file_path=backup_database_file_path,
                )

    @staticmethod
    def load(
        backup_base_name: str = None,
        backup_info_dir: Union[str, Path] = None,
        backup_database_file_path: Union[str, Path] = None,
        create_if_not_exist: bool = False,
        force_db_type: DatabaseFileType = DatabaseFileType.DEFAULT,
    ) -> "BackupInformationDatabase":

        backup_database_file_path, backup_base_name, backup_info_dir = (
            BackupInformationDatabase._resolve_backup_names_dirs(
                backup_database_file_path=backup_database_file_path,
                backup_base_name=backup_base_name,
                backup_info_dir=backup_info_dir,
            )
        )

        if not backup_database_file_path.exists():
            if not create_if_not_exist:
                raise BackupInformationError(
                    f"Backup information db not found: "
                    f"backup_database_file_path={backup_database_file_path} "
                    f"backup_base_name={backup_base_name} "
                    f"backup_info_dir={backup_info_dir} "
                )

            logging.info(
                f"No backup history for '{backup_base_name}'. Creating new history database."
            )
            bid = BackupInformationDatabase(
                is_persistent_db_conn=force_db_type != DatabaseFileType.JSON,
                backup_base_name=backup_base_name,
                backup_info_dir=backup_info_dir,
                force_db_type=force_db_type,
            )
            bid.save(
                dest_backup_info_dir=backup_info_dir,
            )
            if force_db_type != DatabaseFileType.JSON:
                bid._open_db_persistent(db_file_path=backup_database_file_path)
            else:
                bid._rebuild_hashes()  # pylint: disable=protected-access
            return bid

        ft = get_file_type(path=backup_database_file_path)
        if ft == DetectedFileType.JSON:
            logging.info(f"Loading JSON backup information file...")
            try:
                # Open/parse...
                with open(
                    str(backup_database_file_path), "r", encoding="utf-8"
                ) as file:
                    bid: BackupInformationDatabase = json.load(
                        fp=file, cls=backup_info_json_enc_dec.get_json_decoder_class()
                    )
                bid.is_persistent_db_conn = False
                bid.loaded_backup_db_file_path = backup_database_file_path
                bid.loaded_backup_db_file_type = DatabaseFileType.JSON
                if not bid.backup_base_name:
                    bid.backup_base_name = backup_base_name
                bid.backup_info_dir = backup_info_dir
                bid._rebuild_hashes()  # pylint: disable=protected-access
                bid.force_db_type = force_db_type
                return bid
            except Exception as ex:
                raise BackupInformationError(
                    f"Error loading JSON backup information file: "
                    f"filename={backup_database_file_path} {exc_to_string(ex)}"
                ).with_traceback(ex.__traceback__) from ex
        elif ft == DetectedFileType.SQLITE:

            bid = BackupInformationDatabase(
                is_persistent_db_conn=force_db_type != DatabaseFileType.JSON,
                backup_base_name=backup_base_name,
                backup_info_dir=backup_info_dir,
            )
            if force_db_type != DatabaseFileType.JSON:
                bid._open_db_persistent(db_file_path=backup_database_file_path)
            else:
                bid._open_db_load_entire_db(db_file_path=backup_database_file_path)
            bid.force_db_type = force_db_type
            bid.loaded_backup_db_file_path = backup_database_file_path
            bid.loaded_backup_db_file_type = DatabaseFileType.SQLITE
            return bid
        else:
            raise BackupInformationError(
                "Unknown backup information database file type."
            )

    def to_serialization_dict(self) -> dict:
        return self.all_backup_info

    def from_serialization_dict(self, d: dict):
        self.all_backup_info = d
        self.backups: dict = self.all_backup_info[BACKUP_INFO_BACKUPS_SECTION_NAME]
        if len(self.backups):
            self.backup_base_name = next(iter(self.backups))


backup_info_json_enc_dec = MultiEncoderDecoder()
backup_info_json_enc_dec.add_def(
    class_type=BackupFileInformation,
    to_dict_method=BackupFileInformation.to_serialization_dict,
    from_dict_method=BackupFileInformation.from_serialization_dict,
    constructor_arg_names=["path"],
)
backup_info_json_enc_dec.add_def(
    class_type=SpecificBackupInformation,
    to_dict_method=SpecificBackupInformation.to_serialization_dict,
    from_dict_method=SpecificBackupInformation.from_serialization_dict,
    constructor_arg_names=[],
)
backup_info_json_enc_dec.add_def(
    class_type=BackupInformationDatabase,
    to_dict_method=BackupInformationDatabase.to_serialization_dict,
    from_dict_method=BackupInformationDatabase.from_serialization_dict,
    constructor_arg_names=[],
)
