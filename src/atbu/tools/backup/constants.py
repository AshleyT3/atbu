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
r"""ATBU constants.
"""
from dataclasses import dataclass
from typing import Literal


ATBU_MAJOR_VERSION = 0
ATBU_MINOR_VERSION = 20

ATBU_VERSION_STRING = f"{ATBU_MAJOR_VERSION}.{ATBU_MINOR_VERSION:02}"

AT_PREFIX = "at"
AT_PREFIX_U = "AT"
ATBU_ACRONYM = f"{AT_PREFIX}bu"
ATBU_ACRONUM_U = f"{AT_PREFIX_U}BU"

ATBU_PROGRAM_NAME = ATBU_ACRONYM

ATBU_PERSISTENT_INFO_EXTENSION = f".{ATBU_ACRONYM}"
ATBU_PERSISTENT_INFO_DB_EXTENSION = f".{ATBU_ACRONYM}db"
ATBU_SKIP_EXTENSIONS = [
    ATBU_PERSISTENT_INFO_EXTENSION,
    ATBU_PERSISTENT_INFO_DB_EXTENSION,
]
ATBU_DEFAULT_PERSISTENT_DB_FILENAME = (
    f"c4198ead-0b50-4f0e-b52b-685b64e7b9f0{ATBU_PERSISTENT_INFO_DB_EXTENSION}"
)
ATBU_PERSISTENT_INFO_VERSION = 2
ATBU_PERSISTENT_INFO_VERSION_STRING = f"{ATBU_PERSISTENT_INFO_VERSION}"
ATBU_PERSIST_TYPE_PER_DIR = "per-dir"
ATBU_PERSIST_TYPE_PER_FILE = "per-file"
ATBU_PERSIST_TYPE_PER_BOTH = "per-both"
ATBU_PERSIST_TYPES = [ATBU_PERSIST_TYPE_PER_DIR, ATBU_PERSIST_TYPE_PER_FILE]
ATBU_PERSIST_TYPE_HINT = Literal["per-dir", "per-file"]
ATBU_PERSIST_TYPE_CHAR_TO_STR = {
    "d": ATBU_PERSIST_TYPE_PER_DIR,
    "f": ATBU_PERSIST_TYPE_PER_FILE,
    "b": ATBU_PERSIST_TYPE_PER_BOTH,
}

ATBU_FILE_BACKUP_EXTENSION = f".{AT_PREFIX}bak"
ATBU_FILE_BACKUP_EXTENSION_ENCRYPTED = f".{AT_PREFIX}bake"

ATBU_BACKUP_TYPE_FULL = "full"
ATBU_BACKUP_TYPE_INCREMENTAL = "incremental"
ATBU_BACKUP_TYPE_INCREMENTAL_PLUS_SHORT_CMD_OPT = "ip"
ATBU_BACKUP_TYPE_INCREMENTAL_PLUS = "incremental-plus"
ATBU_BACKUP_TYPE_ALL = [
    ATBU_BACKUP_TYPE_FULL,
    ATBU_BACKUP_TYPE_INCREMENTAL,
    ATBU_BACKUP_TYPE_INCREMENTAL_PLUS,
]

ATBU_BACKUP_DRYRUN_SUCCESS_EXIT_CODE = 99

ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST = "digest"
ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST_EXT = "digest-ext"

BACKUP_COMPRESSION_NONE = "none"
BACKUP_COMPRESSION_NORMAL = "normal"
BACKUP_COMPRESSION_CHOICES = [BACKUP_COMPRESSION_NONE, BACKUP_COMPRESSION_NORMAL]
BACKUP_COMPRESSION_DEFAULT = BACKUP_COMPRESSION_NORMAL
BACKUP_COMPRESSION_TYPE = "gzip"

CONFIG_SECTION_COMPRESSION = "compression"
CONFIG_VALUE_NAME_COMPRESSION_LEVEL = "level"
CONFIG_VALUE_NAME_NO_COMPRESS_PATTERN = "no_compress_pattern"
ATBU_BACKUP_DEFAULT_NO_COMPRESS_RE_PAT = (
    r"("
    r".*\.jpg$|.*\.jpeg$|.*\.mp4$|.*\.mov$|.*\.mpg|.*\.mpeg$|.*\.mp3$|"
    r".*\.zip$|.*\.gz$|.*\.7z$|.*\.bz2$"
    r")"
)
CONFIG_VALUE_NAME_COMPRESS_MIN_FILE_SIZE = "min_size"
ATBU_BACKUP_DEFAULT_COMPRESS_MIN_FILE_SIZE = 150
CONFIG_VALUE_NAME_MIN_COMPRESS_RATIO = "min_ratio"
ATBU_BACKUP_DEFAULT_MIN_COMPRESS_RATIO = 0.9
CONFIG_VALUE_NAME_MAX_FTYPE_ATTEMPTS = "max_file_type_attempts"
ATBU_BACKUP_DEFAULT_MAX_FTYPE_ATTEMPTS = 3

ATBU_BACKUP_COMPRESSION_DEFAULTS = {
    CONFIG_VALUE_NAME_COMPRESSION_LEVEL: BACKUP_COMPRESSION_NORMAL,
    CONFIG_VALUE_NAME_NO_COMPRESS_PATTERN: ATBU_BACKUP_DEFAULT_NO_COMPRESS_RE_PAT,
    CONFIG_VALUE_NAME_COMPRESS_MIN_FILE_SIZE: ATBU_BACKUP_DEFAULT_COMPRESS_MIN_FILE_SIZE,
    CONFIG_VALUE_NAME_MIN_COMPRESS_RATIO: ATBU_BACKUP_DEFAULT_MIN_COMPRESS_RATIO,
    CONFIG_VALUE_NAME_MAX_FTYPE_ATTEMPTS: ATBU_BACKUP_DEFAULT_MAX_FTYPE_ATTEMPTS,
}

ATBU_CONFIG_NAME = f"{ATBU_ACRONUM_U} Configuration"

ATBU_CONFIG_FILE_MAJOR_VERSION = 0
ATBU_CONFIG_FILE_MINOR_VERSION = 3
ATBU_CONFIG_FILE_VERSION_STRING_CURRENT = (
    f"{ATBU_CONFIG_FILE_MAJOR_VERSION}.{ATBU_CONFIG_FILE_MINOR_VERSION:02}"
)
ATBU_CONFIG_FILE_VERSION_STRING_0_01 = "0.01"
ATBU_CONFIG_FILE_VERSION_STRING_0_02 = "0.02"
ATBU_CONFIG_FILE_VERSION_STRING_0_03 = ATBU_CONFIG_FILE_VERSION_STRING_CURRENT


ATBU_DEFAULT_CONFIG_DIR_NAME = f".{ATBU_ACRONYM}"
ATBU_STGDEF_CONFIG_FILE_NAME_PREFIX = f"{ATBU_ACRONYM}-stgdef--"
ATBU_USER_DEFAULT_CONFIG_FILE_NAME = f"{ATBU_ACRONYM}-config.json"
ATBU_DEFAULT_BACKUP_INFO_SUBDIR = f"{ATBU_ACRONYM}-backup-info"
REPLACEMENT_FIELD_DEFAULT_CONFIG_DIR = "{DEFAULT_CONFIG_DIR}"
REPLACEMENT_FIELD_CONFIG_DIR = "{CONFIG_DIR}"
REPLACEMENT_FIELDS = [
    REPLACEMENT_FIELD_DEFAULT_CONFIG_DIR,
    REPLACEMENT_FIELD_CONFIG_DIR,
]

CONFIG_SECTION_GENERAL = "general"
CONFIG_VALUE_NAME_BACKUP_INFO_DIR = "backup-info-dir"
CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS = "backup-info-dir-no-defaults"
CONFIG_VALUE_NAME_CONFIG_NAME = "name"
CONFIG_VALUE_NAME_VERSION = "version"

CONFIG_SECTION_STORAGE_DEFINITIONS = "storage-definitions"
CONFIG_SECTION_STORAGE_DEFINITION_SPECIFIER_PREFIX = "storage-def"
CONFIG_VALUE_NAME_STORAGE_DEF_UNIQUE_ID = "id"
CONFIG_VALUE_NAME_INTERFACE_TYPE = "interface"
CONFIG_VALUE_NAME_PROVIDER = "provider"
CONFIG_VALUE_NAME_CONTAINER = "container"
CONFIG_SECTION_DRIVER = "driver"
CONFIG_VALUE_NAME_DRIVER_STORAGE_KEY = "key"
CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET = "secret"
CONFIG_VALUE_NAME_DRIVER_STORAGE_PROJECT = "project"
CONFIG_VALUE_NAME_KEYRING_SERVICE = "service"
CONFIG_VALUE_NAME_KEYRING_USERNAME = "username"
CONFIG_SECTION_ENCRYPTION = "encryption"
CONFIG_VALUE_NAME_ENCRYPTION_KEY = "key"
CONFIG_VALUE_NAME_STORAGE_PERSISTED_IV = "storage-persisted-IV"
CONFIG_STORAGE_PERSISTED_IV_DEFAULT_VALUE = True
CONFIG_VALUE_NAME_STORAGE_PERSISTED_BACKUP_INFO = "storage-persisted-backup-info"
CONFIG_STORAGE_PERSISTED_BACKUP_INFO_DEFAULT_VALUE = True
CONFIG_KEY_VALUE_KEYRING_INDIRECTION = "keyring"
CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION = f"{ATBU_ACRONUM_U}-backup-enc-key"
CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD = f"{ATBU_ACRONUM_U}-storage-password"

CONFIG_INTERFACE_TYPE_LIBCLOUD = "libcloud"
CONFIG_INTERFACE_TYPE_AZURE = "azure"
CONFIG_INTERFACE_TYPE_GOOGLE = "google"
CONFIG_INTERFACE_TYPE_FILESYSTEM = "filesystem"
CONFIG_INTERFACE_HINT = Literal["libcloud", "google", "filesystem"]

CONFIG_PASSWORD_TYPE = "password_type"
# CONFIG_CREDENTIAL_TYPE will be one of...
CONFIG_PASSWORD_KIND_ACTUAL = "actual"
CONFIG_PASSWORD_KIND_FILENAME = "filename"
CONFIG_PASSWORD_KIND_ENVVAR = "envvar"

CRED_OPERATION_SET_PASSWORD = "set-password"
CRED_OPERATION_SET_PASSWORD_ALIAS = "sp"

CRED_OPERATION_SET_PASSWORD_TYPE_BACKUP = "backup"
CRED_OPERATION_SET_PASSWORD_TYPE_STORAGE = "storage"
CRED_OPERATION_SET_PASSWORD_TYPE_FILENAME = "filename"
CRED_OPERATION_SET_PASSWORD_TYPE_ENVVAR = "envvar"
CRED_OPERATION_SET_PASSWORD_TYPES = [
    CRED_OPERATION_SET_PASSWORD_TYPE_BACKUP,
    CRED_OPERATION_SET_PASSWORD_TYPE_STORAGE,
    CRED_OPERATION_SET_PASSWORD_TYPE_FILENAME,
    CRED_OPERATION_SET_PASSWORD_TYPE_ENVVAR,
]

CRED_SECRET_KIND_STORAGE = "driver-secret"
CRED_SECRET_KIND_ENCRYPTION = "encryption-key"

PASSWORD_KINDS = [
    CONFIG_PASSWORD_KIND_ACTUAL,
    CONFIG_PASSWORD_KIND_FILENAME,
    CONFIG_PASSWORD_KIND_ENVVAR,
]

PASSWORD_KIND_CHAR_TO_KIND = {i[0]: i for i in PASSWORD_KINDS}

CRED_SECRET_KIND_STORAGE_FRIENDLY_NAME = "storage secret"
CRED_SECRET_KIND_ENCRYPTION_FRIENDLY_NAME = "backup encryption"

CREDS_SUBCMD_CREATE_STORAGE_DEF = "create-storage-def"

MAX_STORAGE_DEF_NAME = 80

@dataclass
class CredentialDefinition:
    name: str
    friendly_name: str
    store_credential_name: str
    section_path: str


CREDENTIAL_DEFINITIONS = {
    CRED_SECRET_KIND_STORAGE_FRIENDLY_NAME: CredentialDefinition(
        name=CRED_SECRET_KIND_STORAGE,
        friendly_name=CRED_SECRET_KIND_STORAGE_FRIENDLY_NAME,
        store_credential_name=CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD,
        section_path=CRED_SECRET_KIND_STORAGE,
    ),
    CRED_SECRET_KIND_ENCRYPTION_FRIENDLY_NAME: CredentialDefinition(
        name=CRED_SECRET_KIND_ENCRYPTION,
        friendly_name=CRED_SECRET_KIND_ENCRYPTION_FRIENDLY_NAME,
        store_credential_name=CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION,
        section_path=CRED_SECRET_KIND_ENCRYPTION,
    ),
}

ALLOWED_AES_KEY_BIT_LENGTHS = [128, 192, 256]
DEFAULT_AES_KEY_BIT_LENGTH = 256
# On 2021 16-core / 32-thread die, 1 million takes about .5 seconds.
# Obviously a little longer on 2017 mobile device but still acceptable
# given the relative infrequent need for password setup.
PBKDF2_WORK_FACTOR = 1000000

# BASE64_PREFIX_ORIGINAL_IS_BYTES = 0x0B
# BASE64_PREFIX_ORIGINAL_IS_STR = 0x05
