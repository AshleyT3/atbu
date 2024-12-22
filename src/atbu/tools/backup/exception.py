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
r"""ATBU Exceptions.
"""

from atbu.common.exception import *


class PersistentFileInfoError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class InvalidPersistentFileInfoError(PersistentFileInfoError):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class PersistentFileInfoVersionMismatch(PersistentFileInfoError):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class BackupException(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class InvalidStorageDefinitionName(BackupException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class InvalidStorageDefinitionFile(BackupException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class StorageDefinitionAlreadyExists(BackupException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class StorageDefinitionNotFoundError(BackupException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class StorageDefinitionNotCreatedError(BackupException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class StorageDefinitionNotSpecifiedError(BackupException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class PasswordAuthenticationFailure(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialInvalid(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialSetInvalid(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialStateInvalid(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialNotFoundError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialSecretDerivationError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialSecretFileNotFoundError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialTypeNotFoundError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialRequestInvalidError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupSelectionError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackingFileInformationNotFound(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class RestoreFilePathAlreadyExistsError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class VerifyFilePathNotFoundError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class VerifyFailure(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupAlreadyInUseError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupInformationDirectoryNotFound(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupInformationError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupInformationRecoveryFailed(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupInformationFileTimestampNotFound(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupFileHeaderInvalid(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class PreambleParsingError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupFileInformationError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupFileInformationNotInitialized(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupDatabaseSchemaError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class YubiKeyBackendNotAvailableError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class YubiKeyNotPressedTimeout(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class ConfigMigrationError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class OsStatError(BackupException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)
