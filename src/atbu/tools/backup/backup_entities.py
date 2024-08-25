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
    CONFIG_VALUE_NAME_CONFIG_NAME,
    CONFIG_VALUE_NAME_VERSION,
)
from .exception import BackupFileInformationError
from ..persisted_info.file_info import FileInformation


class BackupFileInformationEntity(FileInformation):
    def __init__(self, path: Union[str, Path], discovery_path: Union[str, Path] = None, bfi_id: int = None):
        """If adding/removing arguments, update backup_info_json_enc_dec."""
        super().__init__(path=path)
        self.bfi_id = bfi_id
        self._path_without_root = os.path.splitdrive(path)[1]
        if self._path_without_root[0] in ["\\", "/"]:
            self._path_without_root = self._path_without_root[1:]
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

    @property
    def path_for_logging(self):
        if self.discovery_path is not None:
            return self.path_without_discovery_path
        return self.path_without_root

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
    def path_without_discovery_path(self):
        if self.discovery_path is None:
            raise BackupFileInformationError(
                f"The file information has no discovery path: {self.path}"
            )
        if not os.path.normcase(self.path).startswith(self.nc_discovery_path):
            raise BackupFileInformationError(
                f"The discovery path cannot be found: "
                f"disc_path={self.discovery_path} path={self.path}"
            )
        if os.path.normcase(self.path) == self.nc_discovery_path:
            return self.path
        return self.path[len(self.discovery_path) + 1 :]

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


class SpecificBackupInformationEntity:
    """Represents information of a specific backup session, which includes a list
    BackupFileInformation instances representing files that were backed up.
    """

    def __init__(
        self,
        backup_base_name: str = None,
        specific_backup_name: str = None,
        backup_start_time_utc: datetime = None,
        object_name_hash_salt: bytes = None,
        backup_type: str = None,
        sbi_id: int = None,
    ):
        """If adding/removing arguments, update backup_info_json_enc_dec."""
        self.backup_start_time_utc = backup_start_time_utc
        self.backup_base_name = backup_base_name
        self.specific_backup_name = specific_backup_name
        self.object_name_hash_salt = object_name_hash_salt
        self.backup_type = backup_type
        self.sbi_id = sbi_id
        self.all_file_info: list[BackupFileInformationEntityT] = []

    def get_backup_start_time_stamp_utc(self):
        return self.backup_start_time_utc.strftime(BACKUP_INFO_TIME_STAMP_FORMAT)

    def __len__(self):
        return len(self.all_file_info)

    def append(self, file_info: BackupFileInformationEntity):
        self.all_file_info.append(file_info)

    def extend(self, file_info_list: list[BackupFileInformationEntity]):
        self.all_file_info.extend(file_info_list)


class BackupInformationDatabaseEntity:
    def __init__(
        self,
        backup_base_name: str = None,
        backup_info_dir: Union[str, Path] = None,
    ):
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
        self.path_to_info_all: dict[str, BackupFileInformationEntity] = None
        self.path_to_info_last: dict[str, BackupFileInformationEntity] = None
        self.digest_to_list_info: defaultdict[
            str, list[BackupFileInformationEntity]
        ] = defaultdict(list[BackupFileInformationEntity])

    @property
    def backup_database_name(self) -> str:
        return self.all_backup_info[CONFIG_VALUE_NAME_CONFIG_NAME]

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
