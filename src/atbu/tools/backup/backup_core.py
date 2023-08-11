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
r"""Core backup classes/functions.
"""

from dataclasses import dataclass
import gzip
import io
from multiprocessing.connection import Connection
import os
from datetime import datetime, timezone
import re
import shutil
import tempfile
import time
from shutil import copy2
import logging
from pathlib import Path
from io import SEEK_SET
import multiprocessing
from multiprocessing.managers import SyncManager
from concurrent import futures
from concurrent.futures import (
    ALL_COMPLETED,
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
)
import queue
import json
from typing import BinaryIO, Callable, Iterator, Union
from collections import defaultdict
import struct

from atbu.common.simple_report import (
    FieldDef,
    SimpleReport,
)
from atbu.common.util_helpers import (
    convert_to_pathlib_path,
    create_numbered_backup_of_file,
    posix_timestamp_to_ISO8601_utc_stamp,
)
from atbu.common.multi_json_enc_dec import MultiEncoderDecoder
from atbu.mp_pipeline.mp_global import (
    get_process_pool_exec_init_func,
    get_process_pool_exec_init_args,
    ProcessThreadContextMixin,
    get_verbosity_level,
)
from atbu.mp_pipeline.mp_pipeline import (
    PipeConnectionIO,
    MultiprocessingPipeline,
    PipeConnectionMessage,
    SubprocessPipelineStage,
    ThreadPipelineStage,
    PipelineWorkItem,
)
from atbu.mp_pipeline.mp_helper import wait_futures_to_regulate
from atbu.common.hasher import (
    Hasher,
    DEFAULT_HASH_ALGORITHM,
)
from atbu.common.aes_cbc import (
    AES_CBC_Base,
    AesCbcPaddingEncryptor,
    AesCbcPaddingDecryptor,
)

from .constants import *
from .exception import *
from .global_hasher import GlobalHasherDefinitions
from .credentials import CredentialByteArray
from ..persisted_info.file_info import FileInformation
from .chunk_reader import (
    CHUNK_READER_CB_CIPHERTEXT,
    CHUNK_READER_CB_INPUT_BYTES_MANUAL_APPEND,
    open_chunk_reader,
)
from .storage_interface.base import (
    DEFAULT_MAX_SIMULTANEOUS_FILE_BACKUPS,
    StorageInterface,
    StorageInterfaceFactory,
)

BACKUP_INFO_STORAGE_PREFIX = f"zz-backup-info"

BACKUP_INFO_EXTENSION = f".{ATBU_ACRONYM}inf"
BACKUP_INFO_TEMP_EXTENSION = f".{ATBU_ACRONYM}inf.tmp"

BACKUP_INFO_MAJOR_VERSION = 0
BACKUP_INFO_MINOR_VERSION = 1
BACKUP_INFO_MAJOR_VERSION_STRING = (
    f"{BACKUP_INFO_MAJOR_VERSION}.{BACKUP_INFO_MINOR_VERSION:02}"
)
BACKUP_INFO_BACKUPS_SECTION_NAME = "backups"
BACKUP_INFO_BASE_NAME = "backup_base_name"
BACKUP_INFO_SPECIFIC_NAME = "backup_specific_name"
BACKUP_INFO_START_TIME_NAME = "backup_start_time_utc"
BACKUP_INFO_TIME_STAMP_FORMAT = "%Y%m%d-%H%M%S"
BACKUP_INFO_STORAGE_OBJECT_NAME_SALT = "object_name_hash_salt"
BACKUP_INFO_BACKUP_TYPE_NAME = "backup_type"
BACKUP_INFO_ALL_SECTION_NAME = "all"

BACKUP_OPERATION_NAME_BACKUP = "Backup"
BACKUP_OPERATION_NAME_RESTORE = "Restore"
BACKUP_OPERATION_NAME_VERIFY = "Verify"

BACKUP_PIPE_CMD_COMPRESSION_VIA_PIPE_ABORT = "CompViaPipe=False"
BACKUP_PIPE_CMD_COMPRESSION_VIA_PIPE_BEGIN = "CompViaPipe=True"

BACKUP_PIPELINE_STAGE_HASHING = 0
BACKUP_PIPELINE_STAGE_DECISIONS = 1
BACKUP_PIPELINE_STAGE_COMPRESSION = 2
BACKUP_PIPELINE_STAGE_BACKUP = 3


def _is_debug_logging():
    return logging.getLogger().getEffectiveLevel() >= logging.DEBUG


def _is_very_verbose_logging():
    return (
        get_verbosity_level() >= 2
        and logging.getLogger().getEffectiveLevel() >= logging.DEBUG
    )


class StorageDefinition:
    def __init__(
        self,
        storage_def_name,
        driver_factory: StorageInterfaceFactory,
        container_name: str,
        encryption_key: CredentialByteArray = None,
        storage_persisted_encryption_IV: bool = True,
        storage_persisted_backup_info: bool = True,
    ):
        self._storage_def_name = storage_def_name
        self.driver_factory = driver_factory
        self.encryption_key = encryption_key
        self.storage_persisted_encryption_IV = storage_persisted_encryption_IV
        self._encryption_used = False
        if self.encryption_key is not None:
            # If secrets are resolved, validate they are in the expected format.
            if self.encryption_key != CONFIG_KEY_VALUE_KEYRING_INDIRECTION:
                if not isinstance(self.encryption_key, CredentialByteArray):
                    raise ValueError(
                        f"Invalid encryption key, expecting CredentialByteArray."
                    )
                if len(self.encryption_key) * 8 not in ALLOWED_AES_KEY_BIT_LENGTHS:
                    raise ValueError(
                        f"Expecting encryption key of {ALLOWED_AES_KEY_BIT_LENGTHS}"
                    )
            self._encryption_used = True
        self._container_name = container_name
        if not self.driver_factory or not self._container_name:
            raise ValueError(
                f"Expected both a driver factory and container name for the storage definition."
            )
        self.storage_persisted_backup_info = storage_persisted_backup_info
        self._upload_chunk_size = None  # Lazy resolution via StorageInterface.
        self._download_chunk_size = None  # Lazy resolution via StorageInterface.

    @staticmethod
    def storage_def_from_dict(storage_def_name: str, storage_def_dict: dict):
        storage_interface_factory = StorageInterfaceFactory(
            storage_def_dict=storage_def_dict
        )
        encryption_key = None
        storage_persisted_encryption_IV = False
        encryption_section = storage_def_dict.get(CONFIG_SECTION_ENCRYPTION)
        if not encryption_section:
            logging.warning(
                f"The storage definition '{storage_def_name}' is *not* encrypted."
            )
        else:
            encryption_key = encryption_section.get(CONFIG_VALUE_NAME_ENCRYPTION_KEY)
            if encryption_key:
                logging.debug(f"Backup encryption key found.")
            else:
                raise ValueError(
                    f"Unexpected state: encryption section without key value: "
                    f"service_config_name={storage_def_name}"
                )
            storage_persisted_encryption_IV = encryption_section.get(
                CONFIG_VALUE_NAME_STORAGE_PERSISTED_IV
            )
            if storage_persisted_encryption_IV is None:
                storage_persisted_encryption_IV = (
                    CONFIG_STORAGE_PERSISTED_IV_DEFAULT_VALUE
                )
            if isinstance(storage_persisted_encryption_IV, bool):
                if not storage_persisted_encryption_IV:
                    logging.info(
                        f"You have chosen a non-standard option: "
                        f"The encryption IV will *not* be stored with each file."
                    )
                    logging.info(
                        f"Ensure you safeguard your local backup information files which "
                        f"contain the IVs along with your private key. Without the IVs, "
                        f"files cannot be restored from the backup."
                    )
            else:
                raise InvalidConfigurationValue(
                    f"The '{CONFIG_VALUE_NAME_STORAGE_PERSISTED_IV}' value should be "
                    f"either a bool 'true' or 'false'. "
                    f"Value={storage_persisted_encryption_IV} "
                    f"type={type(storage_persisted_encryption_IV)}"
                )
        storage_def = StorageDefinition(
            storage_def_name=storage_def_name,
            driver_factory=storage_interface_factory,
            container_name=storage_def_dict[CONFIG_VALUE_NAME_CONTAINER],
            encryption_key=encryption_key,
            storage_persisted_encryption_IV=storage_persisted_encryption_IV,
        )
        return storage_def

    def create_storage_interface(self) -> StorageInterface:
        return self.driver_factory.create_storage_interface()

    def _resolve_chunk_sizes(self):
        if self._upload_chunk_size is not None:
            return
        interface = self.create_storage_interface()
        self._upload_chunk_size = interface.upload_chunk_size
        self._download_chunk_size = interface.download_chunk_size
        if self._upload_chunk_size is None or self._download_chunk_size is None:
            raise InvalidStateError(f"Expected resolved chunk sizes but observe None.")

    @property
    def upload_chunk_size(self):
        self._resolve_chunk_sizes()
        return self._upload_chunk_size

    @property
    def download_chunk_size(self):
        self._resolve_chunk_sizes()
        return self._download_chunk_size

    @property
    def storage_def_name(self):
        return self._storage_def_name

    @property
    def is_encryption_used(self):
        return self._encryption_used

    @property
    def container_name(self):
        return self._container_name

    def create_encryptor(self):
        return AesCbcPaddingEncryptor(
            key=self.encryption_key, IV=os.urandom(AES_CBC_Base.BLOCK_SIZE)
        )

    def create_decryptor(self, IV):
        return AesCbcPaddingDecryptor(key=self.encryption_key, IV=IV)


class BackupFileInformation(FileInformation):
    def __init__(self, path: str, discovery_path: str = None):
        """If adding/removing arguments, update backup_info_json_enc_dec."""
        super().__init__(path=path)
        self._path_without_root = os.path.splitdrive(path)[1]
        if self._path_without_root[0] in ["\\", "/"]:
            self._path_without_root = self._path_without_root[1:]
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
        self.backing_fi: BackupFileInformation = None  # Not persisted
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

    def to_serialization_dict(self) -> dict:
        d = super().to_serialization_dict()
        d = d | {
            "_type": "BackupFileInformation",
            "_discovery_path": self._discovery_path,
            "is_successful": self.is_successful,
            "exception": self.exception
            if self.exception is None
            else str(self.exception),
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


class SpecificBackupInformation:
    """Represents backup information, essential a list of BackupFileInformation instances
    representing files that were backed up.

    The information can be in-memory within the instance, or saved/loaded from disk. See ach
    method for more details.

    General structure/schema:

        List of BackupFileInformation in memory or saved to an ATBU backup information file.

        Can hold information for one or more backups (even though below saves for one backup).

        Layout::

            {
                "name": "ATBU Backup Information",
                "version": "0.1",
                "backups": { // all backup information for this and any other backups
                    "<storage_def_name>": {
                        "<specific_backup_name_for_storage_def_name>": {
                            "all": [
                                BackupFileInformation instances
                            ]
                        }
                    }

                }
            }

    """

    def __init__(
        self,
        backup_base_name: str = None,
        specific_backup_name: str = None,
        backup_start_time_utc: datetime = None,
        object_name_hash_salt: bytes = None,
        backup_type: str = None,
    ):
        """If adding/removing arguments, update backup_info_json_enc_dec."""
        self.backup_start_time_utc = backup_start_time_utc
        self.backup_base_name = backup_base_name
        self.specific_backup_name = specific_backup_name
        self.object_name_hash_salt = object_name_hash_salt
        self.backup_type = backup_type
        self.all_file_info: list[BackupFileInformation] = []

    def get_backup_start_time_stamp_utc(self):
        return self.backup_start_time_utc.strftime(BACKUP_INFO_TIME_STAMP_FORMAT)

    def __len__(self):
        return len(self.all_file_info)

    def append(self, file_info: BackupFileInformation):
        self.all_file_info.append(file_info)

    def extend(self, file_info_list: list[BackupFileInformation]):
        self.all_file_info.extend(file_info_list)

    def save_to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as backup_info_file:
            backup_info_file.write(
                json.dumps(
                    self,
                    cls=backup_info_json_enc_dec.get_json_encoder_class(),
                    indent=4,
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


class BackupInformationDatabase:
    def __init__(
        self, backup_base_name: str = None, backup_info_dir: Union[str, Path] = None
    ):
        self.backup_base_name = backup_base_name
        self.backup_info_dir = convert_to_pathlib_path(backup_info_dir)
        self.all_backup_info: dict = {
            CONFIG_VALUE_NAME_CONFIG_NAME: f"{ATBU_ACRONUM_U} Backup Information",
            CONFIG_VALUE_NAME_VERSION: BACKUP_INFO_MAJOR_VERSION_STRING,
            BACKUP_INFO_BACKUPS_SECTION_NAME: {},
        }
        self.backups: dict = self.all_backup_info[BACKUP_INFO_BACKUPS_SECTION_NAME]
        if self.backup_base_name is not None:
            self.backups[self.backup_base_name] = {}
        self.path_to_info_all: dict[str, BackupFileInformation] = None
        self.path_to_info_last: dict[str, BackupFileInformation] = None
        self.digest_to_list_info: defaultdict[
            str, list[BackupFileInformation]
        ] = defaultdict(list[BackupFileInformation])

    def get_file_date_size_modified_state(
        self, cur_fi: BackupFileInformation
    ) -> tuple[bool, BackupFileInformation]:
        existing_fi = self.get_most_recent_backup_of_path(
            path_without_root=cur_fi.path_without_root
        )
        is_changed = True
        if (
            existing_fi is not None
            and cur_fi.size_in_bytes == existing_fi.size_in_bytes
            and cur_fi.modified_time_posix == existing_fi.modified_time_posix
        ):
            is_changed = False
        return is_changed, existing_fi

    def get_primary_digest_changed_info(
        self, cur_fi: BackupFileInformation
    ) -> tuple[bool, BackupFileInformation]:
        existing_fi = self.get_most_recent_backup_of_path(
            path_without_root=cur_fi.path_without_root
        )
        is_changed = True
        if (
            existing_fi is not None
            and cur_fi.primary_digest == existing_fi.primary_digest
        ):
            is_changed = False
        return is_changed, existing_fi

    def get_phys_backup_dup_list(
        self,
        cur_fi: BackupFileInformation,
    ) -> list[BackupFileInformation]:
        dup_list = self.digest_to_list_info.get(cur_fi.primary_digest)
        return dup_list

    def is_phys_backup_dup_exist(
        self,
        cur_fi: BackupFileInformation,
    ) -> bool:
        dup_list = self.get_phys_backup_dup_list(cur_fi=cur_fi)
        if dup_list is not None and len(dup_list) > 0:
            return True
        return False

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
            # Not changed or no history for path location.
            return (False, existing_fi)
        # File date/time and size are not changed.
        # If digests are mismatched, potentially sneaky corruption exists.
        return (cur_fi.primary_digest != existing_fi.primary_digest, existing_fi)

    def get_duplicate_file(
        self, deduplication_option: str, cur_fi: BackupFileInformation
    ) -> BackupFileInformation:
        """Given caller's deduplication_option and BackupFileInformation, return a discovered
        duplicate file.
        """
        dup_list = self.get_phys_backup_dup_list(cur_fi=cur_fi)
        if not dup_list:
            # Duplicate not found.
            return None
        is_check_ext = deduplication_option == ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST_EXT
        for dup_fi in dup_list:
            if cur_fi.primary_digest != dup_fi.primary_digest:
                # Digest sanity check failed.
                raise InvalidStateError(
                    f"get_duplicate_file: The digests should not be different: "
                    f"path1={cur_fi.path} path2={dup_fi.path}"
                )
            if (
                cur_fi.size_in_bytes == dup_fi.size_in_bytes
                and cur_fi.modified_time_posix == dup_fi.modified_time_posix
                and (
                    not is_check_ext
                    or (len(cur_fi.ext) != 0 and cur_fi.ext == dup_fi.ext)
                )
            ):
                # Return discovered duplicate.
                return dup_fi
        # Duplicate not found.
        return None

    def get_most_recent_backup_of_path(
        self, path_without_root
    ) -> BackupFileInformation:
        path = os.path.normcase(path_without_root)
        return self.path_to_info_all.get(path)

    def append(self, bi: SpecificBackupInformation, rebuild_indexes: bool = False):
        if self.backups.get(bi.backup_base_name) is None:
            if len(self.backups) > 0:
                # Multiple backup definitions could be supported per
                # file but current expectations is 1 per file.
                first_key = next(iter(self.backups.keys()))
                raise BackupInformationError(
                    f"The backup '{bi.backup_base_name}' is mismatched "
                    f"to existing backups such as '{first_key}'."
                )
            self.backups[bi.backup_base_name] = {}
        if self.backups[bi.backup_base_name].get(bi.specific_backup_name) is not None:
            raise BackupInformationError(
                f"The backup information for '{bi.specific_backup_name}' already exists."
            )
        self.backups[bi.backup_base_name][bi.specific_backup_name] = bi
        if rebuild_indexes:
            self._build_indexes()

    def get_specific_backup(
        self, specific_backup_name: str
    ) -> SpecificBackupInformation:
        """Returns a specific backup instance."""
        return self.backups[self.backup_base_name].get(specific_backup_name)

    def get_specific_backups(self) -> list[SpecificBackupInformation]:
        """Returns a list of specific backup instances in descending
        chronological order (most recent first).
        """
        b = sorted(
            [*self.backups[self.backup_base_name].values()],
            key=lambda s: s.backup_start_time_utc,
            reverse=True,
        )
        return b

    def _build_indexes(self):
        self.path_to_info_all: dict[str, BackupFileInformation] = {}
        self.path_to_info_last: dict[str, BackupFileInformation] = {}
        if len(self.backups) == 0:
            return
        # From most recent to oldest backup, build path_to_info. First set in path_to_info[path]
        # for given path wins (i.e., newest is reachable via the index).
        specific_backups: list[SpecificBackupInformation] = self.get_specific_backups()
        is_last_backup = True
        needs_backing_fi_dict: defaultdict[
            str, list[BackupFileInformation]
        ] = defaultdict(list[BackupFileInformation])
        needs_backing_fi_from_dedup: list[BackupFileInformation] = []
        for sb in specific_backups:
            sb_fi: BackupFileInformation
            for sb_fi in sb.all_file_info:

                # The backup info file currently tracks unsuccessful backups.
                # Do not use unsuccessful backup information for indexes.
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
                #   B) add the sb_fi to the digest_to_list_info (for later
                #      digest-based lookups, such as deduplication).
                #   C) index this sb_fi as needed.
                #

                #
                # A) Resolve any wanting fi:
                #
                # A normcase path_without_location_root is needed for indexing below.
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
                    # B) Index the digest for all sb_fi representing physical backups.
                    # For all sb_fi representing backups (is_unchanged_since_last==False),
                    # index its digest, add it to the digest's list.
                    self.digest_to_list_info[sb_fi.primary_digest].append(sb_fi)

                #
                # C) Index this sb_fi as needed:
                #
                if not self.path_to_info_all.get(nc_path_wo_root):
                    # This path not indexed already, so it is the first most recent, index it.
                    self.path_to_info_all[nc_path_wo_root] = sb_fi
                    if is_last_backup:
                        # Special case first iteration of 'for' captures 'last' backup info.
                        self.path_to_info_last[nc_path_wo_root] = sb_fi
            # After first iteration, last backup index handled.
            is_last_backup = False
        if len(needs_backing_fi_from_dedup) > 0:
            for needs_backing_fi in list(needs_backing_fi_from_dedup):
                # Find the duplicate using the same approach used when this file was backed up.
                dup_fi = self.get_duplicate_file(
                    deduplication_option=needs_backing_fi.deduplication_option,
                    cur_fi=needs_backing_fi,
                )
                if dup_fi:
                    assert needs_backing_fi.backing_fi is None
                    needs_backing_fi.backing_fi = dup_fi
                    needs_backing_fi_from_dedup.remove(needs_backing_fi)
        if len(needs_backing_fi_dict) > 0:
            failing_paths = [k for k in needs_backing_fi_dict.keys()]
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

    @property
    def db_base_filename(self):
        return f"{self.backup_base_name}{BACKUP_INFO_EXTENSION}"

    @property
    def primary_db_full_path(self):
        return self.backup_info_dir / self.db_base_filename

    def save_to_file(self, dest_backup_info_dir: Union[str, Path] = None):
        if not dest_backup_info_dir:
            dest_backup_info_dir = self.backup_info_dir
        else:
            dest_backup_info_dir = convert_to_pathlib_path(dest_backup_info_dir)
        backup_database_file_path = dest_backup_info_dir / self.db_base_filename
        create_numbered_backup_of_file(
            path=backup_database_file_path, not_exist_ok=True
        )
        with open(backup_database_file_path, "w", encoding="utf-8") as backup_info_file:
            backup_info_file.write(
                json.dumps(
                    self,
                    cls=backup_info_json_enc_dec.get_json_encoder_class(),
                    indent=4,
                )
            )

    @staticmethod
    def create_from_file(backup_base_name: str, backup_info_dir: Union[str, Path]):
        backup_info_dir: Path = convert_to_pathlib_path(backup_info_dir)
        backup_database_file_path: Path = (
            backup_info_dir / f"{backup_base_name}{BACKUP_INFO_EXTENSION}"
        )
        try:
            if not backup_database_file_path.exists():
                logging.info(
                    f"No backup history for '{backup_base_name}'. Creating new history database."
                )
                db = BackupInformationDatabase(
                    backup_base_name=backup_base_name, backup_info_dir=backup_info_dir
                )
                db.save_to_file(dest_backup_info_dir=backup_info_dir)
                db._build_indexes()  # pylint: disable=protected-access
                return db
            # Open/parse...
            with open(str(backup_database_file_path), "r", encoding="utf-8") as file:
                db: BackupInformationDatabase = json.load(
                    fp=file, cls=backup_info_json_enc_dec.get_json_decoder_class()
                )
            db.backup_base_name = backup_base_name
            db.backup_info_dir = backup_info_dir
            db._build_indexes()  # pylint: disable=protected-access
            return db
        except Exception as ex:
            raise BackupInformationError(
                f"Error parsing backup information file: "
                f"filename={backup_database_file_path} {exc_to_string(ex)}"
            ).with_traceback(ex.__traceback__) from ex

    def to_serialization_dict(self) -> dict:
        return self.all_backup_info

    def from_serialization_dict(self, d: dict):
        self.all_backup_info = d
        self.backups: dict = self.all_backup_info[BACKUP_INFO_BACKUPS_SECTION_NAME]
        self.path_to_info_all: dict[str, BackupFileInformation] = None
        self.path_to_info_last: dict[str, BackupFileInformation] = None
        self.digest_to_list_info: defaultdict[
            str, list[BackupFileInformation]
        ] = defaultdict(list[BackupFileInformation])


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


class BackupPipelineWorkItem(PipelineWorkItem):
    def __init__(
        self,
        operation_name: str,
        file_info: BackupFileInformation,
        is_qualified: bool = False,
        operation_runner: object = None,
    ) -> None:
        super().__init__(
            user_obj=None,
            auto_copy_attr=False,
        )
        self.operation_name = operation_name
        self.is_qualified = is_qualified
        self.file_info = file_info
        self.operation_runner = operation_runner
        self.compressed_size = None

    def __str__(self) -> str:
        the_str = super().__str__()
        return (
            the_str + f" oper={self.operation_name} is_q={self.is_qualified} "
            f"or={self.operation_runner} path={self.file_info.path}"
        )

    def stage_complete(
        self, stage_num: int, wi: "BackupPipelineWorkItem", ex: Exception
    ):
        super().stage_complete(stage_num, wi, ex)

        if self.operation_name == BACKUP_OPERATION_NAME_BACKUP:
            if stage_num == BACKUP_PIPELINE_STAGE_DECISIONS:
                self.is_qualified = wi.is_qualified
                self.operation_runner = wi.operation_runner
            elif stage_num == BACKUP_PIPELINE_STAGE_COMPRESSION:
                self.compressed_size = wi.file_info.compressed_size
                self.file_info.compressed_size = self.compressed_size
            elif stage_num == BACKUP_PIPELINE_STAGE_BACKUP:
                self.file_info = wi.file_info
                if self.file_info.compressed_size is not None:
                    self.file_info.compressed_size = self.compressed_size
        elif self.operation_name == BACKUP_OPERATION_NAME_RESTORE:
            self.file_info = wi.file_info  # Currently only a single stage.
        elif self.operation_name == BACKUP_OPERATION_NAME_VERIFY:
            self.file_info = wi.file_info  # Currently only a single stage.


class BackupSyncManager(SyncManager):
    pass


class BackupNameReservations:
    def __init__(self, mp_manager: BackupSyncManager):
        self.reserved_names: dict = mp_manager.dict()
        self.lock = mp_manager.Lock()

    def reserve_name(self, name) -> bool:
        with self.lock:
            if name in self.reserved_names:
                return False
            self.reserved_names[name] = 1
            return True

    def unreserve_name(self, name) -> bool:
        with self.lock:
            if name not in self.reserved_names:
                return False
            del self.reserved_names[name]
            return True


class ProxyIterator:
    """Wrap our BackupQueueIterator instances in this proxy to expose
    only the iterator methods to certain cloud APIs. Specifically,
    libcloud will condition behavior based on hasattr queries, where
    we wish for libcloud not to see 'read' as one example. This proxy
    can be optionally requested by the StorageInterface instances or
    whomever as needed (see BackupQueueIterator for details).
    """

    def __init__(self, orig_stream):
        self.orig_stream = orig_stream

    def __iter__(self):
        return self

    def __next__(self):
        return self.orig_stream.__next__()


class BackupQueueIterator:
    """Iterator serving up chunks fed via the put method."""

    WRITER_MAX_QUEUED_CHUNKS = 5

    def __init__(self, chunk_size, feedback_func: Callable[[int, int], None] = None):
        self._chunk_size = chunk_size
        self._min_chunk_size_observed = self._chunk_size  # Default to maximum allowed.
        self.queue = queue.Queue(maxsize=BackupQueueIterator.WRITER_MAX_QUEUED_CHUNKS)
        self.end_of_stream = False
        self.pending_error = None
        self.total_bytes = 0
        self.in_progress = False
        self.cur_seek_pos = 0
        self.last_chunk = None  # not currently used.
        self.is_last_chunk_next = False  # not currently used.
        self.feedback_func = feedback_func

    @property
    def chunk_size(self):
        return self._chunk_size

    def put(self, chunk: bytes, block=True, timeout=None):
        if self.end_of_stream:
            raise StopIteration(
                f"End of stream already observed, cannot put more chunks."
            )
        if len(chunk) > self._chunk_size:
            raise BackupException(
                f"Chunk being put is larger than max/default chunk size of {self._chunk_size}."
            )
        if len(chunk) > self._min_chunk_size_observed:
            raise BackupException(
                f"Chunk being put is {len(chunk)} which is larger than minimum observed of "
                f"{self._min_chunk_size_observed}, breaking chunk write size assumptions."
            )
        if self._min_chunk_size_observed < self._chunk_size and len(chunk) != 0:
            raise BackupException(
                f"Chunk being written is len={len(chunk)} which is non-zero "
                f"in size after already writing a chunk of "
                f"{self._min_chunk_size_observed} bytes which is less than "
                f"the maximum of {self._chunk_size} bytes."
            )
        self.queue.put(item=chunk, block=block, timeout=timeout)
        self._min_chunk_size_observed = len(chunk)

    def tell(self):
        return self.cur_seek_pos

    def seek(self, offset, whence):
        if self.is_last_chunk_next:
            raise BackupException(
                f"BackupQueueIterator.seek was already called "
                f"to rewind back to the last chunk read."
            )
        if self.last_chunk is None:
            raise BackupException(
                f"BackupQueueIterator.seek only supports seeking for retry which "
                f"can only happen after at least one chunk as already been read."
            )
        if whence != SEEK_SET:
            raise BackupException(
                f"BackupQueueIterator.seek only supports SEEK_SET "
                f"to the prior chunk first byte position."
            )
        size_seek_from_cur_pos = self.cur_seek_pos - offset
        if size_seek_from_cur_pos != len(self.last_chunk):
            raise BackupException(
                f"Attempt to seek from {self.cur_seek_pos} to {offset} which would be "
                f"{size_seek_from_cur_pos} bytes when last chunk size was {len(self.last_chunk)}."
            )
        self.cur_seek_pos = offset
        self.is_last_chunk_next = True

    def set_pending_error(self, pending_error):
        self.pending_error = pending_error

    def __iter__(self):
        return self

    def __next__(self):
        if self.pending_error:
            pe = self.pending_error
            self.pending_error = None
            raise BackupException(pe)
        self.in_progress = False
        if self.end_of_stream:
            raise StopIteration("No more chunks.")
        self.last_chunk = None
        self.is_last_chunk_next = False
        if self.feedback_func:
            self.feedback_func(self.total_bytes)
        chunk = self.queue.get(block=True)
        if not chunk:
            self.end_of_stream = True
            raise StopIteration("No more chunks.")
        self.total_bytes += len(chunk)
        self.cur_seek_pos += len(chunk)
        self.last_chunk = chunk
        logging.debug(
            f"BackupQueueIterator: bytes={len(chunk)} total_bytes={self.total_bytes}"
        )
        self.in_progress = True
        return chunk

    def read(self, size=-1):
        # TODO: We added this read method after testing libcloud, where libcloud multipart will
        # use read first if available, and if that's the case, then libcloud determines the
        # chunk size which may differ from outside. We likely need to dyn delete the read method
        # for libcloud usage.
        if size != self._chunk_size:
            raise BackupException(
                f"Cannot read chunk size of {size} bytes, only chunk sizes of "
                f"{self._chunk_size} are allowed."
            )
        return self.__next__()

    def get_iterator_only_proxy(self):
        return ProxyIterator(self)


class BackupStorageWriter(ProcessThreadContextMixin):
    RETRY_DEFAULT_DELAY_SECONDS = 1
    RETRY_BACKUP_MULTIPLIER = 2
    RETRY_MAX_DELAY_SECONDS = 30

    def __init__(
        self,
        source_path: str,
        queue_iterator: BackupQueueIterator,
        storage_def: StorageDefinition,
        object_name_hash_salt: bytes,
        object_name_reservations: BackupNameReservations,
        force_object_name: str = None,
    ):
        super().__init__()
        self.source_path = source_path
        self.object_name = force_object_name
        self.queue_iterator = queue_iterator
        self.storage_def = storage_def
        self.object_name_hash_salt = object_name_hash_salt
        self.object_name_reservations = object_name_reservations

    def run(self):
        try:
            logging.debug(
                f"BackupStorageWriter: {self.get_exec_context_log_stamp_str()} "
                f"path={self.source_path}"
            )

            logging.debug(f"Creating storage driver...")
            storage_interface = self.storage_def.create_storage_interface()

            # Retry loop
            # If is_retry_okay is True, allow retry, else exit while "retry" loop
            # Generally, is_retry_okay==True only around network I/O operations that
            # can be affected by transient network failures.
            is_retry_okay = False
            retry_delay = BackupStorageWriter.RETRY_DEFAULT_DELAY_SECONDS
            while True:

                try:
                    is_retry_okay = True
                    container = storage_interface.get_container(
                        container_name=self.storage_def.container_name
                    )
                    is_retry_okay = False

                    # If caller did not specify a specific object name in advance...
                    if self.object_name is None:
                        #
                        # Create a name for the storage object.
                        #
                        # The basis for the storage name will be a hash of the file path.
                        # Use of object_name_hash_salt is to remove the ease with which
                        # a path name can be deduced from a direct hash of the storage name.
                        #
                        _, path_without_drive_letter = os.path.splitdrive(
                            self.source_path
                        )
                        hasher: Hasher = GlobalHasherDefinitions().create_hasher()
                        hasher.update_all(self.object_name_hash_salt)
                        hasher.update_all(path_without_drive_letter.encode())
                        source_path_hash = hasher.get_primary_hexdigest()
                        if self.storage_def.is_encryption_used:
                            extension = ATBU_FILE_BACKUP_EXTENSION_ENCRYPTED
                        else:
                            extension = ATBU_FILE_BACKUP_EXTENSION
                        candidate_name = f"{source_path_hash}{extension}"
                        logging.debug(
                            f"candidate_name={candidate_name} for path={self.source_path}"
                        )
                    else:
                        candidate_name = self.object_name
                    counter = 0
                    while True:
                        try:
                            if self.object_name_reservations.reserve_name(
                                candidate_name
                            ):
                                is_retry_okay = True
                                o = container.get_object(candidate_name)
                                is_retry_okay = False
                                #
                                # candidate_name was found so is not available for use.
                                #
                                logging.debug(
                                    f"{candidate_name} already exists: cloud_size={o.size}"
                                )
                                self.object_name_reservations.unreserve_name(
                                    candidate_name
                                )
                            else:
                                logging.debug(
                                    f"{candidate_name} already reserved by "
                                    f"sibling backup."
                                )
                            counter += 1
                            if counter > 1000:
                                # Given candidate_name is hash of path, "
                                # this limit should not be reached.
                                raise BackupException(
                                    f"Could not find a unique file name."
                                )
                            candidate_name = (
                                f"{source_path_hash}-{counter:03}{extension}"
                            )
                        except ObjectDoesNotExistError:
                            #
                            # candidate_name is available for use.
                            #
                            break
                    try:
                        storage_interface.upload_stream_to_object(
                            container=container,
                            object_name=candidate_name,
                            stream=self.queue_iterator,
                            source_path=self.source_path,
                        )
                        # Successful upload, remove name from reservation list.
                        # Names left at end were failed backups.
                        # Need to avoid retry above after upload attempt given
                        # iterator is only good once.
                        # Consider propagating to outer BackupFile(...) retry.
                        self.object_name_reservations.unreserve_name(candidate_name)
                        # Success, exit retry.
                        self.object_name = candidate_name
                        return candidate_name
                    except Exception as ex:
                        logging.error(
                            f"Backup failed, deleting any partial object: "
                            f"name={candidate_name} {exc_to_string(ex)}"
                        )
                        try:
                            container.delete_object(candidate_name)
                            # TODO: Track partial names that cannot be deleted
                            # for later deletion (exclude if reused during retry).
                        except Exception as ex2:
                            logging.warning(
                                f"Could not delete object of failed backup: {exc_to_string(ex2)}"
                            )
                        raise

                except Exception as ex:
                    logging.error(f"Backup writer error: {exc_to_string(ex)}")
                    if not is_retry_okay:
                        logging.error(
                            f"Backup retry is not allowed: {exc_to_string(ex)}"
                        )
                        raise
                    is_retry_okay = False
                    if not isinstance(ex, storage_interface.retry_exceptions):
                        raise
                    logging.warning(
                        f"Retry-eligible backup failure. "
                        f"Waiting {retry_delay} seconds before retry."
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * BackupStorageWriter.RETRY_BACKUP_MULTIPLIER,
                        BackupStorageWriter.RETRY_MAX_DELAY_SECONDS,
                    )
                    logging.warning(f"Retrying operation now...")
        except Exception as ex:
            logging.error(
                f"BackupStorageWriter: "
                f"ERROR: Backup of {self.source_path} failed, "
                f"cannot retry: {exc_to_string(ex)}"
            )
            raise


_PREAMBLE_HASHAGLO_MACRO = "{hashalgo}"
_PREAMBLE_FIELD_COMPRESSION = "z"
_PREAMBLE_FIELDS = [
    ("v", lambda fi: "1"),
    (
        _PREAMBLE_FIELD_COMPRESSION,
        lambda fi: BACKUP_COMPRESSION_TYPE
        if (
            (fi.is_compressed is not None and fi.is_compressed)
            or fi.compressed_file_path is not None
            or fi.compressed_size is not None
        )
        else BACKUP_COMPRESSION_NONE,
    ),
    (_PREAMBLE_HASHAGLO_MACRO, lambda fi: fi.primary_digest),
    ("size", lambda fi: fi.size_in_bytes),
    ("modified", lambda fi: fi.modified_time_posix),
    ("accessed", lambda fi: fi.accessed_time_posix),
    ("path", lambda fi: fi.path_without_root),
]

_NUM_PREAMBLE_FIELDS = len(_PREAMBLE_FIELDS)


def parse_backup_file_preamble(preamble) -> tuple[dict, int]:
    """Parse preamble bytes into a dictionary with the kv pairs.
    Return a tuple of dict, total_preamble_size, where total_preamble_size
    can be used by caller to advance to the start of the file's data.
    """
    preamble_size = struct.unpack_from("<H", preamble, 0)[0]
    total_size_needed = preamble_size + 2  # 2 bytes for preamble_size.
    total_size_with_padding = (
        int((total_size_needed + AES_CBC_Base.BLOCK_SIZE) / AES_CBC_Base.BLOCK_SIZE)
        * AES_CBC_Base.BLOCK_SIZE
    )
    preamble_string_encoded: bytes = struct.unpack_from(
        f"<{preamble_size}s", preamble, 2
    )[0]
    preamble_dict = dict(
        kv_pair.split(sep="=", maxsplit=1)
        for kv_pair in preamble_string_encoded.decode().split(
            sep=",", maxsplit=_NUM_PREAMBLE_FIELDS - 1
        )
    )
    if preamble_dict.get(_PREAMBLE_FIELD_COMPRESSION) is None:
        preamble_dict[_PREAMBLE_FIELD_COMPRESSION] = BACKUP_COMPRESSION_NONE
    return preamble_dict, total_size_with_padding


def create_backup_file_preamble(file_info: BackupFileInformation) -> bytes:
    """Create a byte array containing the preamble to go into the header
    of the backed up file. The premable byte array is padded up to the
    nearest AES_CBC_Base.BLOCK_SIZE (16 bytes).
    """
    preamble_string_parts = []
    for preamble_field in _PREAMBLE_FIELDS:
        if len(preamble_string_parts) > 0:
            preamble_string_parts.append(",")
        field_name = preamble_field[0]
        if field_name == _PREAMBLE_HASHAGLO_MACRO:
            field_name = GlobalHasherDefinitions().get_primary_hashing_algo_name()
        preamble_string_parts.append(f"{field_name}={preamble_field[1](file_info)}")
    preamble_string_encoded = "".join(preamble_string_parts).encode()
    preamble_size = len(preamble_string_encoded)
    if preamble_size > 0xFFFF:
        raise Exception(
            f"Preamble bytes must be less than or equal to {0xFFFF} bytes in length."
        )
    total_size_needed = preamble_size + 2  # 2 bytes for preamble_size itself.
    total_size_with_padding = (
        int((total_size_needed + AES_CBC_Base.BLOCK_SIZE) / AES_CBC_Base.BLOCK_SIZE)
        * AES_CBC_Base.BLOCK_SIZE
    )
    preamble_bytearray = bytearray(total_size_with_padding)
    struct.pack_into(
        f"<H{preamble_size}s",
        preamble_bytearray,
        0,
        preamble_size,
        preamble_string_encoded,
    )
    return preamble_bytearray


BACKUP_HEADER_VERSION = 0x01
BACKUP_HEADER_OPTION_IV_INCLUDED = 0x01


def create_backup_file_header(
    encryption_IV: bytes = None,
    option_flags: int = 0,
    version: int = BACKUP_HEADER_VERSION,
) -> bytes:
    header_size = 2  # 1 byte for version, 1 byte for option flags.
    if encryption_IV:
        if not isinstance(encryption_IV, bytes):
            raise ValueError(f"The encryption_IV should be bytes.")
        # Encryption IV itself plus a prefixed length byte.
        header_size += 1 + len(encryption_IV)
        # Despite not assuming length, assert on block size to enforce today's known fixed size.
        if len(encryption_IV) != AES_CBC_Base.BLOCK_SIZE:
            raise BackupFileHeaderInvalid(
                f"Expected caller encryption IV to be {AES_CBC_Base.BLOCK_SIZE} "
                f"bytes but is {len(encryption_IV)} instead."
            )
        option_flags |= BACKUP_HEADER_OPTION_IV_INCLUDED
    header_bytearray = bytearray(header_size)
    struct.pack_into("BB", header_bytearray, 0, version, option_flags)
    if encryption_IV:
        if option_flags & BACKUP_HEADER_OPTION_IV_INCLUDED == 0:
            raise BackupFileHeaderInvalid(
                f"Expected BACKUP_HEADER_OPTION_IV_INCLUDED flag to be set."
            )
        struct.pack_into(
            f"B{len(encryption_IV)}s",
            header_bytearray,
            2,
            len(encryption_IV),
            encryption_IV,
        )
    return bytes(header_bytearray)


def parse_backup_file_header(
    raw_header: Union[bytes, bytearray]
) -> tuple[int, int, int, bytes]:
    if len(raw_header) < 2:
        raise BackupFileHeaderInvalid(
            f"The backup file header should be at least 2 bytes."
        )
    version, option_flags = struct.unpack_from("BB", raw_header, 0)
    size_consumed = 2
    encryption_IV = None
    if option_flags & BACKUP_HEADER_OPTION_IV_INCLUDED:
        if len(raw_header) < 3:
            raise BackupFileHeaderInvalid(
                f"The backup file header does not include the expected IV length byte."
            )
        (IV_length,) = struct.unpack_from("B", raw_header, 2)
        size_consumed += 1
        # Remove of change this check as needed if block size changes.
        if IV_length != AES_CBC_Base.BLOCK_SIZE:
            raise BackupFileHeaderInvalid(f"The IV length of {IV_length} is invalid.")
        if len(raw_header) < 3 + IV_length:
            raise BackupFileHeaderInvalid(
                f"The raw_header with length {len(raw_header)} "
                f"not enough for IV of length {IV_length}."
            )
        (encryption_IV,) = struct.unpack_from(f"{IV_length}s", raw_header, 3)
        size_consumed += IV_length
    return size_consumed, version, option_flags, encryption_IV


class BackupFile(ProcessThreadContextMixin):
    def __init__(
        self,
        file_info: BackupFileInformation,
        storage_def: StorageDefinition,
        object_name_hash_salt: bytes,
        object_name_reservations: BackupNameReservations,
        perform_cleartext_hashing: bool,
        is_dryrun: bool,
    ):
        super().__init__()
        self.thread_exec = None
        self.file_info = file_info
        self.storage_def = storage_def
        self.backup_queue_iterator = None
        self.writer_future = None
        self.object_name_hash_salt = object_name_hash_salt
        self.object_name_reservations = object_name_reservations
        self.perform_cleartext_hashing = perform_cleartext_hashing
        self.is_dryrun = is_dryrun

    def get_compression_decision(
        self,
        pipe_input_file: PipeConnectionIO,
    ) -> bool:
        if pipe_input_file is not None:
            msg = pipe_input_file.recv_message()
            if msg.cmd == BACKUP_PIPE_CMD_COMPRESSION_VIA_PIPE_BEGIN:
                return True
        return False

    def get_compression_pipe_input_file(
        self,
        pipe_conn: Connection,
    ) -> tuple[PipeConnectionIO, int]:
        if pipe_conn is not None:
            pipe_input_file = PipeConnectionIO(pipe_conn, is_write=False)
            is_compression = self.get_compression_decision(
                pipe_input_file=pipe_input_file
            )
            if is_compression:
                return (
                    pipe_input_file,
                    pipe_input_file.fileno(),
                )
            pipe_input_file.close()
        return (
            None,
            -1,
        )

    def run(self, wi: BackupPipelineWorkItem):
        try:
            path = self.file_info.path

            if self.is_dryrun:
                logging.info(f"(dry run) BackupFile: Completed {path}")
                self.file_info.is_successful = True
                return (self.file_info, None)

            path_to_backup = path
            if self.file_info.compressed_file_path is not None:
                path_to_backup = self.file_info.compressed_file_path
            total_size_in_bytes = self.file_info.size_in_bytes
            last_percent_reported = None
            if path == path_to_backup:
                logging.debug(
                    f"BackupFile: {self.get_exec_context_log_stamp_str()} path={path}"
                )
            else:
                logging.debug(
                    f"BackupFile: {self.get_exec_context_log_stamp_str()} "
                    f"path={path} compressed={path_to_backup}"
                )
            self.thread_exec = ThreadPoolExecutor(
                thread_name_prefix="BackupStorageWriter"
            )

            def feedback(total_bytes_processed):
                nonlocal path
                nonlocal total_size_in_bytes
                nonlocal last_percent_reported
                if total_size_in_bytes == 0:
                    percent = 100
                else:
                    percent = int(
                        (
                            min(total_bytes_processed, total_size_in_bytes)
                            / total_size_in_bytes
                        )
                        * 100
                    )
                if last_percent_reported is None or (percent / 10) > (
                    last_percent_reported / 10
                ):
                    last_percent_reported = percent
                    logging.info(f"{percent: >3}% completed of {path}")

            upload_chunk_size = self.storage_def.upload_chunk_size

            self.backup_queue_iterator = BackupQueueIterator(
                chunk_size=upload_chunk_size,
                feedback_func=feedback,
            )
            enc = None
            hasher_ciphertext = None
            if self.storage_def.is_encryption_used:
                enc: AesCbcPaddingEncryptor = self.storage_def.create_encryptor()
                self.file_info.encryption_IV = enc.IV
                hasher_ciphertext = GlobalHasherDefinitions().create_hasher()
            hasher_cleartext = None
            if self.perform_cleartext_hashing:
                hasher_cleartext = GlobalHasherDefinitions().create_hasher()
            total_bytes_read_from_file = 0

            def perform_hashing_callback(what, data):
                nonlocal total_bytes_read_from_file
                nonlocal hasher_ciphertext
                nonlocal hasher_cleartext
                if what == CHUNK_READER_CB_CIPHERTEXT:
                    if hasher_ciphertext:
                        hasher_ciphertext.update_all(data)
                elif what == CHUNK_READER_CB_INPUT_BYTES_MANUAL_APPEND:
                    total_bytes_read_from_file += len(data)
                    if hasher_cleartext:
                        hasher_cleartext.update_all(data)
                elif what == CHUNK_READER_CB_INPUT_BYTES_MANUAL_APPEND:
                    pass  # ignore preamble data for plaintext hashing.

            pipe_input_file, pipe_input_fileno = self.get_compression_pipe_input_file(
                pipe_conn=wi.pipe_conn
            )

            self.file_info.is_compressed = pipe_input_file is not None

            with open_chunk_reader(
                chunk_size=upload_chunk_size,
                path=path_to_backup,
                fileobj=pipe_input_file,
                read_without_size=pipe_input_file is not None,
                encryptor=enc,
                user_func=perform_hashing_callback,
            ) as chunk_reader:

                self.writer_future = self.thread_exec.submit(
                    BackupStorageWriter.run,
                    BackupStorageWriter(
                        source_path=path,
                        queue_iterator=self.backup_queue_iterator,
                        storage_def=self.storage_def,
                        object_name_hash_salt=self.object_name_hash_salt,
                        object_name_reservations=self.object_name_reservations,
                        force_object_name=self.file_info.storage_object_name,
                    ),
                )

                #
                # Insert at start the cleartext backup file header.
                # This contains at least version and option flags (2 bytes) but
                # may also include the encryption IV if desired by the user (per the storage def).
                #
                backup_file_header: bytes = None
                if enc and self.storage_def.storage_persisted_encryption_IV:
                    backup_file_header = create_backup_file_header(encryption_IV=enc.IV)
                else:
                    backup_file_header = create_backup_file_header()
                chunk_reader.queue_data(
                    bytes_to_queue=backup_file_header, do_not_encrypt=True
                )

                # Insert preamble before writing data.
                # It is effectively the backup file header.
                preamble = create_backup_file_preamble(self.file_info)
                chunk_reader.queue_data(bytes_to_queue=preamble)

                # Read chunk size bytes from reader, breaking out of loop
                # as soon as less than chunk size is read, where final
                # bytes handled outside loop further below...
                while True:
                    try:
                        logging.debug(
                            f"BackupFile: fileno={pipe_input_fileno}: waiting for next chunk."
                        )
                        file_bytes = chunk_reader.read_chunk()
                        logging.debug(
                            f"BackupFile: fileno={pipe_input_fileno}: "
                            f"Processing file_bytes={len(file_bytes)}"
                        )
                    except OSError as ex:
                        logging.error(
                            f"BackupFile: Error: fileno={pipe_input_fileno}: "
                            f"backing up {path} {exc_to_string(ex)}"
                        )
                        raise
                    except BaseException as ex:
                        logging.error(
                            f"BackupFile: Error: fileno={pipe_input_fileno}: "
                            f"backing up {path} {exc_to_string(ex)}"
                        )
                        raise
                    if len(file_bytes) < upload_chunk_size:
                        logging.debug(
                            f"EOF detected due to reading {len(file_bytes)} bytes which is less "
                            f"than chunk size {upload_chunk_size} bytes."
                        )
                        break
                    # This loop only 'puts' chunk size bytes, nothing more/less.
                    # We break out of loop to handle the final blocks/writes.
                    if len(file_bytes) != upload_chunk_size:
                        raise BackupException(
                            f"The resolved chunk size of {len(file_bytes)} "
                            f"bytes is not equal to the expected chunk size of "
                            f"{upload_chunk_size} bytes."
                        )
                    logging.debug(
                        f"BackupFile: Putting processed file_bytes={len(file_bytes)}"
                    )
                    self.put_with_future_check(chunk=file_bytes)
                    logging.debug(f"BackupFile: Queued file_bytes={len(file_bytes)}")
            logging.debug(f"BackupFile: Writing final bytes/EOF for {path} ...")
            self.put_with_future_check(chunk=file_bytes)
            if len(file_bytes) > 0:
                self.put_with_future_check(bytes())  # EOF
            if self.writer_future and not self.writer_future.done():
                logging.debug(f"Waiting for dependent worker to complete.")
                self.file_info.storage_object_name = self.writer_future.result()
                logging.debug(
                    f"Dependent worker completed: storage_name={self.file_info.storage_object_name}"
                )
            else:
                logging.debug(f"Dependent worker already completed.")
            logging.info(f"BackupFile: Completed {path}")
            logging.info(f"  Total bytes .............. {total_bytes_read_from_file}")
            if hasher_cleartext:
                logging.info(
                    f"  SHA256 original file ..... "
                    f"{hasher_cleartext.get_hexdigests()[DEFAULT_HASH_ALGORITHM]}"
                )
            backing_fi_digest_indicator = ""
            if self.file_info.is_backing_fi_digest:
                backing_fi_digest_indicator = "(assumed)"
            logging.info(
                f"  SHA256 original file ..... "
                f"{self.file_info.primary_digest} {backing_fi_digest_indicator}"
            )
            if self.storage_def.is_encryption_used:
                logging.info(
                    f"  SHA256 encrypted file .... "
                    f"{hasher_ciphertext.get_hexdigests()[DEFAULT_HASH_ALGORITHM]}"
                )
            logging.info(f"---")
            if hasher_cleartext:
                self.file_info.primary_digest = hasher_cleartext.get_hexdigests()[
                    DEFAULT_HASH_ALGORITHM
                ]
            if self.storage_def.is_encryption_used:
                self.file_info.is_backup_encrypted = True
                self.file_info.ciphertext_hash_during_backup = (
                    hasher_ciphertext.get_hexdigests()[DEFAULT_HASH_ALGORITHM]
                )
            self.file_info.is_successful = True
            return (self.file_info, None)
        except Exception as ex:
            self.file_info.exception = ex
            self.file_info.is_successful = False
            logging.error(
                f"BackupFile: FAILURE: {self.get_exec_context_log_stamp_str()} "
                f"path={path} {exc_to_string(ex)}"
            )
            return (self.file_info, ex)
        finally:
            if wi.pipe_conn is not None:
                wi.pipe_conn.close()
                wi.pipe_conn = None
            logging.debug(
                f"{self.our_thread_name}: "
                f"Completed: is_successful={self.file_info.is_successful} {path}"
            )

    def put_with_future_check(self, chunk):
        start_put = time.perf_counter()
        while True:
            # Check consumer, raise exception if error detected.
            if self.writer_future.done():
                exception = self.writer_future.exception()
                logging.error(
                    f"BackupFile.put_with_future_check: "
                    f"Unexpected completion of BackupStorageWriter: "
                    f"exception={exception}"
                )
                if exception:
                    raise BackupException(
                        f"BackupFile.put_with_future_check: "
                        f"Backup failed during BackupStorageWriter processing, "
                        f"see inner exception. "
                        f"path={self.file_info.path} ex={exception}",
                        exception,
                    ).with_traceback(exception.__traceback__) from exception
                else:
                    raise BackupException(
                        f"Unexpected termination of BackupStorageWriter. path={self.file_info.path}"
                    ).with_traceback()
            try:
                # Put chunk. If queue full due to consumer being tied up,
                # check future again (above) and try putting again.
                self.backup_queue_iterator.put(chunk=chunk, block=True, timeout=5)
                break
            except queue.Full:
                # This only logs warnings after 60 seconds.
                # Since each iteration of the loop
                # checks the queue-consuming future, we rely
                # on its failure to abort... or something
                # more major such as user CTRL-C abort to stop
                # attempts. At a later time we can always add
                # terminate abort timeout or some such if needed.
                current_wait_secs = time.perf_counter() - start_put
                if current_wait_secs > 60 and current_wait_secs % 30 == 0:
                    logging.warning(
                        f"BackupFile: Queue to BackupStorageWriter "
                        f"still full after {current_wait_secs} seconds."
                    )


class BackupResultsManager:
    """BackupResultsManager performs the following duties:
    The constructor establishes the specific name of the backup, which
    includes UTC start time.

    This BackupResultsManager accepts results from BackupFile Future
    instances as they complete.

    This BackupResultsManager periodically uses SpecificBackupInformation
    to save the results to a temp file.

    After backup completes, this BackupResultsManager finalizes the results
    (aka backup information) by using SpecificBackupInformation to save the
    final results (tmp to non-tmp file).
    """

    BACKUP_INFORMATION_SAVE_INTERVAL_SECONDS = 60

    def __init__(
        self,
        backup_info_db: BackupInformationDatabase,
        storage_def_name: str,
        object_name_hash_salt: bytes,
        backup_type: str,
        primary_backup_info_dir: str,
        secondary_backup_info_dirs: list[str],
        is_dryrun: bool,
    ):
        # pylint: disable=line-too-long
        """Construct BackupResultsManager which manages results during the backup.

        At the end of the backup, creates a backup information info with details about a
        particular backup...

        Backup info file name: f"{storage_def_name}-YYYYMMDD-HHMMSS{BACKUP_INFO_EXTENSION}"
        Example: MyBackup-20220503-072647.atbuinf

        The primary .atbuinf file is stored in primary_backup_info_dir, and secondary copies will
        be stored in each of secondary_backup_info_dirs.

        General flow relating to this class:
        ThreadA: BackupFile instances --> create --> backup results --> sent_to --> BackupResultsManager.extend_temp_results --> temp result list
        ThreadB: BackupResultsManager.background_save --> periodically calls move_results_temp_to_final_list_and_save to move temp results to final results.
        ThreadA at end of backup calls SpecificBackupInformation.save_final_revision to save final result list.

        ThreadA is not created by this instance, but is a BackupFile instance's thread calling into this instance to supply its results.
        ThreadB is created and maintained by this instance and is responsible for periodic saving of the .atbuinf.
        """
        self.is_dryrun = is_dryrun

        if not backup_info_db:
            raise ValueError(f"The backup_info_db must be specified.")
        self.backup_info_db = backup_info_db

        if not storage_def_name:
            raise ValueError(f"The storage_def_name must be specified.")

        #
        # Ensure the primary_backup_info_dir was supplied, can be created as, or is already a directory.
        #
        if not primary_backup_info_dir:
            raise ValueError(f"The primary_backup_info_dir must be specified.")
        primary_backup_info_dir: Path = Path(primary_backup_info_dir)
        if primary_backup_info_dir.is_file():
            raise ValueError(
                f"The backup info dir is a file. backup_info_dir={str(primary_backup_info_dir)}"
            )
        primary_backup_info_dir.mkdir(exist_ok=True)
        if not primary_backup_info_dir.is_dir():
            raise ValueError(
                f"Cannot create backup info directory. backup_info_dir={str(primary_backup_info_dir)}"
            )

        if not object_name_hash_salt:
            raise ValueError(f"The object_name_hash_salt must be specified.")

        #
        # Start time of backup.
        #
        self.backup_start_time_utc = datetime.now(timezone.utc)

        #
        # The specific name for this backup.
        #
        specific_backup_name = (
            f"{storage_def_name}-{self.backup_start_time_utc.strftime('%Y%m%d-%H%M%S')}"
        )

        #
        # The backup information file name for this backup.
        #
        self.backup_info_file = (
            primary_backup_info_dir / f"{specific_backup_name}{BACKUP_INFO_EXTENSION}"
        )

        #
        # Primary parameters validated/setup, assign to self.
        #
        self._backup_base_name = storage_def_name
        self._specific_backup_name = specific_backup_name
        self.backup_info_dir: Path = primary_backup_info_dir
        self.secondary_backup_info_dirs: list[str] = secondary_backup_info_dirs
        self.backup_info_file_tmp = self.backup_info_file.with_suffix(
            BACKUP_INFO_TEMP_EXTENSION
        )
        self.is_dirty_for_tmp = False
        self.tmp_results: list[BackupFileInformation] = list()
        self.final_results = SpecificBackupInformation(
            backup_base_name=self._backup_base_name,
            specific_backup_name=self._specific_backup_name,
            backup_start_time_utc=self.backup_start_time_utc,
            object_name_hash_salt=object_name_hash_salt,
            backup_type=backup_type,
        )
        self.lock = multiprocessing.Lock()
        self.thread_stop_event = multiprocessing.Event()
        self.thread_exec = ThreadPoolExecutor(
            thread_name_prefix=f"BackupResultsManager-{specific_backup_name}"
        )
        self.background_save_thread_future = self.thread_exec.submit(
            BackupResultsManager.background_save, self
        )

    @property
    def backup_base_name(self):
        return self._backup_base_name

    @property
    def specific_backup_name(self):
        return self._specific_backup_name

    def stop(self):
        if self.background_save_thread_future:
            self.thread_stop_event.set()
            logging.info(f"Waiting for backup information to be saved...")
            self.background_save_thread_future.result()
            self.background_save_thread_future = None

    @staticmethod
    def background_save(o):
        is_stop_initiated = False
        try:
            while not is_stop_initiated:
                is_stop_initiated = o.thread_stop_event.wait(
                    BackupResultsManager.BACKUP_INFORMATION_SAVE_INTERVAL_SECONDS
                )
                if is_stop_initiated:
                    logging.info(
                        f"SpecificBackupInformation thread stop initiated. Finishing up..."
                    )
                results_available = 0
                with o.lock:
                    results_available = len(o.tmp_results)
                if results_available > 0:
                    o.move_results_temp_to_final_list_and_save()
            o.save_final_revision()
        except Exception as ex:
            logging.error(
                f"SpecificBackupInformation thread exception detected: {exc_to_string(ex)}"
            )
            raise
        finally:
            logging.info(f"SpecificBackupInformation background thread ending.")

    def extend_temp_results(self, results: list[BackupFileInformation]):
        if isinstance(results, BackupFileInformation):
            results = [results]
        if not isinstance(results, list):
            raise ValueError(
                f"extend_temp_results requires either a BackupFileInformation "
                f"or a list[BackupFileInformation]."
            )
        if len(results) == 0:
            return
        if not isinstance(results[0], BackupFileInformation):
            raise ValueError(
                f"list should contain only BackupFileInformation instances."
            )
        with self.lock:
            self.tmp_results.extend(results)
            self.is_dirty_for_tmp = True

    def move_results_temp_to_final_list_and_save(self):
        was_dirty = False
        with self.lock:
            was_dirty = self.is_dirty_for_tmp
            if self.is_dirty_for_tmp:
                self.final_results.extend(self.tmp_results)
                self.tmp_results.clear()
                self.is_dirty_for_tmp = False
        if was_dirty:
            logging.info(
                f"Saving in-progress backup information: {self.backup_info_file_tmp}"
            )
            save_start = time.perf_counter()
            self.final_results.save_to_file(path=str(self.backup_info_file_tmp))
            save_seconds = time.perf_counter() - save_start
            logging.info(
                f"Saving backup information complete: "
                f"It took {save_seconds:.3f} seconds to write "
                f"{self.backup_info_file_tmp}"
            )

    def save_final_revision(self):
        if self.is_dryrun:
            logging.info(f"*** Dry run, not saving backup information.")
            self.backup_info_file_tmp.unlink(missing_ok=True)
            return
        logging.info(f"Saving backup info file: {self.backup_info_file}")
        # Save final individual backup into final per-backup file.
        self.final_results.save_to_file(path=self.backup_info_file)
        # Add the backup info to the db, save the db.
        self.backup_info_db.append(bi=self.final_results)
        self.backup_info_db.save_to_file()
        logging.info(f"Backup info file saved: {self.backup_info_file}")
        logging.debug(f"Removing temp backup info file: {self.backup_info_file_tmp}")
        self.backup_info_file_tmp.unlink(missing_ok=True)
        if self.secondary_backup_info_dirs is not None and isinstance(
            self.secondary_backup_info_dirs, list
        ):
            for sbid in self.secondary_backup_info_dirs:
                logging.info(f"Copying primary {self.backup_info_file} to {sbid}...")
                copy2(src=self.backup_info_file, dst=sbid)
                self.backup_info_db.save_to_file(dest_backup_info_dir=sbid)


@dataclass
class BackupAnomaly(Anomaly):
    file_info: BackupFileInformation = None


def get_anomalies_report(anomalies: list[BackupAnomaly]) -> list[str]:
    report_lines = []
    max_kind = 0
    max_exception_name = 0
    max_path = 0
    for anomaly in anomalies:
        max_kind = max(len(anomaly.kind), max_kind)
        if isinstance(anomaly.exception, Exception):
            max_exception_name = max(
                len(type(anomaly.exception).__name__), max_exception_name
            )
        max_path = max(len(anomaly.file_info.path), max_path)
    field_defs = [
        FieldDef(header="Type", max_width=min(max(len("Type"), max_kind), 20)),
        FieldDef(
            header="Exception",
            max_width=min(max(len("Exception"), max_exception_name), 40),
        ),
        FieldDef(header="Path", max_width=min(max(len("Path"), max_path), 40)),
        FieldDef(header="Message", max_width=60),
    ]
    sr = SimpleReport(field_defs=field_defs)
    report_lines.extend(sr.render_report_header())
    report_header_line_count = len(report_lines)
    for anomaly in anomalies:
        path = (
            anomaly.file_info.path
            if anomaly.file_info is not None
            else "<unknown or N/A>"
        )
        exception_name = (
            type(anomaly.exception).__name__ if anomaly.exception is not None else ""
        )
        message = anomaly.message if anomaly.message is not None else ""
        if len(message) == 0 and isinstance(anomaly.exception, Exception):
            message = (
                exc_to_string(anomaly.exception)
                if anomaly.exception is not None
                else ""
            )
        detail_lines = sr.render_detail_lines(
            detail_line_data=[anomaly.kind, exception_name, path, message]
        )
        if len(report_lines) > report_header_line_count:
            report_lines.append("")
        report_lines.extend(detail_lines)
    return report_lines


def log_anomalies_report(anomalies: list[BackupAnomaly]):
    if len(anomalies) == 0:
        return
    logging.error(f"*******************************************")
    logging.error(f"*** The following errors were detected: ***")
    logging.error(f"*******************************************")
    for report_line in get_anomalies_report(anomalies=anomalies):
        logging.error(report_line)


def file_operation_future_result(
    f: Future,
    anomalies: list[BackupAnomaly],
    the_operation: str,
    is_dryrun: bool = False,
):
    """Evaluate one future result which will return a BackupFileInformation
    instance from the future if deemed successful, else it will return None
    but will add error information to the anomalies list.

    The string the_operation is the first string of the first sentence of
    error messages, choose one to your liking. For example, if
    the_operation="Backup" a message might then start "Backup failed...".
    """

    dryrun_str = "(dry run) " if is_dryrun else ""

    # From the future, usually always expecting a result tuple
    # as follows:
    #
    #       tuple[0]: BackupFileInformation
    #       tuple[1]: Any uncaught exception, so usually
    #                 this is None, even in cases where
    #                 the BackupFileInformation has its
    #                 exception field set.

    if f.exception():
        #
        # Non-typical: A direct Future exception, something went
        # really wrong in an unexpected or uncaught manner.
        #
        msg = (
            f"{the_operation} failed: "
            f"Got unexpected Future exception without file information. "
            f"Error occurred: {exc_to_string(f.exception())}"
        )
        logging.error(msg)
        anomalies.append(
            BackupAnomaly(
                kind=ANOMALY_KIND_EXCEPTION, exception=f.exception(), message=msg
            )
        )
        return None

    if f.cancelled():
        #
        # Non-typical: We do not currently cancel so this should not generally happen.
        #
        anomalies.append((None, "cancelled", None))
        msg = (
            f"{the_operation} failed: "
            f"Got unexpected Future Cancellation without file information."
        )
        logging.error(msg)
        anomalies.append(BackupAnomaly(kind=ANOMALY_KIND_CANCELLED, message=msg))
        return None

    wi: BackupPipelineWorkItem = f.result()
    if isinstance(wi.file_info, BackupFileInformation):
        #
        # The most expected kind of result, a 2 element tuple
        # (BackupFileInformation,Exception | None)
        #
        file_info: BackupFileInformation = wi.file_info
        if file_info.is_successful and file_info.exception is None and not wi.is_failed:
            #
            # Most typical and successful case:
            # The BackupFileInformation is marked successful.
            # The BackupFileInformation has no record of an exception.
            # The second tuple element is None.
            #
            logging.info(f"{dryrun_str}{the_operation} succeeded: {file_info.path_for_logging}")
            return file_info

        if (
            wi.operation_name == BACKUP_OPERATION_NAME_BACKUP
            and not wi.is_qualified
            and file_info.is_unchanged_since_last
            and file_info.exception is None
            and not wi.is_failed
        ):
            logging.info(
                f"{the_operation} not needed, unchanged: {file_info.path_for_logging}"
            )
            return None

        if file_info.exception:
            #
            # Most typical type of exception error condition, where
            # the BackupFileInformation has a tracked exception. This
            # tracked exception should match tuple Exception.
            #
            msg = (
                f"{the_operation} failed: "
                f"Error occurred: {exc_to_string(file_info.exception)}"
            )
            logging.error(msg)
            anomalies.append(
                BackupAnomaly(
                    kind=ANOMALY_KIND_EXCEPTION,
                    file_info=file_info,
                    exception=file_info.exception,
                    message=msg,
                )
            )
            return file_info

        if wi.exceptions is not None:
            #
            # Non-typical... an exception with BackupFileInformation
            # exception was not set. Something caused a caught exception
            # which did not update the BackupFileInformation instance. (bug)
            #
            if not isinstance(wi.exceptions, list):
                raise InvalidStateError(
                    f"Expecting a list of exceptions but got {type(wi.exceptions)}"
                )
            for ex in wi.exceptions:
                msg = (
                    f"{the_operation} failed: "
                    f"Did not expect Future.exception() to return exception. "
                    f"path={file_info.path} Error occurred: {exc_to_string(ex)}"
                )
                logging.error(msg)
                anomalies.append(
                    BackupAnomaly(
                        kind=ANOMALY_KIND_EXCEPTION,
                        file_info=file_info,
                        exception=ex,
                        message=msg,
                    )
                )
            return file_info

        #
        # Non-typical: There is file information but no indication of failure/exception.
        #
        msg = (
            f"{the_operation} failed: "
            f"No exception or successful state detected. "
            f"Unexpected state for {file_info.path}"
        )
        logging.error(msg)
        anomalies.append(
            BackupAnomaly(
                kind=ANOMALY_KIND_UNEXPECTED_STATE,
                file_info=file_info,
                message=msg,
            )
        )
        return file_info

    msg = (
        f"{the_operation} failed: "
        f"The work item did not have the expected file info."
    )
    logging.error(msg)
    anomalies.append(BackupAnomaly(kind=ANOMALY_KIND_UNEXPECTED_STATE, message=msg))
    return None


def file_operation_futures_to_results(
    fs: set,
    fi_list: list[BackupFileInformation],
    anomalies: list[BackupAnomaly],
    the_operation: str,
    is_dryrun: bool = False,
) -> list[BackupFileInformation]:
    """Check all futures in fs, add any resulting file_info to the fi_list,
    record any errors to anomalies list. Return the resulting fi_list.
    """
    f: Future
    for f in set(fs):
        if not f.done():
            continue

        fs.remove(f)

        fi = file_operation_future_result(
            f=f,
            anomalies=anomalies,
            the_operation=the_operation,
            is_dryrun=is_dryrun,
        )

        if fi is not None:
            fi_list.append(fi)

    return fi_list


class HasherPipelineStage(SubprocessPipelineStage):
    def __init__(self) -> None:
        super().__init__()

    def is_for_stage(self, pwi: BackupPipelineWorkItem) -> bool:
        return True

    def perform_stage_work(
        self,
        pwi: BackupPipelineWorkItem,
        **kwargs,
    ):
        max_attempts = 5
        try:
            pwi.file_info.refresh_digests(max_attempts=max_attempts)
            return pwi
        except FileChangedWhileCalculatingHash as ex:
            logging.error(
                f"After {max_attempts} attempts, cannot hash the file, "
                f"file changed while hashing: {exc_to_string(ex)}"
            )
            raise


class GzipFileWrapper(gzip.GzipFile):
    # pylint: disable=useless-super-delegation
    def __init__(
        self, filename=None, mode=None, compresslevel=9, fileobj=None, mtime=None
    ):
        super().__init__(
            filename=filename,
            mode=mode,
            compresslevel=compresslevel,
            fileobj=fileobj,
            mtime=mtime,
        )
        self.compressed_bytes = 0

    def __enter__(self) -> object:
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return super().__exit__(exc_type, exc_val, exc_tb)

    def write(self, data):
        self.compressed_bytes += len(data)
        if _is_very_verbose_logging():
            logging.debug(
                f"GzipFileWrapper: writing {len(data)} of data to compression: path={self.filename}"
            )
        return super().write(data)


class CompressionPipelineStage(SubprocessPipelineStage):
    def __init__(
        self,
        compression_settings: dict,
        upload_chunk_size: int,
        backup_temp_dir: str,
        ext_to_abort_count_dict: dict,
        ext_to_ratio: dict,
        shared_lock: multiprocessing.Lock,
        is_dryrun: bool,
    ) -> None:
        super().__init__()
        self.is_dryrun = is_dryrun
        self.compression_settings = compression_settings
        self.upload_chunk_size = (upload_chunk_size,)
        self.backup_temp_dir = backup_temp_dir
        self.compression_level = self.compression_settings[
            CONFIG_VALUE_NAME_COMPRESSION_LEVEL
        ]
        self.is_compression_active = self.compression_level != BACKUP_COMPRESSION_NONE
        self.no_compress_pat = os.path.normcase(
            self.compression_settings[CONFIG_VALUE_NAME_NO_COMPRESS_PATTERN]
        )
        self.compress_min_file_size = int(
            self.compression_settings[CONFIG_VALUE_NAME_COMPRESS_MIN_FILE_SIZE]
        )
        self.compress_min_compress_ratio = float(
            self.compression_settings[CONFIG_VALUE_NAME_MIN_COMPRESS_RATIO]
        )
        self.compress_max_ftype_attempts = int(
            self.compression_settings[CONFIG_VALUE_NAME_MAX_FTYPE_ATTEMPTS]
        )
        self.ext_to_poor_ratio_count = ext_to_abort_count_dict  # dict[str,int]()
        self.ext_to_ratio = ext_to_ratio  # dict[str,float]()
        self.shared_lock = shared_lock
        self.output_file = None

    @property
    def is_pipe_with_next_stage(self):
        return self.is_compression_active

    def is_for_stage(self, pwi: BackupPipelineWorkItem) -> bool:
        return (
            self.compression_level != BACKUP_COMPRESSION_NONE
            and pwi.is_qualified
            and not self.is_dryrun
        )

    def update_compression_stats(
        self,
        fi: BackupFileInformation,
    ):
        nc_ext = os.path.normcase(fi.ext)
        compressed_size = fi.compressed_size
        compression_ratio = compressed_size / fi.size_in_bytes
        is_compression_poor = compression_ratio > self.compress_min_compress_ratio
        with self.shared_lock:
            compression_ratio_avg = self.ext_to_ratio.get(nc_ext)
            if compression_ratio_avg is None:
                compression_ratio_avg = compression_ratio
            else:
                compression_ratio_avg = (compression_ratio_avg + compression_ratio) / 2
            self.ext_to_ratio[nc_ext] = compression_ratio_avg
            if is_compression_poor:
                if len(nc_ext) > 0:
                    poor_ratio_count = self.ext_to_poor_ratio_count.get(nc_ext)
                    if poor_ratio_count is None:
                        poor_ratio_count = 0
                    poor_ratio_count += 1
                    self.ext_to_poor_ratio_count[nc_ext] = poor_ratio_count
                else:
                    poor_ratio_count = (
                        -1
                    )  # No extension, not tracked, still abort, logged below.
        if is_compression_poor:
            logging.debug(
                f"Tracked inefficient compression: "
                f"ext={nc_ext} ext_count={poor_ratio_count} "
                f"orig_size={fi.size_in_bytes} "
                f"comp_size={compressed_size} "
                f"ratio={compression_ratio} "
                f"path={fi.path}"
            )

    def is_no_compress_file(
        self,
        fi: BackupFileInformation,
    ):
        return re.match(self.no_compress_pat, fi.nc_path) is not None

    def has_file_poorly_compressed_to_many_times(
        self,
        fi: BackupFileInformation,
    ):
        nc_ext = os.path.normcase(fi.ext)
        if len(nc_ext) > 0:
            with self.shared_lock:
                abort_count = self.ext_to_poor_ratio_count.get(nc_ext)
            if (
                abort_count is not None
                and abort_count >= self.compress_max_ftype_attempts
            ):
                logging.debug(
                    f"Skipping compression for extension, "
                    f"more than {self.compress_max_ftype_attempts} "
                    f"poor compression results: "
                    f"path={fi.path}"
                )
                return True

    def is_file_below_compress_size_threshold(
        self,
        fi: BackupFileInformation,
    ):
        if fi.size_in_bytes < self.compress_min_file_size:
            logging.debug(
                f"Skipping compression for file less than {self.compress_min_file_size} bytes: "
                f"path={fi.path}"
            )
            return True

    def compress_to_output_file(
        self,
        fi: BackupFileInformation,
        output_file: io.RawIOBase,
    ):
        output_fileno = output_file.fileno()
        try:
            read_size = 35 * 1024 * 1024
            with (
                open(file=fi.path, mode="rb") as input_file,
                GzipFileWrapper(  # gzip.GzipFile(
                    mode="wb",
                    fileobj=output_file,
                ) as output_gzip_file,
            ):
                while True:
                    b = input_file.read(read_size)
                    if len(b) == 0:
                        break
                    if _is_very_verbose_logging():
                        logging.debug(
                            f"Sending {len(b)} bytes through compression to "
                            f"fileno={output_fileno}: path={fi.path}"
                        )
                    output_gzip_file.write(b)

            fi.compressed_size = self.get_compressed_size()

            if self.is_pipe_with_next_stage and hasattr(output_file, "write_eof"):
                output_file.write_eof(bytes())

            if _is_debug_logging():
                logging.debug(
                    f"Compression complete: orig_size={fi.size_in_bytes} "
                    f"comp_size={fi.compressed_size} fileno={output_fileno} "
                    f"path={fi.path}"
                )
        except Exception as ex:
            logging.error(
                f"Compression failed: fileno={output_fileno} path={fi.path} {exc_to_string(ex)}"
            )
            raise

    def get_compressed_size(self):
        if self.is_pipe_with_next_stage:
            return self.output_file.num_bytes
        else:
            return self.output_file.tell()

    def get_output_file(
        self,
        pwi: BackupPipelineWorkItem,
    ) -> BinaryIO:
        fi = pwi.file_info
        if self.output_file is not None:
            return self.output_file
        if self.is_pipe_with_next_stage:
            self.output_file = PipeConnectionIO(c=pwi.pipe_conn, is_write=True)
            if _is_debug_logging():
                logging.debug(
                    f"Compression avenue: "
                    f"orig_size={fi.size_in_bytes} "
                    f"path={fi.path} --> pipe"
                )
        else:
            temp_file_fd, temp_file_path = tempfile.mkstemp(
                prefix="atbu_z_", dir=self.backup_temp_dir, text=False
            )
            if _is_debug_logging():
                logging.debug(
                    f"Compressing avenue: orig_size={fi.size_in_bytes} "
                    f"path={fi.path} --> dest={temp_file_path}"
                )
            self.output_file = io.FileIO(file=temp_file_fd, mode="wb", closefd=True)
            fi.compressed_file_path = temp_file_path
        return self.output_file

    def inform_abort_compression(
        self,
        pwi: BackupPipelineWorkItem,
    ):
        if not self.is_pipe_with_next_stage or pwi.pipe_conn is None:
            if _is_debug_logging():
                logging.debug(f"no need to inform abort compression: wi={str(pwi)}")
            return
        if _is_debug_logging():
            logging.debug(f"inform abort compression: wi={str(pwi)}")
        o: PipeConnectionIO = self.get_output_file(pwi)
        if not isinstance(o, PipeConnectionIO):
            raise InvalidStateError(f"Expected PipeConnectionIO but got {type(o)}.")
        o.send_message(
            msg=PipeConnectionMessage(cmd=BACKUP_PIPE_CMD_COMPRESSION_VIA_PIPE_ABORT)
        )

    def inform_begin_compression(
        self,
        pwi: BackupPipelineWorkItem,
    ):
        if not self.is_pipe_with_next_stage or pwi.pipe_conn is None:
            if _is_debug_logging():
                logging.debug(f"no need to inform begin compression: wi={str(pwi)}")
            return
        if _is_debug_logging():
            logging.debug(f"inform begin compression: wi={str(pwi)}")
        o: PipeConnectionIO = self.get_output_file(pwi)
        if not isinstance(o, PipeConnectionIO):
            raise InvalidStateError(f"Expected PipeConnectionIO but got {type(o)}.")
        o.send_message(
            msg=PipeConnectionMessage(cmd=BACKUP_PIPE_CMD_COMPRESSION_VIA_PIPE_BEGIN)
        )

    def perform_stage_work(
        self,
        pwi: BackupPipelineWorkItem,
        **kwargs,
    ):
        if _is_debug_logging():
            logging.debug(f"perform_stage_work: " f"ENTER: wi={str(pwi)}")
        try:
            if self.is_pipe_with_next_stage and pwi.pipe_conn is None:
                raise InvalidStateError(
                    f"perform_stage_work: "
                    f"Expected pipe connection because "
                    f"is_pipe_with_next_stage is True. wi={str(pwi)}"
                )

            if not self.is_compression_active:
                return pwi

            fi = pwi.file_info

            if self.is_no_compress_file(fi=fi):
                if _is_debug_logging():
                    logging.debug(
                        f"perform_stage_work: is_no_compress_file==True wi={str(pwi)}"
                    )
                self.inform_abort_compression(pwi=pwi)
                return pwi

            if self.has_file_poorly_compressed_to_many_times(fi=fi):
                if _is_debug_logging():
                    logging.debug(
                        f"perform_stage_work: "
                        f"has_file_poorly_compressed_to_many_times==True wi={str(pwi)}"
                    )
                self.inform_abort_compression(pwi=pwi)
                return pwi

            if self.is_file_below_compress_size_threshold(fi=fi):
                if _is_debug_logging():
                    logging.debug(
                        f"perform_stage_work: "
                        f"is_file_below_compress_size_threshold==True wi={str(pwi)}"
                    )
                self.inform_abort_compression(pwi=pwi)
                return pwi

            #
            # Compress to output file.
            #
            self.inform_begin_compression(pwi=pwi)
            self.compress_to_output_file(fi=fi, output_file=self.output_file)
            self.update_compression_stats(fi=fi)
        except Exception as ex:
            fi.compressed_file_path = None
            pwi.append_exception(ex)
            logging.error(
                f"Exception during compression pipeline stage. wi={str(pwi)} {exc_to_string(ex)}"
            )
        finally:
            if self.output_file is not None and not self.output_file.closed:
                self.output_file.close()
            if pwi.pipe_conn is not None and not pwi.pipe_conn.closed:
                pwi.pipe_conn.close()
            pwi.pipe_conn = None
            if _is_debug_logging():
                logging.debug(f"perform_stage_work: EXIT: wi={str(pwi)}")
        return pwi


def is_qualified_for_operation(wi: BackupPipelineWorkItem):
    return wi.is_qualified


def run_operation_stage(wi: BackupPipelineWorkItem):
    if wi.operation_runner is None:
        raise InvalidStateError(f"The operation runner is None.")
    # In case BackupFile sets any attributes to
    # values that cannot be picked, set it to None.
    operation_runner = wi.operation_runner
    wi.operation_runner = None
    # The old way of returning results via the
    # future was as shown tuple[file_info,Exception].
    # TODO: This can be changed given 'wi' is passed in.
    fi, ex = operation_runner.run(wi)
    fi.exception = ex
    wi.file_info = fi
    if isinstance(ex, Exception):
        wi.append_exception(ex)
    return wi


class Backup:

    MAX_SIMULTANEOUS_FILES = DEFAULT_MAX_SIMULTANEOUS_FILE_BACKUPS

    def __init__(
        self,
        backup_type: str,
        deduplication_option: str,
        compression_settings: dict,
        sneaky_corruption_detection: bool,
        primary_backup_info_dir: str,
        secondary_backup_info_dirs: list[str],
        source_file_info_list: list[BackupFileInformation],
        storage_def: StorageDefinition,
        is_dryrun: bool,
    ) -> None:
        self.is_dryrun = is_dryrun
        if not source_file_info_list or not isinstance(source_file_info_list, list):
            raise ValueError(f"source_files must be a list.")
        if not isinstance(storage_def, StorageDefinition):
            raise ValueError(f"The storage_def must be a StorageDefinition.")
        if backup_type not in ATBU_BACKUP_TYPE_ALL:
            raise ValueError(f"Invalid backup type '{backup_type}'.")
        self._backup_type = backup_type
        self._deduplication_option = deduplication_option
        self._compression_settings = compression_settings
        self._temp_dir = tempfile.mkdtemp(prefix="atbu_bktmp_")
        self._sneaky_corruption_detection = sneaky_corruption_detection
        self._source_files = source_file_info_list
        self._object_name_hash_salt = os.urandom(32)
        self._backup_history = BackupInformationDatabase.create_from_file(
            backup_base_name=storage_def.storage_def_name,
            backup_info_dir=primary_backup_info_dir,
        )
        self._results_mgr: BackupResultsManager = BackupResultsManager(
            backup_info_db=self._backup_history,
            storage_def_name=storage_def.storage_def_name,
            object_name_hash_salt=self._object_name_hash_salt,
            backup_type=self._backup_type,
            primary_backup_info_dir=primary_backup_info_dir,
            secondary_backup_info_dirs=secondary_backup_info_dirs,
            is_dryrun=self.is_dryrun,
        )
        self._unchanged_skipped_files: list[BackupFileInformation] = list()
        self._storage_def = storage_def
        self._mp_manager = BackupSyncManager()
        self._mp_manager.start()
        self._object_name_hash_salt = os.urandom(32)
        self._object_name_reservations = BackupNameReservations(self._mp_manager)
        self.anomalies: list[BackupAnomaly] = []
        self.success_count = 0
        self._subprocess_pipeline = MultiprocessingPipeline(
            name="Backup",
            max_simultaneous_work_items=min(os.cpu_count() // 2, 15),
            process_initfunc=get_process_pool_exec_init_func(),
            process_initargs=get_process_pool_exec_init_args(),
        )
        self._subprocess_pipeline.add_stage(stage=HasherPipelineStage())
        self._subprocess_pipeline.add_stage(
            ThreadPipelineStage(
                fn_determiner=lambda pwi: True,
                fn_worker=self._post_hasher_decision_making,
            )
        )
        if self.is_dryrun:
            # For dry run, do not create compression stage, but keep backup stage which will return
            # success without performing a backup.
            logging.info(f"*** Dry run, will not perform compression or backup work.")
        self._compression_stage = CompressionPipelineStage(
            compression_settings=self._compression_settings,
            backup_temp_dir=self._temp_dir,
            upload_chunk_size=self.storage_def.upload_chunk_size,
            ext_to_abort_count_dict=multiprocessing.Manager().dict(),
            ext_to_ratio=multiprocessing.Manager().dict(),
            shared_lock=multiprocessing.Manager().Lock(),  # pylint: disable=no-member
            is_dryrun=self.is_dryrun,
        )
        self._subprocess_pipeline.add_stage(
            stage=self._compression_stage,
        )
        self._subprocess_pipeline.add_stage(
            SubprocessPipelineStage(
                fn_determiner=is_qualified_for_operation,
                fn_worker=run_operation_stage,
            )
        )
        self._is_used = False

    def shutdown(self):
        if self._results_mgr:
            self._results_mgr.stop()
        if self._subprocess_pipeline is not None:
            self._subprocess_pipeline.shutdown()
        try:

            def on_error(_, path, exc_info):
                value = ""
                if (
                    exc_info is not None
                    and len(exc_info) >= 3
                    and exc_info[2] is not None
                ):
                    value = f" ({exc_info[2]})"
                logging.warning(f"Failed to delete temp file: {path}{value}")

            if (
                self._temp_dir is not None
                and len(self._temp_dir) > 0
                and os.path.isdir(self._temp_dir)
            ):
                shutil.rmtree(
                    path=self._temp_dir, ignore_errors=False, onerror=on_error
                )
        except Exception as ex:
            logging.error(
                f"Unhandled exception while cleaning up the backup temp folder: "
                f"{self._temp_dir} ex={ex}"
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False

    @property
    def storage_def(self) -> StorageDefinition:
        return self._storage_def

    def _handle_sneaky_corruption_detection(
        self,
        file_info: BackupFileInformation,
    ) -> None:
        bh = self._backup_history
        # Check for potential sneaky corruption.
        (
            is_potential_sneaky_corruption,
            existing_fi,
        ) = bh.get_potential_bitrot_or_sneaky_corruption_info(cur_fi=file_info)
        if is_potential_sneaky_corruption:
            # The path of file_info has been backed up before,
            # and its most recent backup has matching date/time
            # and size but the digests are different.
            warning_str = ""
            if self._sneaky_corruption_detection:
                warning_str = "WARNING: "
            msg = (
                f"{warning_str}Potential bitrot or sneaky corruption: "
                f"File at path has same date/time and size as last backup but digest differs: "
                f"path={file_info.path} "
                f"modified_utc={file_info.modified_date_stamp_ISO8601_utc} "
                f"size={file_info.size_in_bytes} "
                f"digest_now={file_info.primary_digest} "
                f"digest_last={existing_fi.primary_digest}"
            )
            if self._sneaky_corruption_detection:
                logging.warning(msg)
                self.anomalies.append(
                    BackupAnomaly(
                        kind=ANOMALY_KIND_UNEXPECTED_STATE,
                        file_info=file_info,
                        message=msg,
                    )
                )
            else:
                logging.info(msg)

    def _is_file_for_backup(
        self,
        file_info: BackupFileInformation,
    ) -> bool:
        """This method is called after hashing, at the point in time
        when incremental plus deduplication evaluation can take place.
        If incremental plus is not in effect, this function returns
        True, else it determines the dedup status and returns True/False
        accordingly (see logic below). The caller-supplied file_info
        may be updated below depending on the outcome of the evaluation.
        """
        bh = self._backup_history
        #
        # Post-hashing result is available for --incremental-plus backups.
        #
        if self._backup_type != ATBU_BACKUP_TYPE_INCREMENTAL_PLUS:
            #
            # Not incremental plus so backup status of this file
            # was determined at the time it was discovered, before
            # hashing, etc. Backup this file.
            #
            return True

        if self._deduplication_option in [
            ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST,
            ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST_EXT,
        ]:
            #
            # Deduplication option specified, evaluate accordingly:
            #

            dup_fi = bh.get_duplicate_file(
                deduplication_option=self._deduplication_option,
                cur_fi=file_info,
            )
            if dup_fi is None:
                #
                # No duplciates found, backup the file.
                #
                return True

            #
            # Duplicates found, skip backup of this file.
            #
            logging.info(
                f"Skipping unchanged file (dedup='{self._deduplication_option}'): {file_info.path}"
            )
            logging.debug(f"  Duplicate already backed up: {dup_fi.path}")
            self._unchanged_skipped_files.append(file_info)
            file_info.is_unchanged_since_last = True
            file_info.deduplication_option = self._deduplication_option
            file_info.backing_fi = dup_fi
            self._results_mgr.extend_temp_results(file_info)
            return False

        #
        # No deduplication option, evaluate accordingly:
        #
        (
            is_changed,
            existing_fi,
        ) = bh.get_primary_digest_changed_info(cur_fi=file_info)
        if is_changed:
            #
            # Digest change, backup the file.
            #
            logging.debug(f"Detected digest change: {file_info.path}")
            return True

        #
        # No digest change.
        #
        (
            is_changed,
            existing_fi2,
        ) = bh.get_file_date_size_modified_state(cur_fi=file_info)
        if existing_fi != existing_fi2:
            # This would indicate a bug.
            msg = (
                f"ERROR: Historical file information for digest and "
                f"date/size checks differs unexpectedly. "
                f"Continuing regardless, will backup file. "
                f"Please report this issue and verify your backup."
            )
            logging.error(msg)
            self.anomalies.append(
                BackupAnomaly(
                    kind=ANOMALY_KIND_UNEXPECTED_STATE,
                    file_info=file_info,
                    message=msg,
                )
            )
            #
            # Backup file.
            #
            return True

        if not is_changed:
            #
            # Date/time and size not changed, skip this file.
            #
            logging.debug(
                f"Skipping unchanged file "
                f"(digest, modified date/time, size all unchanged): "
                f"{file_info.path}"
            )
            self._unchanged_skipped_files.append(file_info)
            file_info.is_unchanged_since_last = True
            file_info.deduplication_option = existing_fi.deduplication_option
            file_info.backing_fi = existing_fi
            self._results_mgr.extend_temp_results(file_info)
            return False

        #
        # Digests match but size/time do not match, emit details and backup anyway.
        #
        if file_info.size_in_bytes != existing_fi2.size_in_bytes:
            msg = (
                f"WARNING: File unchanged file based on digest check, "
                f"but size differs. "
                f"The file could have changed since digest calc, "
                f"queuing for backup: {file_info.path}"
            )
            logging.warning(msg)
            self.anomalies.append(
                BackupAnomaly(
                    kind=ANOMALY_KIND_UNEXPECTED_STATE,
                    file_info=file_info,
                    message=msg,
                )
            )

            #
            # Backup the file.
            #
            return True

        if file_info.modified_time_posix != existing_fi2.modified_time_posix:
            msg = (
                f"WARNING: File unchanged file based on digest check, "
                f"but last modified time differs. The file could have "
                f"changed since digest calc, and files can be 'touch'ed."
                f"Queuing for backup: {file_info.path}"
            )
            logging.warning(msg)
            self.anomalies.append(
                BackupAnomaly(
                    kind=ANOMALY_KIND_UNEXPECTED_STATE,
                    file_info=file_info,
                    message=msg,
                )
            )
            #
            # Backup the file
            #
            return True

        # This would indicate a bug.
        msg = (
            f"ERROR: File unchanged file based on digest check, "
            f"but modified time/size checks are causing change "
            f"detection for unknown reasons. Please report this "
            f"issue: "
            f"{file_info.path}"
        )
        logging.error(msg)
        self.anomalies.append(
            BackupAnomaly(
                kind=ANOMALY_KIND_UNEXPECTED_STATE,
                file_info=file_info,
                message=msg,
            )
        )
        #
        # Backup file.
        #
        return True

    def _post_hasher_decision_making(self, wi: BackupPipelineWorkItem):
        """Handle a hashing result."""

        file_info: BackupFileInformation = wi.file_info

        # See if date/time and size have not changed despite
        # digest indicating changes. If yes, report as either
        # error or informational message depending on whether
        # or not user specified --no-detect-bitrot.
        self._handle_sneaky_corruption_detection(file_info=file_info)

        # If decision to backup not already made...
        if not wi.is_qualified:
            # ...decide whether to backup or not.
            wi.is_qualified = self._is_file_for_backup(file_info=file_info)

        if wi.is_qualified:
            wi.operation_runner = BackupFile(
                file_info=file_info,
                storage_def=self.storage_def,
                object_name_hash_salt=self._object_name_hash_salt,
                object_name_reservations=self._object_name_reservations,
                perform_cleartext_hashing=False,
                is_dryrun = self.is_dryrun,
            )

        return wi

    def _backup_files(self):
        logging.info(f"Starting backup '{self._results_mgr.specific_backup_name}'...")
        if self._is_used:
            raise AlreadyUsedError(f"This instance has already been used.")
        self._is_used = True
        pending_backups = set[Future]()
        try:
            logging.info(f"Scheduling hashing jobs...")
            for file_info in self._source_files:
                if self._backup_type == ATBU_BACKUP_TYPE_INCREMENTAL:
                    (
                        is_changed,
                        existing_fi,
                    ) = self._backup_history.get_file_date_size_modified_state(
                        cur_fi=file_info
                    )
                    if not is_changed:
                        # For incremental, skip based on size/modified-based checks.
                        logging.info(f"Skipping unchanged file: {file_info.path}")
                        self._unchanged_skipped_files.append(file_info)
                        file_info.is_unchanged_since_last = True
                        file_info.deduplication_option = (
                            existing_fi.deduplication_option
                        )
                        file_info.backing_fi = existing_fi
                        # For incremental, there is only date/size check for same path
                        # to see if there is a match. When such a match occurs, set
                        # the current file's digest to that of the assumed duplicate.
                        file_info.is_backing_fi_digest = True
                        file_info.primary_digest = existing_fi.primary_digest
                        self._results_mgr.extend_temp_results(file_info)
                        continue
                    elif existing_fi:
                        logging.info(
                            f"Scheduling backup of changed file: {file_info.path} "
                            f"cur_date={file_info.modified_date_stamp_ISO8601_local} "
                            f"old_date={existing_fi.modified_date_stamp_ISO8601_local} "
                            f"cur_size={file_info.size_in_bytes} "
                            f"old_size={existing_fi.size_in_bytes}"
                        )
                        logging.debug(
                            f"POSIX timestamps: {file_info.path} "
                            f"cur_posix={file_info.accessed_time_posix} "
                            f"old_posix={file_info.accessed_time_posix}"
                        )
                    else:
                        logging.info(
                            f"Scheduling backup of file never backed up before: {file_info.path}"
                        )
                wait_futures_to_regulate(
                    fs=pending_backups,
                    max_allowed_pending=Backup.MAX_SIMULTANEOUS_FILES,
                )
                pending_backup_fut = self._subprocess_pipeline.submit(
                    work_item=BackupPipelineWorkItem(
                        operation_name=BACKUP_OPERATION_NAME_BACKUP,
                        file_info=file_info,
                    )
                )
                pending_backups.add(pending_backup_fut)
                self._results_mgr.extend_temp_results(
                    file_operation_futures_to_results(
                        fs=pending_backups,
                        fi_list=[],
                        anomalies=self.anomalies,
                        the_operation=BACKUP_OPERATION_NAME_BACKUP,
                        is_dryrun=self.is_dryrun,
                    )
                )

            logging.info(
                f"Wait for {len(pending_backups)} backup file operations to complete..."
            )
            while len(pending_backups) > 0:
                done, pending_backups = futures.wait(
                    fs=pending_backups, return_when=FIRST_COMPLETED
                )
                if _is_very_verbose_logging():
                    logging.debug(
                        f"Backup: observe {len(done)} completed, "
                        f"{len(pending_backups)} remaining files."
                    )
                self._results_mgr.extend_temp_results(
                    file_operation_futures_to_results(
                        fs=done,
                        fi_list=list(),
                        anomalies=self.anomalies,
                        the_operation=BACKUP_OPERATION_NAME_BACKUP,
                        is_dryrun=self.is_dryrun,
                    )
                )
                if _is_very_verbose_logging() and len(pending_backups) > 0:
                    logging.info(
                        f"Wait for {len(pending_backups)} backup file operations to complete..."
                    )

            #
            # Stopping the results manager saves the final backup information file.
            #
            self._results_mgr.stop()

            if self.storage_def.storage_persisted_backup_info:
                if self.is_dryrun:
                    logging.info(f"*** Dry run, not storing backup information to backup.")
                else:
                    #
                    # Save backup information to the backup storage.
                    #
                    fi_backup_info = BackupFileInformation(
                        path=str(self._results_mgr.backup_info_db.primary_db_full_path),
                    )

                    #
                    # Create a storage object name for the backup information.
                    # It will be BackupName-YYYYMMDD-HHMMSS.atbuinf where the date/time
                    # stamp derives from the specific backup start time.
                    #
                    sbi = self._results_mgr.final_results
                    backup_start_time_stamp = sbi.get_backup_start_time_stamp_utc()
                    # Store backup information with backup storage using a generic
                    # prefix BACKUP_INFO_STORAGE_PREFIX, where it will be renamed as
                    # needed during recovery.
                    db_storage_basename = (
                        f"{BACKUP_INFO_STORAGE_PREFIX}-"
                        f"{backup_start_time_stamp}{BACKUP_INFO_EXTENSION}"
                    )
                    fi_backup_info.storage_object_name = db_storage_basename

                    f = self._subprocess_pipeline.submit(
                        BackupPipelineWorkItem(
                            operation_name=BACKUP_OPERATION_NAME_BACKUP,
                            file_info=fi_backup_info,
                            is_qualified=True,
                        )
                    )
                    if f is None:
                        msg = f"Failed to schedule backup of the backup info file."
                        logging.error(msg)
                        self.anomalies.append(
                            BackupAnomaly(
                                kind=ANOMALY_KIND_UNEXPECTED_STATE,
                                file_info=fi_backup_info,
                                message=msg,
                            )
                        )
                        return
                    done, not_done = futures.wait(fs=set([f]), return_when=ALL_COMPLETED)
                    if len(done) != 1 or f not in done:
                        msg = (
                            f"Expected backup info future to be completed but got "
                            f"done={len(done)} not_done={len(not_done)} f.done()={f.done()}."
                        )
                        logging.error(msg)
                        self.anomalies.append(
                            BackupAnomaly(
                                kind=ANOMALY_KIND_UNEXPECTED_STATE,
                                file_info=fi_backup_info,
                                message=msg,
                            )
                        )
                        return
                    if f.exception():
                        msg = (
                            f"There was an error during backup of the backup information: "
                            f"{exc_to_string(f.exception())}"
                        )
                        logging.error(msg)
                        self.anomalies.append(
                            BackupAnomaly(
                                kind=ANOMALY_KIND_EXCEPTION,
                                file_info=fi_backup_info,
                                exception=f.exception(),
                                message=msg,
                            )
                        )
                        return

                    logging.info(
                        f"The backup information has been successfully backed up: "
                        f"{fi_backup_info.path}"
                    )

        except Exception as ex:
            logging.error(
                f"Unexpected exception scheduling to hasher worker and file backup workers. "
                f"{exc_to_string(ex)}"
            )
            raise
        finally:
            self._subprocess_pipeline.shutdown()
            self.anomalies.extend(self._subprocess_pipeline.anomalies)

    def is_completely_successful(self):
        return len(self.anomalies) == 0

    def backup_files(self):
        try:
            self._backup_files()
        finally:
            self._results_mgr.stop()

        dryrun_str = "(dry run) " if self.is_dryrun else ""
        logging.info(f"{dryrun_str}All backup file operations have completed.")
        if (
            self._compression_stage is not None
            and self._compression_stage.ext_to_ratio is not None
        ):
            logging.info(f"")
            logging.info(f"{dryrun_str}Extension compression ratio report (lower is better):")
            ext_to_ratio = self._compression_stage.ext_to_ratio
            if len(ext_to_ratio) == 0:
                logging.info(f"{dryrun_str}  - No extension-to-ratio info captured -")
            else:
                for k, v in sorted(ext_to_ratio.items(), key=lambda t: t[1]):
                    if len(k) == 0:
                        k = "(no extension)"
                    k = f" '{k}' "
                    logging.info(f"{k:.<45} {(v*100):5.1f}%")
                logging.info(f"")

        if self.is_dryrun:
            logging.info(f"{dryrun_str}: Files that would have been backed up:")
            total_bytes = 0
            ONE_MB = 1024.0*1024.0
            for fi in self._results_mgr.final_results.all_file_info:
                if fi.is_successful and fi.exception is None:
                    logging.info(f"{fi.path} ({fi.size_in_bytes/ONE_MB:.3f} MB)")
                    total_bytes += fi.size_in_bytes
            logging.info(f"{dryrun_str}: Total bytes all files: {total_bytes/ONE_MB:.3f} MB")

        if len(self.anomalies) == 0:
            logging.info(f"***************")
            logging.info(f"*** SUCCESS *** {dryrun_str}")
            logging.info(f"***************")
            logging.info(f"{dryrun_str}No errors detected during backup.")
        else:
            log_anomalies_report(anomalies=self.anomalies)
        for fi in self._results_mgr.final_results.all_file_info:
            if fi.is_successful and fi.exception is None:
                self.success_count += 1
        logging.info(f"{dryrun_str}{'Total files ':.<45} {len(self._source_files)}")
        logging.info(
            f"{dryrun_str}{'Total unchanged files ':.<45} {len(self._unchanged_skipped_files)}"
        )
        logging.info(
            f"{dryrun_str}{'Total backup operations ':.<45} "
            f"{len(self._results_mgr.final_results) - len(self._unchanged_skipped_files)}"
        )
        unexpected_count_diff = len(self._source_files) - len(
            self._results_mgr.final_results
        )
        if unexpected_count_diff != 0:
            logging.info(
                f"{dryrun_str}"
                f"{'Total unexpected files-results difference ':.<45} {unexpected_count_diff}"
            )
        if len(self._results_mgr.tmp_results) > 0:
            logging.info(
                f"{dryrun_str}"
                f"{'Total unexpected unsaved results ':.<45} {len(self._results_mgr.tmp_results)}"
            )
        logging.info(f"{dryrun_str}{'Total errors ':.<45} {len(self.anomalies)}")
        logging.info(f"{dryrun_str}{'Total successful backups ':.<45} {self.success_count}")


class StorageFileRetriever(ProcessThreadContextMixin):

    RETRY_DEFAULT_DELAY_SECONDS = 1
    RETRY_BACKUP_MULTIPLIER = 2
    RETRY_MAX_DELAY_SECONDS = 30

    def __init__(
        self, file_info: BackupFileInformation, storage_def: StorageDefinition
    ):
        super().__init__()
        self.file_info = file_info
        if self.file_info.is_unchanged_since_last:
            self._backing_fi = file_info.backing_fi
        else:
            self._backing_fi = file_info
        self._storage_def = storage_def
        self.preamble_dict: dict = None
        self.preamble_compression: str = None
        self.preamble_digest: str = None
        self.preamble_size_in_bytes: int = None
        self.preamble_modified_time_posix: float = None
        self.preamble_accessed_time_posix: float = None
        self.preamble_path_without_root: str = None
        self._dec: AesCbcPaddingDecryptor = None
        self._hasher_ciphertext: Hasher = None
        self._hasher_cleartext: Hasher = None
        self._cleartext_digest: str = None
        self._is_first_chunk = True
        self._is_last_chunk = False
        self.total_cleartext_bytes = 0
        self.total_ciphertext_bytes = 0
        self._header_version = None
        self._header_option_flags = None
        self._header_IV = None
        self._download_chunk_size = self._storage_def.download_chunk_size

    @property
    def path_for_logging(self) -> str:
        return self.file_info.path_without_discovery_path

    @property
    def cleartext_digest(self) -> str:
        if self._cleartext_digest is None:
            raise InvalidStateError(
                f"StorageFileRetriever: self._cleartext_digest is not set."
            )
        return self._cleartext_digest

    def disable_cleartext_hashing(self):
        self._hasher_cleartext = None

    @property
    def ciphertext_digest(self) -> str:
        if not self._hasher_ciphertext:
            raise InvalidStateError(
                f"StorageFileRetriever: Expected hasher self.hasher_ciphertext to be available."
            )
        return self._hasher_ciphertext.get_primary_hexdigest()

    @property
    def is_compressed(self) -> bool:
        if self.preamble_compression is None:
            raise StateNotYetKnownError(
                f"Compression/non-compression state cannot be "
                f"known until after preamble processing."
            )
        return self.preamble_compression == BACKUP_COMPRESSION_TYPE

    def get_download_iterator(self) -> tuple[Iterator[bytes], tuple[Exception]]:
        """Returns an iterator from which to download chunks, and
        the exception types it might throw which can be retried.
        The download iterator must supply the same size chunk of
        bytes until the last iterator which may be that largest
        chunk size or less.
        """
        logging.debug(f"StorageFileRetriever: Creating storage driver...")
        storage_interface = self._storage_def.create_storage_interface()
        container = storage_interface.get_container(
            container_name=self._storage_def.container_name
        )
        storage_object = container.get_object(self._backing_fi.storage_object_name)
        download_iter = storage_interface.download_object_as_stream(
            storage_object=storage_object,
            chunk_size=self._download_chunk_size,
        )
        return download_iter, storage_interface.retry_exceptions

    def prepare_destination(self):
        """Prepare decrypted data destination."""
        pass

    def attempt_failed_cleanup(self):
        """After failed attempt (more retries remaining) cleanup
        resources before next attempt. This usually cleans up
        resources established in StorageFileRetriever.prepare.
        """
        pass

    def report_progress(self, percent: int):
        pass

    def extract_header(self, chunk: bytes) -> bytes:
        """Extract backup file header information if this is "
        the first chunk and header information has not already
        been extracted. Returns the chunk without the header bytes.
        Must be called by both decryption and non-decryption
        restore/verify code paths.
        """
        if not self._is_first_chunk:
            if not self._header_version:
                raise BackupFileHeaderInvalid(
                    f"Not the first chunk but no header was read."
                )
            return chunk
        if self._header_version:
            # Header info already extracted, nothing to do.
            return chunk
        # Extract header info.
        (
            size_consumed,
            self._header_version,
            self._header_option_flags,
            self._header_IV,
        ) = parse_backup_file_header(raw_header=chunk)
        # The actual first chunk (encrypted or decrypted) begins
        # just after the plaintext header just extracted.
        # Return the true non-header chunk.
        chunk = chunk[size_consumed:]
        return chunk

    def decrypt_chunk(self, encrypted_chunk: bytes):
        self.total_ciphertext_bytes += len(encrypted_chunk)
        if self._is_first_chunk:
            # If using encryption, header is extracted here.
            encrypted_chunk = self.extract_header(chunk=encrypted_chunk)
        if self.file_info.populate_from_header:
            if self.file_info.encryption_IV is None and self._header_IV is not None:
                self.file_info.encryption_IV = self._header_IV
        if not self._dec:
            iv_to_use = self._backing_fi.encryption_IV
            if iv_to_use is None:
                iv_to_use = self._header_IV
            if iv_to_use is None:
                raise InvalidStateError(
                    f"StorageFileRetriever: Expected decryptor self.dec to be available."
                )
            self._dec: AesCbcPaddingDecryptor = self._storage_def.create_decryptor(
                IV=iv_to_use
            )
        if not self._hasher_ciphertext:
            raise InvalidStateError(
                f"StorageFileRetriever: Expected hasher self.hasher_ciphertext to be available."
            )
        self._hasher_ciphertext.update_all(encrypted_chunk)
        decrypted_chunk = self._dec.update(encrypted_chunk)
        if self._is_last_chunk:
            decrypted_chunk += self._dec.finalize()
        return decrypted_chunk

    def process_decrypted_chunk_raw(self, decrypted_chunk: bytes) -> bytes:
        if self._is_first_chunk:
            # If not using encryption, header is extracted here.
            decrypted_chunk = self.extract_header(
                chunk=decrypted_chunk
            )  # Do this before setting is_first_chunk=False
            self._is_first_chunk = False
            #
            # Extract preamble to dict, remove preemable from decrypted bytes.
            #
            try:
                (
                    self.preamble_dict,
                    preamble_with_padding_size,
                ) = parse_backup_file_preamble(preamble=decrypted_chunk)
                hashalgo_name = (
                    GlobalHasherDefinitions().get_primary_hashing_algo_name()
                )
                self.preamble_digest = self.preamble_dict[hashalgo_name]
                self.preamble_path_without_root = self.preamble_dict["path"]
                self.preamble_size_in_bytes = int(self.preamble_dict["size"])
                self.preamble_modified_time_posix = float(
                    self.preamble_dict["modified"]
                )
                self.preamble_accessed_time_posix = float(
                    self.preamble_dict["accessed"]
                )
                self.preamble_compression = self.preamble_dict[
                    _PREAMBLE_FIELD_COMPRESSION
                ]
            except Exception as ex:
                raise PreambleParsingError(
                    f"StorageFileRetriever: Error parsing preemable: "
                    f"path={self.file_info.path_without_root} {exc_to_string(ex)}"
                ).with_traceback(ex.__traceback__) from ex
            # Remove preamble from decrypted_chunk.
            decrypted_chunk = decrypted_chunk[preamble_with_padding_size:]
            if self.file_info.populate_from_header:
                self.file_info.primary_digest = self.preamble_digest
                self.file_info.size_in_bytes = self.preamble_size_in_bytes
                self.file_info.modified_time_posix = self.preamble_modified_time_posix
                self.file_info.accessed_time_posix = self.preamble_accessed_time_posix

        if self._hasher_cleartext is not None:
            # Update cleartext hash with file plaintext data.
            self._hasher_cleartext.update_all(decrypted_chunk)

        self.total_cleartext_bytes += len(decrypted_chunk)

        return decrypted_chunk

    def process_decrypted_chunk(self, decrypted_chunk: bytes):
        pass

    def download_completed(self):
        """Successful download cleanup."""
        pass

    def download_failed(self):
        """Failed download (no more retries) cleanup.
        This is the "exception" handler, no retries remaining, handler.
        """
        pass

    def final_cleanup(self):
        """Final cleanup, called after either download_completed and download_failed.
        This is the "finally" block (no more retries) cleanup.
        """
        pass

    def run(self, wi: BackupPipelineWorkItem):  # pylint: disable=unused-argument
        try:
            self.file_info.is_successful = False
            self.file_info.exception = None
            total_size_in_bytes = self._backing_fi.size_in_bytes
            self.file_info.is_backup_encrypted = self._storage_def.is_encryption_used
            logging.debug(
                f"StorageFileRetriever: {self.get_exec_context_log_stamp_str()} "
                f"path={self._backing_fi.path_without_root}"
            )
            self._dec = None
            self._hasher_ciphertext = None
            if self._storage_def.is_encryption_used:
                self._hasher_ciphertext = GlobalHasherDefinitions().create_hasher()
            self._hasher_cleartext = GlobalHasherDefinitions().create_hasher()
            is_prepare_called = False
            retry_delay = StorageFileRetriever.RETRY_DEFAULT_DELAY_SECONDS
            download_iter: Iterator[bytes] = None
            retry_exception_types: tuple[type] = ()
            is_retry_okay: bool = False
            while True:
                try:
                    logging.debug(f"StorageFileRetriever: Get download iterator...")
                    download_iter, retry_exception_types = self.get_download_iterator()

                    last_percent_reported = None

                    is_retry_okay = True  # For next iter
                    for chunk in download_iter:
                        is_retry_okay = False

                        self._is_last_chunk = len(chunk) < self._download_chunk_size

                        if len(chunk) == 0 and (
                            not self._storage_def.is_encryption_used
                            or (self._dec is not None and self._dec.is_finalized)
                        ):
                            break

                        if self._storage_def.is_encryption_used and (
                            self._dec is not None and self._dec.is_finalized
                        ):
                            raise AlreadyFinalizedError(
                                f"StorageFileRetriever: "
                                f"More data but decryption already finalized: "
                                f"{self.file_info.path_without_root}"
                            )

                        if total_size_in_bytes == 0:
                            percent = 100
                        else:
                            percent = int(
                                (
                                    min(self.total_cleartext_bytes, total_size_in_bytes)
                                    / total_size_in_bytes
                                )
                                * 100
                            )
                        if last_percent_reported is None or (percent / 10) > (
                            last_percent_reported / 10
                        ):
                            last_percent_reported = percent
                            self.report_progress(percent)

                        if self._storage_def.is_encryption_used:
                            decrypted_chunk = self.decrypt_chunk(encrypted_chunk=chunk)
                        else:
                            decrypted_chunk = chunk

                        #
                        # Process the decrypted chunk for internal
                        # processing, including header extraction.
                        #
                        decrypted_chunk = self.process_decrypted_chunk_raw(
                            decrypted_chunk
                        )

                        #
                        # Prepare destination (which may use header
                        # info extracted above).
                        #
                        if not is_prepare_called:
                            is_prepare_called = True
                            self.prepare_destination()

                        #
                        # Process the pure decrypted file data.
                        #
                        self.process_decrypted_chunk(decrypted_chunk)

                        is_retry_okay = True  # for next iter
                    is_retry_okay = False  # iter complete
                    if self._storage_def.is_encryption_used and (
                        self._dec is None or not self._dec.is_finalized
                    ):
                        raise InvalidStateError(
                            f"Storage definition requires encryption, "
                            f"but encryption was either not used or not completed."
                        )
                    break
                except Exception as ex:
                    logging.error(
                        f"StorageFileRetriever error: path={self._backing_fi.path_without_root} "
                        f"storage={self._backing_fi.storage_object_name} {exc_to_string(ex)}"
                    )
                    if not is_retry_okay:
                        logging.error(
                            f"StorageFileRetriever: retry is not allowed: ex={ex}"
                        )
                        raise
                    is_retry_okay = False
                    if not isinstance(ex, retry_exception_types):
                        raise
                    #
                    # Reset for next attempt.
                    #
                    is_prepare_called = False
                    self.attempt_failed_cleanup()
                    logging.warning(
                        f"StorageFileRetriever: Retry-eligible failure. "
                        f"Waiting {retry_delay} seconds before restore retry."
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * StorageFileRetriever.RETRY_BACKUP_MULTIPLIER,
                        StorageFileRetriever.RETRY_MAX_DELAY_SECONDS,
                    )
                    logging.warning(f"Retrying operation now...")
            self.file_info.is_successful = True
            if self.file_info.populate_from_header:
                if self._storage_def.is_encryption_used:
                    # Usually, populate_from_header is used when local info has been lost or
                    # has become unavailable. There is therefore no backup ciphertext hash.
                    # There is an encrypted cleartext hash, generally protected to whatever
                    # extent the encryption is secure.
                    self.file_info.ciphertext_hash_during_backup = (
                        self.ciphertext_digest
                    )
            if self._hasher_cleartext is not None:
                self._cleartext_digest = self._hasher_cleartext.get_primary_hexdigest()
            self.download_completed()
            return (self.file_info, None)
        except Exception as ex:
            self.file_info.exception = ex
            self.file_info.is_successful = False
            logging.error(
                f"StorageFileRetriever: FAILURE: {self.get_exec_context_log_stamp_str()} "
                f"path={self.file_info.path_without_root} {exc_to_string(ex)}"
            )
            self.download_failed()
            return (self.file_info, ex)
        finally:
            self.final_cleanup()
            logging.debug(
                f"{self.our_thread_name}: "
                f"Completed: is_successful={self.file_info.is_successful} "
                f"{self.file_info.path_without_root}"
            )

    def perform_common_checks(
        self,
        log_msg_prefix_str: str,
        file_path_for_logging: str,
        orig_file_info: BackupFileInformation,
    ):
        logging.info(f"{log_msg_prefix_str}: Completed for {file_path_for_logging}")
        logging.info(f"{'  Total bytes ':.<45} {self.total_cleartext_bytes}")
        if self._cleartext_digest is not None:
            logging.info(f"{'  SHA256 download ':.<45} {self.cleartext_digest}")
        backing_fi_digest_indicator = ""
        if orig_file_info.is_backing_fi_digest:
            backing_fi_digest_indicator = "(assumed)"
        logging.info(
            f"{'  SHA256 original ':.<45} "
            f"{orig_file_info.primary_digest} "
            f"{backing_fi_digest_indicator}"
        )
        if (
            orig_file_info.size_in_bytes != self.total_cleartext_bytes
            or orig_file_info.size_in_bytes != self.preamble_size_in_bytes
        ):
            raise SizeMistmatchError(
                f"{log_msg_prefix_str}: The file's cleartext sizes do not match: "
                f"path={file_path_for_logging} "
                f"backup_size={orig_file_info.size_in_bytes} "
                f"header_size={self.preamble_size_in_bytes} "
                f"verify_size={self.total_cleartext_bytes}"
            )
        if orig_file_info.modified_time_posix != self.preamble_modified_time_posix:
            preamble_modified_time_ISO8601 = posix_timestamp_to_ISO8601_utc_stamp(
                self.preamble_modified_time_posix
            )
            raise DateTimeMistmatchError(
                f"{log_msg_prefix_str}: "
                f"The backup record of file date/time do not match those stored in the backup: "
                f"path={file_path_for_logging} "
                f"original_modified={orig_file_info.modified_date_stamp_ISO8601_utc} "
                f"({orig_file_info.modified_time_posix}) "
                f"header_modified={preamble_modified_time_ISO8601} "
                f"({self.preamble_modified_time_posix})"
            )
        if orig_file_info.primary_digest != self.cleartext_digest:
            raise DigestMistmatchError(
                f"{log_msg_prefix_str}: The file's cleartext hashes do not match: "
                f"path={file_path_for_logging} "
                f"backup_hash{backing_fi_digest_indicator}={orig_file_info.primary_digest} "
                f"verify_hash={orig_file_info.cleartext_hash_during_restore}"
            )
        if self._storage_def.is_encryption_used:
            logging.info(
                f"{'  SHA256 encrypted download ':.<45} " f"{self.ciphertext_digest}"
            )
            logging.info(
                f"{'  SHA256 encrypted original ':.<45} "
                f"{orig_file_info.ciphertext_hash_during_backup}"
            )
            if orig_file_info.ciphertext_hash_during_backup != self.ciphertext_digest:
                # This check is not completely superfluous. For the encrypted case, it includes the
                # encrypted preamble which is not included in the plaintext digest.
                raise DigestMistmatchError(
                    f"{log_msg_prefix_str}: The file's ciphertext hashes do not match: "
                    f"path={file_path_for_logging} "
                    f"backup_hash={orig_file_info.ciphertext_hash_during_backup} "
                    f"verify_hash={orig_file_info.ciphertext_hash_during_restore}"
                )

            # Used by tests.
            logging.debug(
                f"{log_msg_prefix_str}: "
                f"SHA256={self.ciphertext_digest} "
                f"bytes={self.total_ciphertext_bytes}"
            )

        # Used by tests: debug logging of single line with relevant info:
        logging.debug(
            f"{log_msg_prefix_str}: "
            f"path={orig_file_info.path} "
            f"backup_size={orig_file_info.size_in_bytes} "
            f"verify_size={self.total_cleartext_bytes} "
            f"backup_modified={orig_file_info.modified_time_posix} "
            f"backup_{orig_file_info.primary_digest_algo_name}={orig_file_info.primary_digest} "
            f"verify_{orig_file_info.primary_digest_algo_name}={orig_file_info.primary_digest}"
        )
