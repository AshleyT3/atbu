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
r"""ATBU interface for libcloud.
"""

from typing import Iterator
from uuid import uuid4
import libcloud.storage.types
from libcloud.storage.providers import get_driver
import libcloud.storage.base
from libcloud.storage.drivers.azure_blobs import (
    AZURE_DOWNLOAD_CHUNK_SIZE,
    AZURE_UPLOAD_CHUNK_SIZE,
)
from libcloud.utils.retry import RETRY_EXCEPTIONS

from atbu.common.exception import (
    exc_to_string,
    ObjectDoesNotExistError,
    InvalidContainerNameError,
    ContainerAlreadyExistsError,
    ContainerAutoCreationFailed,
)

from ..credentials import CredentialByteArray
from .base import (
    AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR,
    DEFAULT_CHUNK_DOWNLOAD_SIZE,
    DEFAULT_CHUNK_UPLOAD_SIZE,
    StorageContainerInterface,
    StorageInterface,
    StorageObjectInterface,
)
from ..constants import *
from ..config import *


class LibCloudStorageObjectInterface(StorageObjectInterface):
    def __init__(self, storage_object):
        super().__init__()
        self.storage_object: libcloud.storage.base.Object = storage_object

    @property
    def size(self):
        return self.storage_object.size

    @property
    def hash(self):
        return self.storage_object.hash

    @property
    def name(self):
        return self.storage_object.name


class LibCloudStorageContainerInterface(StorageContainerInterface):
    def __init__(self, container: libcloud.storage.base.Container):
        super().__init__()
        self.container = container

    @property
    def name(self) -> str:
        return self.container.name

    def get_object(self, object_name: str):
        try:
            object_interface = LibCloudStorageObjectInterface(
                storage_object=self.container.get_object(object_name)
            )
        except libcloud.storage.types.ObjectDoesNotExistError as ex:
            raise ObjectDoesNotExistError(
                f"The object {object_name} does not exist or was not found. {exc_to_string(ex)}",
                ex,
            ).with_traceback(ex.__traceback__) from ex
        return object_interface

    def delete_object(self, object_name: str):
        try:
            o = self.container.get_object(object_name=object_name)
            self.container.delete_object(o)
        except libcloud.storage.types.ObjectDoesNotExistError as ex:
            raise ObjectDoesNotExistError(
                f"The object {object_name} does not exist or was not found. {exc_to_string(ex)}",
                ex,
            ).with_traceback(ex.__traceback__) from ex

    def list_objects(self, prefix: str = None) -> list[StorageObjectInterface]:
        olist = self.container.list_objects(prefix=prefix)
        result: list[StorageObjectInterface] = []
        for o in olist:
            result.append(LibCloudStorageObjectInterface(storage_object=o))
        return result


class LibCloudStorageInterface(StorageInterface):
    def __init__(self, storage_def):
        super().__init__()
        self.provider_id = storage_def[CONFIG_VALUE_NAME_PROVIDER]
        self.libcloud_driver_class: libcloud.storage.base.StorageDriver = get_driver(
            self.provider_id
        )
        if storage_def[CONFIG_SECTION_DRIVER].get(CONFIG_PASSWORD_TYPE):
            # Remove constructor argument that will be rejected by Libcloud.
            del storage_def[CONFIG_SECTION_DRIVER][CONFIG_PASSWORD_TYPE]
        driver_parameters = dict(storage_def[CONFIG_SECTION_DRIVER])
        secret = driver_parameters[CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET]
        if isinstance(secret, (CredentialByteArray, bytearray, bytes)):
            secret = secret.decode("utf-8")
        driver_parameters[CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET] = secret
        self.storage_driver: libcloud.storage.base.StorageDriver = (
            self.libcloud_driver_class(**driver_parameters)
        )

    @property
    def upload_chunk_size(self):
        chunk_size = DEFAULT_CHUNK_UPLOAD_SIZE
        # Add exceptions to the default upload chunk size here.
        if self.provider_id == libcloud.storage.types.Provider.AZURE_BLOBS:
            chunk_size = AZURE_UPLOAD_CHUNK_SIZE
        return chunk_size

    @property
    def download_chunk_size(self):
        chunk_size = DEFAULT_CHUNK_DOWNLOAD_SIZE
        # Add exceptions to the default download chunk size here.
        # Libcloud download_object_as_stream will silently change
        # caller-specified chunk_size without caller knowing, breaking
        # assumption that chunk size will be max until possibly final
        # chunk.
        if self.provider_id == libcloud.storage.types.Provider.AZURE_BLOBS:
            chunk_size = AZURE_DOWNLOAD_CHUNK_SIZE
        return chunk_size

    def get_container(self, container_name: str) -> StorageContainerInterface:
        return LibCloudStorageContainerInterface(
            self.storage_driver.get_container(container_name=container_name)
        )

    def _create_container(self, container_name: str) -> StorageContainerInterface:
        try:
            return LibCloudStorageContainerInterface(
                self.storage_driver.create_container(container_name=container_name)
            )
        except libcloud.storage.types.ContainerAlreadyExistsError as ex:
            raise ContainerAlreadyExistsError(
                f"The storage container {container_name} already exists. {exc_to_string(ex)}"
            ) from ex
        except libcloud.storage.types.InvalidContainerNameError as ex:
            raise InvalidContainerNameError(
                f"The storage container {container_name} is invalid. {exc_to_string(ex)}"
            ) from ex

    def create_container(self, container_name: str) -> StorageContainerInterface:
        if container_name[-1] != AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR:
            return self._create_container(container_name=container_name)
        else:
            base_name = container_name[:-1]
            max_attempts = 100
            attempts_remaining = max_attempts
            while True:
                attempts_remaining -= 1
                candidate = f"{base_name}-{str(uuid4())}"
                try:
                    ci = self._create_container(container_name=candidate)
                    return ci
                except (ContainerAlreadyExistsError, InvalidContainerNameError) as ex:
                    if attempts_remaining <= 0:
                        raise ContainerAutoCreationFailed(
                            f"Automatic container creation failed after {max_attempts} attempts. "
                            f"{exc_to_string(ex)}"
                        ) from ex

    def delete_container(self, container_name: str):
        c = self.storage_driver.get_container(container_name=container_name)
        self.storage_driver.delete_container(container=c)

    def upload_stream_to_object(
        self,
        container: StorageContainerInterface,
        object_name: str,
        stream,
        source_path: str,
    ):
        self.storage_driver.upload_object_via_stream(
            iterator=stream.get_iterator_only_proxy(),
            container=container.container,
            object_name=object_name,
        )

    def download_object_as_stream(
        self, storage_object: LibCloudStorageObjectInterface, chunk_size: int
    ) -> Iterator[bytes]:
        return self.storage_driver.download_object_as_stream(
            obj=storage_object.storage_object, chunk_size=chunk_size
        )

    @property
    def retry_exceptions(self) -> tuple:
        return RETRY_EXCEPTIONS
