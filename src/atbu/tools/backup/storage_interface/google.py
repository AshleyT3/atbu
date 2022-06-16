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
r"""ATBU interface for Google Cloud Storage as used via ResumableUpload and
ChunkedDownload. At the time of ATBU initial implementation, libcloud did not
support GCS multipart upload.
"""

# pylint: disable=missing-class-docstring)

from concurrent.futures import ThreadPoolExecutor
import os
import queue
import threading
import time
from typing import Iterator
from uuid import uuid4
import requests
from google.cloud import storage
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from google.resumable_media.requests import ResumableUpload, ChunkedDownload
from google.resumable_media.common import InvalidResponse, RetryStrategy
import google.api_core.exceptions

from atbu.common.exception import (
    exc_to_string,
    RetryLimitReached,
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
    DEFAULT_CHUNK_UPLOAD_SIZE,
)
from ..constants import *
from ..storage_interface import base
from ..config import *

DEFAULT_RETRY_EXCEPTIONS = base.DEFAULT_RETRY_EXCEPTIONS + (InvalidResponse,)
TWO_DAYS_IN_SECONDS = 60 * 60 * 24 * 2
DEFAULT_RETRY_SECONDS = TWO_DAYS_IN_SECONDS


class WriteableQueueIterator:
    """Emulates stream.write(bytes) that ChunkedUpload expects.
    Allows to be read as iterator.
    """

    def __init__(self):
        self.queue = queue.Queue()
        self.finished = False

    def write(self, b):
        self.queue.put(b)

    def _checkiter(self):
        if self.finished:
            raise StopIteration(
                f"Iterator already observed 0-byte chunk, iteration already finished."
            )

    def __iter__(self):
        self._checkiter()
        return self

    def __next__(self):
        self._checkiter()
        chunk = self.queue.get()
        if len(chunk) == 0:
            self.finished = True
        return chunk


class GoogleStorageObjectInterface(StorageObjectInterface):
    def __init__(self, storage_object: storage.Blob):
        super().__init__()
        self.storage_object = storage_object

    @property
    def size(self):
        return self.storage_object.size

    @property
    def hash(self):
        return self.storage_object.md5_hash

    @property
    def name(self):
        return self.storage_object.name


class GoogleStorageContainerInterface(StorageContainerInterface):
    def __init__(self, container: storage.Bucket):
        super().__init__()
        self.container = container

    @property
    def name(self) -> str:
        return self.container.name

    def get_object(self, object_name: str):
        try:
            blob = self.container.get_blob(blob_name=object_name)
        except google.api_core.exceptions.RetryError as ex:
            raise RetryLimitReached(
                f"Retry limit reached while trying to access blob "
                f"{object_name} of container {self.container.name}. "
                f"{exc_to_string(ex)}",
                ex,
            ) from ex
        if blob is None:
            raise ObjectDoesNotExistError(
                f"The object {object_name} does not exist or was not found."
            )
        object_interface = GoogleStorageObjectInterface(storage_object=blob)

        return object_interface

    def delete_object(self, object_name: str):
        try:
            self.container.delete_blob(object_name)
        except google.cloud.exceptions.NotFound as ex:
            raise ObjectDoesNotExistError(
                f"The object {object_name} does not exist or was not found. {exc_to_string(ex)}"
            ).with_traceback(ex.__traceback__) from ex

    def list_objects(self, prefix: str = None) -> list[StorageObjectInterface]:
        blob_list = self.container.list_blobs(prefix=prefix)
        result: list[StorageObjectInterface] = []
        for b in blob_list:
            result.append(GoogleStorageObjectInterface(storage_object=b))
        return result


class GoogleStorageInterface(StorageInterface):

    class_lock = threading.Lock()
    _thread_exec = None

    @classmethod
    def _class_init(cls):
        with cls.class_lock:
            if cls._thread_exec is None:
                cls._thread_exec = ThreadPoolExecutor(
                    thread_name_prefix="GoogleStorageInterface-downloader"
                )

    def __init__(self, storage_def):
        GoogleStorageInterface._class_init()
        super().__init__()
        self.storage_def: dict = storage_def
        self.driver_config: dict = self.storage_def[CONFIG_SECTION_DRIVER]
        self.project_name = self.driver_config[CONFIG_VALUE_NAME_DRIVER_STORAGE_PROJECT]
        self.scoped_credentials = self._create_credential()

    def _create_credential(self):
        password_type = self.driver_config.get(CONFIG_PASSWORD_TYPE)
        if password_type is None:
            raise f"Credential type not found in configuration."
        secret = self.driver_config[CONFIG_VALUE_NAME_DRIVER_STORAGE_SECRET]
        if isinstance(secret, (CredentialByteArray, bytearray, bytes)):
            secret = secret.decode("utf-8")
        if password_type == CONFIG_PASSWORD_TYPE_FILENAME:
            # For OAuth 2 .json, referencing the file location would be more likely.
            credentials = service_account.Credentials.from_service_account_file(
                filename=secret
            )
        elif password_type == CONFIG_PASSWORD_TYPE_ENVVAR:
            if secret is None or secret == "":
                raise ValueError(f"Environment variable not found")
            cred_filename = os.getenv(secret)
            credentials = service_account.Credentials.from_service_account_file(
                cred_filename
            )
        else:
            raise ValueError(f"Unknown credential type '{password_type}'.")
        scoped_credentials = credentials.with_scopes(
            ["https://www.googleapis.com/auth/devstorage.read_write"]
        )
        return scoped_credentials

    def _create_session(self):
        return AuthorizedSession(credentials=self.scoped_credentials)

    def get_container(self, container_name: str) -> StorageContainerInterface:
        storage_client = storage.Client(
            project=self.project_name, credentials=self.scoped_credentials
        )
        bucket = storage_client.bucket(container_name)
        return GoogleStorageContainerInterface(container=bucket)

    def _create_container(self, container_name: str) -> StorageContainerInterface:
        try:
            storage_client = storage.Client(
                project=self.project_name, credentials=self.scoped_credentials
            )
            bucket = storage_client.create_bucket(bucket_or_name=container_name)
            return GoogleStorageContainerInterface(container=bucket)
        except google.api_core.exceptions.Conflict as ex:
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
            storage_client = storage.Client(
                project=self.project_name, credentials=self.scoped_credentials
            )
            b = storage_client.get_bucket(container_name)
            b.delete()
        except Exception:  # pylint: disable=try-except-raise
            raise  # TBD any customizations.

    def upload_stream_to_object(
        self,
        container: StorageContainerInterface,
        object_name: str,
        stream,
        source_path: str,
    ):
        # pylint: disable=too-many-locals
        session = self._create_session()
        session.headers["x-goog-project-id"] = self.project_name
        url_template = (
            "https://www.googleapis.com/upload/storage/v1/b/{bucket}/o?"
            "uploadType=resumable"
        )
        upload_url = url_template.format(
            bucket=self.storage_def[CONFIG_VALUE_NAME_CONTAINER]
        )
        metadata = {"name": object_name}
        upload = ResumableUpload(upload_url, DEFAULT_CHUNK_UPLOAD_SIZE)
        upload._retry_strategy = RetryStrategy(  # pylint: disable=protected-access
            max_sleep=30, max_cumulative_retry=DEFAULT_RETRY_SECONDS
        )
        response = upload.initiate(
            transport=session,
            stream=stream,
            metadata=metadata,
            content_type="application/octet-stream",
            stream_final=False,
        )
        logging.debug(
            f"Uploading: project={self.project_name} container={container.name} "
            f"object={object_name}: UploadID={response.headers['X-GUploader-UploadID']} "
            f"from source_path={source_path}"
        )
        logging.info(f"Backing up: {source_path}")
        perf_seconds_start = time.perf_counter()
        chunk_number = 1
        pos_before_xmit = 0
        while not upload.finished:
            last_bytes_uploaded = upload.bytes_uploaded
            try:
                seconds_running = time.perf_counter() - perf_seconds_start
                logging.debug(
                    f"Uploading chunk {chunk_number} at {seconds_running:.3f} "
                    f"seconds into the backup. "
                    f"source_path={source_path} dest={container.name}:{object_name}"
                )
                pos_before_xmit = stream.tell()
                response = upload.transmit_next_chunk(session)
                logging.debug(
                    f"upload_stream_to_object: " f"chunk upload response={response}"
                )
                logging.debug(
                    f"upload_stream_to_object: "
                    f"chunk bytes uploaded={upload.bytes_uploaded - last_bytes_uploaded}"
                )
                logging.debug(
                    f"upload_stream_to_object: "
                    f"total bytes uploaded={upload.bytes_uploaded}"
                )
                chunk_number += 1
            except Exception as ex:
                # We cannot be certain of the exception being caused by final timeout or not.
                # Generally, we may observe MaxRetryError but that is for the inner connection
                # error so it is a MaxRetryError of each attempt, where we will see the last one.
                # There is currently no "RetryStrategyLimitReached" exception, for example, so we
                # sample time running to determine if the retry strategy limit has been reached.
                seconds_running = time.perf_counter() - perf_seconds_start
                pos_after_xmit = stream.tell()
                chunk_size = pos_after_xmit - pos_before_xmit
                logging.error(
                    f"Chunk upload of {chunk_size} bytes via transmit_next_chunk failed. "
                    f"seconds_running={seconds_running:.3f}"
                    f"upload.invalid={upload.invalid} pos_before={pos_before_xmit} "
                    f"pos_after={pos_after_xmit} {exc_to_string(ex)}"
                )
                # Has retry strategy limit been reached?
                if seconds_running >= DEFAULT_RETRY_SECONDS:
                    raise RetryLimitReached(
                        f"Backup file write failed after "
                        f"{seconds_running:.3f} overall retry time. "
                        f"{exc_to_string(ex)}",
                        ex,
                    ) from ex
                # Attempt to recover.
                if not upload.invalid:
                    # When transmit_next_chunk exhausts timeout, it can raise without
                    # setting invalid=True which will cause recover to fail. Alteratively,
                    # we could do the following and skip recover which works...
                    #     if stream.tell() != pos_before_xmit:
                    #         stream.seek(pos_before_xmit, SEEK_SET)
                    # The following _make_invalid is what ResumableUpload does internally
                    # for other exceptions so is done here.
                    upload._make_invalid()  # pylint: disable=protected-access
                # Attempt to recover. This seems to essentially amount to pinging the server
                # for its notion of the current range for the upload, where that by itself
                # validates connection is good, and the mutual understanding, and recover
                # rewinds stream back to start of last read chunk so transmit_next_chunk
                # can perform the re-read and retry.
                response: requests.Response = upload.recover(session)
                logging.warning(f"recover result={response}")
        # json_response = response.json()
        # logging.debug(f"json_response={json_response}")

    def download_object_as_stream(
        self, storage_object: GoogleStorageObjectInterface, chunk_size: int
    ) -> Iterator[bytes]:
        def _internal_feed_stream_download(download, stream):
            # pylint: disable=unused-variable
            perf_seconds_start = time.perf_counter()
            try:
                while not download.finished:
                    try:
                        response = download.consume_next_chunk(
                            session
                        )  # pylint: disable=unused-variable
                        # logging.debug(
                        #     f"finished={download.finished} "
                        #     f"read={len(r.content)} chunk_size={chunk_size}"
                        # )
                        # logging.debug(f"Content-Length={r.headers['Content-Length']}")
                        # logging.debug(f"Content-Range={r.headers['Content-Range']}")
                        # logging.debug(f"status_code: r={r.status_code}")
                    except Exception as ex:
                        seconds_running = time.perf_counter() - perf_seconds_start
                        if seconds_running >= DEFAULT_RETRY_SECONDS:
                            raise RetryLimitReached(
                                f"Backup file write failed after {seconds_running:.3f} "
                                f"overall retry time. {exc_to_string(ex)}",
                                ex,
                            ) from ex
                        if download.invalid:
                            raise RetryLimitReached(
                                f"The download object is invalid, cannot retry. "
                                f"Backup file write failed after {seconds_running:.3f} "
                                f"overall retry time. ex={ex}",
                                ex,
                            ) from ex
            finally:
                if not stream.finished:
                    stream.write(bytes())

        session = self._create_session()
        session.headers["x-goog-project-id"] = self.project_name
        url_template = "https://www.googleapis.com/download/storage/v1/b/{bucket}/o/{blob_name}?alt=media"
        download_url = url_template.format(
            bucket=self.storage_def[CONFIG_VALUE_NAME_CONTAINER],
            blob_name=storage_object.name,
        )
        stream = WriteableQueueIterator()
        download = ChunkedDownload(
            media_url=download_url, chunk_size=chunk_size, stream=stream
        )
        download._retry_strategy = RetryStrategy(  # pylint: disable=protected-access
            max_sleep=30, max_cumulative_retry=DEFAULT_RETRY_SECONDS
        )

        future = GoogleStorageInterface._thread_exec.submit(
            _internal_feed_stream_download, download, stream
        )
        try:
            for c in stream:
                if not future.running():
                    future.result()
                yield c
        finally:
            future.result()

    @property
    def retry_exceptions(self) -> tuple:
        return self._retry_exceptions
