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

r"""Base for ATBU storage interface abstraction, both decoupling ATBU from
other APIs, and providing ATBU itself a common storage interface for its
focused needs.
"""

from abc import ABC, abstractmethod
from socket import gaierror
from http.client import NotConnected, ImproperConnectionState
from typing import Iterator

from atbu.common.exception import RetryLimitReached

from ..constants import *
from ..config import *
from ..exception import BackupException

CHUNK_SIZE_5MB = 5 * 1024 * 1024
CHUNK_SIZE_50MB = 50 * 1024 * 1024
DEFAULT_CHUNK_UPLOAD_SIZE = CHUNK_SIZE_5MB
DEFAULT_CHUNK_DOWNLOAD_SIZE = CHUNK_SIZE_50MB
DEFAULT_MAX_SIMULTANEOUS_FILE_BACKUPS = 5

DEFAULT_RETRY_EXCEPTIONS = (
    OSError,
    gaierror,
    NotConnected,
    ImproperConnectionState,
    RetryLimitReached,
)

AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR = "*"


class StorageObjectInterface(ABC):
    def __init__(self):
        pass

    @property
    @abstractmethod
    def size(self):
        return None

    @property
    @abstractmethod
    def hash(self):
        return None

    @property
    @abstractmethod
    def name(self):
        return None


class StorageContainerInterface(ABC):
    def __init__(self):
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def get_object(self, object_name: str) -> StorageObjectInterface:
        pass

    @abstractmethod
    def delete_object(self, object_name: str):
        pass

    @abstractmethod
    def list_objects(self, prefix: str = None) -> list[StorageObjectInterface]:
        pass


class StorageInterface(ABC):
    def __init__(self):
        self._retry_exceptions = list(DEFAULT_RETRY_EXCEPTIONS)

    @property
    def upload_chunk_size(self):
        return DEFAULT_CHUNK_UPLOAD_SIZE

    @property
    def download_chunk_size(self):
        return DEFAULT_CHUNK_DOWNLOAD_SIZE

    @abstractmethod
    def get_container(self, container_name: str) -> StorageContainerInterface:
        pass

    @abstractmethod
    def create_container(self, container_name: str) -> StorageContainerInterface:
        pass

    @abstractmethod
    def delete_container(self, container_name: str):
        pass

    @abstractmethod
    def upload_stream_to_object(
        self,
        container: StorageContainerInterface,
        object_name: str,
        stream,
        source_path: str,
    ):
        pass

    @abstractmethod
    def download_object_as_stream(
        self, storage_object: StorageObjectInterface, chunk_size: int
    ) -> Iterator[bytes]:
        pass

    @property
    def retry_exceptions(self):
        return self._retry_exceptions


class StorageInterfaceFactory:
    def __init__(self, storage_def_dict):
        self.storage_def_dict = storage_def_dict

    @property
    def interface_type(self):
        return self.storage_def_dict[CONFIG_VALUE_NAME_INTERFACE_TYPE]

    @property
    def provider_name(self):
        return self.storage_def_dict[CONFIG_VALUE_NAME_PROVIDER]

    def create_storage_interface(self) -> StorageInterface:
        # pylint: disable=import-outside-toplevel
        desired_interface = self.storage_def_dict[CONFIG_VALUE_NAME_INTERFACE_TYPE]
        if desired_interface == CONFIG_INTERFACE_TYPE_LIBCLOUD:
            from .libcloud import LibCloudStorageInterface

            return LibCloudStorageInterface(storage_def=self.storage_def_dict)
        elif desired_interface == CONFIG_INTERFACE_TYPE_AZURE:
            from .azure import AzureStorageInterface

            return AzureStorageInterface(storage_def=self.storage_def_dict)
        elif desired_interface == CONFIG_INTERFACE_TYPE_GOOGLE:
            from .google import GoogleStorageInterface

            return GoogleStorageInterface(storage_def=self.storage_def_dict)
        elif desired_interface == CONFIG_INTERFACE_TYPE_FILESYSTEM:
            from .filesystem import FileSystemStorageInterface

            return FileSystemStorageInterface(storage_def=self.storage_def_dict)
        else:
            raise BackupException(f"Unknown interface type: {desired_interface}")

    @staticmethod
    def create_factory_from_storage_def_name(storage_def_name: str):
        atbu_cfg, _, _ = AtbuConfig.access_cloud_storage_config(
            storage_def_name=storage_def_name,
            must_exist=True,
            create_if_not_exist=False,
        )
        storage_def_dict = atbu_cfg.get_storage_def_with_resolved_secrets_deep_copy(
            storage_def_name=storage_def_name
        )
        return StorageInterfaceFactory(storage_def_dict=storage_def_dict)
