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
r"""ATBU interface for Azure Blob Storage via azure-storage-blob portion
of the Azure SDK. Using azure-storage-blob allows for use of the more
robust Shared Access Signature (SAS) credentials.
"""

# pylint: disable=missing-class-docstring)

from typing import Iterator
from uuid import uuid4

from azure.storage.blob import (
    BlobServiceClient,
    ContainerClient,
    BlobClient,
)
from azure.core.exceptions import (
    ResourceExistsError,
    ServiceRequestError,
)

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
    StorageContainerInterface,
    StorageInterface,
    StorageObjectInterface,
)
from ..constants import *
from ..config import *

DEFAULT_AZURE_RETRY_EXCEPTIONS = (
    ServiceRequestError,
)

class AzureStorageObjectInterface(StorageObjectInterface):
    def __init__(self, storage_object: BlobClient):
        super().__init__()
        self.storage_object = storage_object

    @property
    def size(self):
        return self.storage_object.get_blob_properties().size

    @property
    def hash(self):
        return self.storage_object.get_blob_properties().content_settings.content_md5.hex()

    @property
    def name(self):
        return self.storage_object.blob_name


class AzureStorageContainerInterface(StorageContainerInterface):
    def __init__(self, container: ContainerClient):
        super().__init__()
        self.container = container

    @property
    def name(self) -> str:
        return self.container.container_name

    def get_object(self, object_name: str):
        blob = self.container.get_blob_client(blob=object_name)
        if not blob.exists():
            raise ObjectDoesNotExistError(
                f"The object {object_name} does not exist or was not found."
            )
        object_interface = AzureStorageObjectInterface(storage_object=blob)
        return object_interface

    def delete_object(self, object_name: str):
        blob = self.container.get_blob_client(blob=object_name)
        if blob.exists():
            blob.delete_blob()

    def list_objects(self, prefix: str = None) -> list[StorageObjectInterface]:
        blob_name_list = self.container.list_blob_names(name_starts_with=prefix)
        result: list[StorageObjectInterface] = []
        for bn in blob_name_list:
            blob_client = self.container.get_blob_client(blob=bn)
            result.append(AzureStorageObjectInterface(storage_object=blob_client))
        return result


class AzureStorageInterface(StorageInterface):

    def __init__(self, storage_def):
        super().__init__()
        self._retry_exceptions = DEFAULT_AZURE_RETRY_EXCEPTIONS
        self.storage_def: dict = storage_def
        self.driver_config: dict = self.storage_def[CONFIG_SECTION_DRIVER]
        self.blob_service_client = self._create_blob_service_client()

    @property
    def upload_chunk_size(self):
        max_block_size = 4*1024*1024
        try:
            max_block_size = self.blob_service_client._config.max_block_size
        except:
            pass
        return max_block_size

    @property
    def download_chunk_size(self):
        max_chunk_get_size = 4*1024*1024
        try:
            max_chunk_get_size = self.blob_service_client._config.max_chunk_get_size
        except:
            pass
        return max_chunk_get_size

    def _create_blob_service_client(self):
        password_type = self.driver_config.get(CONFIG_PASSWORD_TYPE)
        if password_type is None:
            raise ValueError(f"Credential type not found in configuration.")
        if password_type != CONFIG_PASSWORD_KIND_ACTUAL:
            raise ValueError(
                f"Expected either an Azure Blob Storage Access Key or SAS."
            )
        # For Azure Blob Storage:
        #   key is the storage account name
        #   secret is either the key (secret) or the SAS token.
        storage_account_name = self.driver_config[CONFIG_VALUE_NAME_DRIVER_STORAGE_KEY]
        # For Azure Blob Storage, the secret is either the access
        secret = self.driver_config[CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET]
        if isinstance(secret, (CredentialByteArray, bytearray, bytes)):
            secret = secret.decode("utf-8")
        blob_service_client = BlobServiceClient(
            account_url=f"https://{storage_account_name}.blob.core.windows.net",
            credential=secret,
        )
        return blob_service_client

    def get_container(self, container_name: str) -> StorageContainerInterface:
        container_client = self.blob_service_client.get_container_client(container=container_name)
        return AzureStorageContainerInterface(container=container_client)

    def _create_container(self, container_name: str) -> StorageContainerInterface:
        try:
            container_client = self.blob_service_client.create_container(name=container_name)
            return AzureStorageContainerInterface(container=container_client)
        except ResourceExistsError as ex:
            raise InvalidContainerNameError(
                f"Cannot create container '{container_name}' due to a conflict: {exc_to_string(ex)}"
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
        try:
            self.blob_service_client.delete_container(container=container_name)
        except Exception:  # pylint: disable=try-except-raise
            raise  # TBD any customizations.

    def upload_stream_to_object(
        self,
        container: StorageContainerInterface,
        object_name: str,
        stream,
        source_path: str,
    ):
        azure_container: AzureStorageContainerInterface = container
        azure_container.container.upload_blob(
            name=object_name,
            data=stream.get_iterator_only_proxy(),
        )

    def download_object_as_stream(
        self, storage_object: AzureStorageObjectInterface, chunk_size: int
    ) -> Iterator[bytes]:
        ssd = storage_object.storage_object.download_blob()
        for chunk in ssd.chunks():
            c = chunk
            yield chunk
