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


class InvalidStorageDefinitionName(AtbuException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class InvalidStorageDefinitionFile(AtbuException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class StorageDefinitionAlreadyExists(AtbuException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class StorageDefinitionNotFoundError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class StorageDefinitionNotCreatedError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class StorageDefinitionNotSpecifiedError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        super().__init__(message=message, cause=cause)


class PasswordAuthenticationFailure(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialInvalid(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialNotFoundError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialSecretDerivationError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialSecretFileNotFoundError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialTypeNotFoundError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class CredentialRequestInvalidError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupSelectionError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackingFileInformationNotFound(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class RestoreFilePathAlreadyExistsError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class VerifyFilePathNotFoundError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class VerifyFailure(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class BackupException(AtbuException):
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


class BackupFileInformationError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)


class YubiKeyBackendNotAvailableError(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)

class YubiKeyNotPressedTimeout(AtbuException):
    def __init__(self, message: str = None, cause=None):
        self._cause = cause
        super().__init__(message=message, cause=cause)
