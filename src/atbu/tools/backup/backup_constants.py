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
r"""Backup core constants.
"""

from enum import Enum
from .constants import *

BACKUP_INFO_STORAGE_PREFIX = f"zz-backup-info"

BACKUP_INFO_EXTENSION = f".{ATBU_ACRONYM}inf"
BACKUP_INFO_TEMP_EXTENSION = f".{ATBU_ACRONYM}inf.tmp"

BACKUP_INFO_MAJOR_VERSION = 0
BACKUP_INFO_MINOR_VERSION = 4
BACKUP_INFO_MAJOR_VERSION_STRING = (
    f"{BACKUP_INFO_MAJOR_VERSION}.{BACKUP_INFO_MINOR_VERSION:02}"
)
BACKUP_DATABASE_DEFAULT_NAME = f"{ATBU_ACRONUM_U} Backup Information"
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

class DatabaseFileType(Enum):
    DEFAULT = "default"
    JSON = "json"
    SQLITE = "sqlite"
