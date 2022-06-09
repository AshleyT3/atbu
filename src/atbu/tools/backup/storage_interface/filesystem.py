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
r"""Storage interface for local file system.
"""

from glob import iglob
from pathlib import Path
from typing import Iterator, Union
from uuid import uuid4

from atbu.common.exception import (
    exc_to_string,
    ObjectDoesNotExistError,
    ContainerAlreadyExistsError,
)

from .base import (
    AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR,
    StorageContainerInterface,
    StorageInterface,
    StorageObjectInterface,
)
from ..constants import *
from ..config import *
from ...persisted_info.file_info import FileInformation


def get_filesystem_storage_path(root: Union[Path, str], object_name: Union[Path, str]):
    if isinstance(root, str):
        root = Path(root)
    if isinstance(object_name, str):
        object_name = Path(object_name)
    # Path objects have parent . if just a single component.
    if object_name.parent != Path("."):
        raise ValueError("Object name is not just a name.")
    if len(str(object_name)) < 2:
        return root / object_name
    return root / str(object_name)[:2] / object_name


class FileSystemStorageObjectInterface(StorageObjectInterface):
    def __init__(self, object_path: Path):
        super().__init__()
        self.object_path: Path = convert_to_pathlib_path(object_path)
        self.file_info = FileInformation(path=str(object_path))

    @property
    def size(self):
        size_in_bytes = self.file_info.size_in_bytes
        return size_in_bytes

    @property
    def hash(self):
        digest = self.file_info.primary_digest
        return digest

    @property
    def name(self):
        return self.object_path.name


class FileSystemStorageContainerInterface(StorageContainerInterface):
    def __init__(self, container_root_path: Path):
        super().__init__()
        self.container_root_path = container_root_path

    @property
    def name(self) -> str:
        return self.container_root_path

    def get_object(self, object_name: str):
        desired_object_path = get_filesystem_storage_path(
            root=self.container_root_path, object_name=object_name
        )
        if not desired_object_path.is_file():
            raise ObjectDoesNotExistError(
                f"The file {str(desired_object_path)} does not exist or is not a file."
            )
        try:
            return FileSystemStorageObjectInterface(object_path=desired_object_path)
        except Exception as ex:
            logging.error(
                f"Unexpected error trying to access the file: "
                f"{str(desired_object_path)} {exc_to_string(ex)}"
            )
            raise

    def delete_object(self, object_name: str):
        desired_object_path = get_filesystem_storage_path(
            root=self.container_root_path, object_name=object_name
        )
        try:
            desired_object_path.unlink()
        except FileNotFoundError as ex:
            raise ObjectDoesNotExistError(
                f"The object {object_name} does not exist or was not found. {exc_to_string(ex)}"
            ).with_traceback(ex.__traceback__) from ex

    def list_objects(self, prefix: str = None) -> list[StorageObjectInterface]:
        result: list[StorageObjectInterface] = []
        if prefix:
            prefix = os.path.normcase(prefix)
        for p in iglob(os.path.join(self.container_root_path, "**"), recursive=True):
            if prefix:
                just_name = os.path.normcase(os.path.split(p)[1])
                if not just_name.startswith(prefix):
                    continue
            result.append(FileSystemStorageObjectInterface(object_path=p))
        return result


class FileSystemStorageInterface(StorageInterface):
    def __init__(self, storage_def):
        super().__init__()
        self.storage_def: dict = storage_def
        self.provider_id = storage_def[CONFIG_VALUE_NAME_PROVIDER]
        self.backup_root = Path(storage_def[CONFIG_VALUE_NAME_CONTAINER])

    def get_container(self, container_name: str) -> StorageContainerInterface:
        container_name_path = Path(container_name)
        if self.backup_root != container_name_path:
            raise ValueError(
                f"This file system interface only supports "
                f"accessing one container: container={self.backup_root}"
            )
        return FileSystemStorageContainerInterface(self.backup_root)

    def create_container(self, container_name: str) -> StorageContainerInterface:
        if container_name[-1] == AUTO_FIND_CREATE_CONTAINER_INDICATOR_CHAR:
            base_name = container_name[:-1]
            max_attempts = 1000
            while max_attempts > 0:
                max_attempts -= 1
                candidate = Path(f"{base_name}-{str(uuid4())}")
                if not candidate.exists():
                    candidate.mkdir(parents=True, exist_ok=True)
                    return self.get_container(container_name=candidate)
        else:
            candidate = Path(container_name)
            if candidate.exists():
                raise ContainerAlreadyExistsError(
                    f"FileSystemStorageInterface: The container already exists: {str(candidate)}"
                )
            candidate.mkdir(parents=True, exist_ok=True)
            return self.get_container(container_name=str(candidate))

    def delete_container(self, container_name: str):
        # TBD
        raise NotImplementedError()

    def upload_stream_to_object(
        self,
        container: StorageContainerInterface,
        object_name: str,
        stream,
        source_path: str,
    ):
        if not isinstance(container, FileSystemStorageContainerInterface):
            raise ValueError(
                f"The container is not an instance of FileSystemStorageContainerInterface"
            )
        fsc: FileSystemStorageContainerInterface = container
        if self.backup_root != fsc.container_root_path:
            raise ValueError(
                f"The container does not belong to this interface: "
                f"caller={fsc.container_root_path} this={fsc.container_root_path}"
            )
        storage_path = get_filesystem_storage_path(
            root=self.backup_root, object_name=object_name
        )
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(storage_path), "wb") as storage_file:
            for chunk in stream:
                storage_file.write(chunk)

    def download_object_as_stream(
        self, storage_object: FileSystemStorageObjectInterface, chunk_size: int
    ) -> Iterator[bytes]:
        storage_path = get_filesystem_storage_path(
            root=self.backup_root, object_name=storage_object.name
        )
        with open(str(storage_path), "rb") as storage_file:
            while True:
                b = storage_file.read(chunk_size)
                yield b
                if len(b) == 0:
                    break

    @property
    def retry_exceptions(self) -> tuple:
        return ()
