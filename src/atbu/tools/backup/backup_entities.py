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

from typing import TypeVar, Union
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from atbu.common.exception import *

from .backup_constants import (
    BACKUP_DATABASE_DEFAULT_NAME,
    BACKUP_INFO_BACKUPS_SECTION_NAME,
    BACKUP_INFO_EXTENSION,
    BACKUP_INFO_MAJOR_VERSION_STRING,
    BACKUP_INFO_TIME_STAMP_FORMAT,
)
from .constants import (
    ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST_EXT,
    CONFIG_VALUE_NAME_CONFIG_NAME,
    CONFIG_VALUE_NAME_VERSION,
)
from .exception import BackupFileInformationError, BackupFileInformationNotInitialized
from ..persisted_info.file_info import FileInformation


def split_path_root(path) -> tuple[str, str]:
    path_root, path_without_root = os.path.splitdrive(path)
    if path_without_root[0] in ["\\", "/"]:
        path_root += path_without_root[:1]
        path_without_root = path_without_root[1:]
    return path_root, path_without_root


class BackupFileInformationEntity(FileInformation):
    def __init__(
        self,
        path: Union[str, Path],
        discovery_path: Union[str, Path] = None,
        sb_id: int = None,
        bfi_id: int = None,
    ):
        """If adding/removing arguments, update backup_info_json_enc_dec."""
        super().__init__(path=path)
        self.sb_id = sb_id
        self.bfi_id = bfi_id
        self._path_root, self._path_without_root = split_path_root(path=path)
        if isinstance(discovery_path, Path):
            discovery_path = str(discovery_path)
        self._discovery_path = discovery_path
        self._is_backup_encrypted = False
        self.is_successful = False
        self.exception = None
        self._ciphertext_hash_during_backup = None
        self.encryption_IV: bytes = None
        self.storage_object_name = None
        self.is_unchanged_since_last = False
        self.deduplication_option = None
        self.is_backing_fi_digest = False
        self.backing_fi: BackupFileInformationEntity = None  # Not persisted
        self.cleartext_hash_during_restore = None  # Not persisted
        self.ciphertext_hash_during_restore = None  # Not persisted
        self._restore_path_override = None  # Not persisted
        self.populate_from_header: bool = False  # Not persisted
        self.is_decrypt_operation: bool = False  # Not persisted
        self.is_compressed: bool = False  # Not peristed
        self.compressed_file_path: str = None  # Not persisted
        self.compressed_size: int = (
            None  # Not persisted (what was written to pipe for file)
        )

    def __eq__(self, o) -> bool:
        if not isinstance(o, BackupFileInformationEntity):
            raise ValueError("Expecting BackupFileInformationEntity for 'o' other arg.")
        if self.bfi_id is None and o.bfi_id is None:
            return self is o
        if self.bfi_id is None or self.sb_id is None or o.bfi_id is None or o.sb_id is None:
            raise ValueError(
                f"Expecting all database id values to be valid. "
                f"self.bfi_id={self.bfi_id} "
                f"self.sb_id={self.sb_id} "
                f"self.bfi_id={o.bfi_id} "
                f"self.bfi_id={o.sb_id} "
            )
        if self.sb_id != o.sb_id or self.bfi_id != self.bfi_id:
            return False
        attr_names = list(vars(self))
        for an in attr_names:
            if not hasattr(self, an) or not hasattr(o, an):
                return False
            if getattr(self, an) != getattr(o, an):
                return False
        return True

    @property
    def path_for_logging(self):
        try:
            if self.discovery_path is not None:
                return self.path_without_discovery_path
        except BackupFileInformationError:
            pass
        return self.path_without_root

    @property
    def path_root(self):
        return self._path_root

    @property
    def path_without_root(self):
        return self._path_without_root

    @property
    def nc_path_without_root(self):
        return os.path.normcase(self.path_without_root)

    @property
    def discovery_path(self):
        return self._discovery_path

    @property
    def nc_discovery_path(self):
        return os.path.normcase(self.discovery_path)

    @property
    def discovery_path_without_root(self):
        return split_path_root(self._discovery_path)[1]

    @property
    def nc_discovery_path_without_root(self):
        return os.path.normcase(self.discovery_path_without_root)

    @property
    def path_without_discovery_path(self):
        if self.discovery_path is None:
            raise BackupFileInformationError(
                f"The file information has no discovery path: {self.path}"
            )

        nc_path_without_root = self.nc_path_without_root
        nc_discovery_path_without_root = self.nc_discovery_path_without_root
        if not nc_path_without_root.startswith(nc_discovery_path_without_root):
            raise BackupFileInformationError(
                f"The discovery path cannot be found: "
                f"disc_path={self.discovery_path} path={self.path}"
            )

        if nc_path_without_root == nc_discovery_path_without_root:
            return self.path_without_root

        return self.path_without_root[len(nc_discovery_path_without_root) + 1 :]

    @property
    def restore_path_override(self):
        return self._restore_path_override

    @restore_path_override.setter
    def restore_path_override(self, value):
        self._restore_path_override = value

    @property
    def restore_path(self):
        if self._restore_path_override is not None:
            return self.restore_path_override
        return self.path_without_root

    @property
    def is_backup_encrypted(self):
        if self.backing_fi:
            return self.backing_fi.is_backup_encrypted
        return self._is_backup_encrypted

    @is_backup_encrypted.setter
    def is_backup_encrypted(self, value):
        self._is_backup_encrypted = value

    @property
    def ciphertext_hash_during_backup(self):
        if not self.is_backup_encrypted:
            raise InvalidStateError(
                f"Call to ciphertext_hash_during_backup when backup not encrypted. "
                f"If related to retrieval (i.e., restore/verify), "
                f"was setting is_backup_encrypted overlooked?"
            )
        if self.is_unchanged_since_last and self.backing_fi:
            return self.backing_fi.ciphertext_hash_during_backup
        return self._ciphertext_hash_during_backup

    @ciphertext_hash_during_backup.setter
    def ciphertext_hash_during_backup(self, value):
        self._ciphertext_hash_during_backup = value

    @property
    def is_failed(self):
        return self.exception is not None

    @property
    def is_backed_up(self):
        return not self.is_failed and (self.is_successful or self.is_unchanged_since_last)


class SpecificBackupInformationEntity:
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
        """If adding/removing arguments, update backup_info_json_enc_dec."""
        self.backup_start_time_utc = backup_start_time_utc
        self.is_persistent_db_conn = is_persistent_db_conn
        self.backup_database_file_path = backup_database_file_path
        self.backup_base_name = backup_base_name
        self.specific_backup_name = specific_backup_name
        self.object_name_hash_salt = object_name_hash_salt
        self.backup_type = backup_type
        self.sbi_id = sbi_id
        self.all_file_info: list[BackupFileInformationEntityT] = None

    def get_backup_start_time_stamp_utc(self):
        return self.backup_start_time_utc.strftime(BACKUP_INFO_TIME_STAMP_FORMAT)

    def __len__(self):
        if self.all_file_info is None:
            raise BackupFileInformationNotInitialized(
                "Count of file information is not available. "
                "The file information has not been loaded or initialized."
            )
        return len(self.all_file_info)

    def append(self, file_info: BackupFileInformationEntity):
        if self.all_file_info is None:
            self.all_file_info = []
        self.all_file_info.append(file_info)

    def extend(self, file_info_list: list[BackupFileInformationEntity]):
        if self.all_file_info is None:
            self.all_file_info = []
        self.all_file_info.extend(file_info_list)


class BackupInformationDatabaseEntity:
    def __init__(
        self,
        is_persistent_db_conn: bool = False,
        backup_base_name: str = None,
        backup_info_dir: Union[str, Path] = None,
    ):
        self.is_persistent_db_conn = is_persistent_db_conn
        self.backup_base_name = backup_base_name
        if backup_info_dir:
            backup_info_dir = Path(backup_info_dir)
        self.backup_info_dir = backup_info_dir
        self.all_backup_info: dict = {
            CONFIG_VALUE_NAME_CONFIG_NAME: BACKUP_DATABASE_DEFAULT_NAME,
            CONFIG_VALUE_NAME_VERSION: BACKUP_INFO_MAJOR_VERSION_STRING,
            BACKUP_INFO_BACKUPS_SECTION_NAME: {},
        }
        self.backups: dict = self.all_backup_info[BACKUP_INFO_BACKUPS_SECTION_NAME]
        if self.backup_base_name is not None:
            self.backups[self.backup_base_name] = {}
        self.path_to_most_recent_bfi: dict[str, BackupFileInformationEntity] = None
        self.digest_to_bfi_list: defaultdict[str, list[BackupFileInformationEntity]] = None

    @property
    def db_base_filename(self):
        return f"{self.backup_base_name}{BACKUP_INFO_EXTENSION}"

    @property
    def primary_db_full_path(self):
        return self.backup_info_dir / self.db_base_filename

BackupFileInformationEntityT = TypeVar(
    "BackupFileInformationEntityT", bound=BackupFileInformationEntity
)

SpecificBackupInformationEntityT = TypeVar(
    "SpecificBackupInformationEntityT", bound=SpecificBackupInformationEntity
)

BackupInformationDatabaseEntityT = TypeVar(
    "BackupInformationDatabaseEntityT", bound=BackupInformationDatabaseEntity
)

def validate_bfi_backing_information(bfi: BackupFileInformationEntityT):
    if bfi.is_successful:
        if bfi.is_unchanged_since_last:
            raise InvalidStateError(
                f"Unexpected state: "
                f"Non-duplicate BackupFileInformation must not be unchanged since last: "
                f"path={bfi.path} "
                f"digest={bfi.primary_digest}"
            )
        if bfi.backing_fi is not None:
            raise InvalidStateError(
                f"Unexpected state: "
                f"Non-duplicate BackupFileInformation must not have backing file: "
                f"path={bfi.path} "
                f"digest={bfi.primary_digest}"
            )
        return
    if not bfi.is_unchanged_since_last:
        raise InvalidStateError(
            f"Unexpected state: "
            f"Duplicate BackupFileInformation must be unchanged since last: "
            f"path={bfi.path} "
            f"digest={bfi.primary_digest}"
        )
    if bfi.backing_fi is None:
        raise InvalidStateError(
            f"Unexpected state: "
            f"Duplicate BackupFileInformation must have backing file: "
            f"path={bfi.path} "
            f"digest={bfi.primary_digest}"
        )
    if bfi.primary_digest != bfi.backing_fi.primary_digest:
        raise InvalidStateError(
            f"Unexpected state: "
            f"Discovered BackupFileInformation digest must match: "
            f"bfi.path={bfi.path} "
            f"bfi.digest={bfi.primary_digest} "
            f"bfi.backing_fi.path={bfi.backing_fi.path} "
            f"bfi.backing_fi.digest={bfi.backing_fi.primary_digest}"
        )


def is_bfi_duplicate_info(
    deduplication_option: str,
    bfi: BackupFileInformationEntityT,
    digest: Union[bytes,str],
    modified_time_posix: float,
    size_in_bytes: int,
    ext: str,
) -> bool:
    if bfi is None:
        raise ValueError("a bfi must be specified.")
    if isinstance(digest, bytes):
        digest = digest.hex()
    is_check_ext = deduplication_option == ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST_EXT
    if bfi.primary_digest != digest:
        raise InvalidStateError(
            f"get_duplicate_file: The digests should not be different: "
            f"path1={bfi.path} primary_digest={bfi.primary_digest} "
            f"other_digest={digest}"
        )
    if (
        bfi.size_in_bytes == size_in_bytes
        and bfi.modified_time_posix == modified_time_posix
        and (
            not is_check_ext
            or (len(bfi.ext) != 0 and bfi.ext == ext)
        )
    ):
        # Duplicate discovered.
        return True
    # Duplicate not found.
    return False


def is_bfi_duplicate_bfi(
    deduplication_option: str,
    bfi: BackupFileInformationEntityT,
    cand_dup_bfi: BackupFileInformationEntityT,
) -> bool:
    if bfi is None or cand_dup_bfi is None:
        raise ValueError("a current and candidate bfi must be specified.")
    if bfi.primary_digest != cand_dup_bfi.primary_digest:
        # Digest sanity check failed.
        raise InvalidStateError(
            f"get_duplicate_file: The digests should not be different: "
            f"path1={bfi.path} path2={cand_dup_bfi.path}"
        )
    return is_bfi_duplicate_info(
        deduplication_option=deduplication_option,
        bfi=bfi,
        digest=cand_dup_bfi.primary_digest,
        size_in_bytes=cand_dup_bfi.size_in_bytes,
        modified_time_posix=cand_dup_bfi.modified_time_posix,
        ext=cand_dup_bfi.ext,
    )


def find_duplicate_in_list(
    deduplication_option: str,
    bfi: BackupFileInformationEntityT,
    dup_list: list[BackupFileInformationEntityT],
) -> BackupFileInformationEntityT:
    if not dup_list:
        return None
    for cand_dup_bfi in dup_list:
        if is_bfi_duplicate_bfi(
            deduplication_option=deduplication_option,
            bfi=bfi,
            cand_dup_bfi=cand_dup_bfi,
        ):
            return cand_dup_bfi
    return None


def is_bfi_modiifed(
    cur_bfi: BackupFileInformationEntityT,
    most_recent_backup_bfi: BackupFileInformationEntityT,
    check_digests: bool,
):
    if cur_bfi is None:
        raise ValueError("cur_bfi must be specified.")
    if most_recent_backup_bfi is None:
        return True
    if (cur_bfi.size_in_bytes != most_recent_backup_bfi.size_in_bytes
        or cur_bfi.modified_time_posix != most_recent_backup_bfi.modified_time_posix
    ):
        return True
    if not check_digests:
        return False
    if not cur_bfi.primary_digest or not most_recent_backup_bfi.primary_digest:
        assert ValueError("digests must be present to be checked.")
    return cur_bfi.primary_digest != most_recent_backup_bfi.primary_digest
