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
r"""ChunkSizeFileReader simplifies enforcing reading from a file
in byte chunks of a specified size. This is important for particular
APIs such as libcloud which expect to see data in specific chunk
sizes until the last chunk.
"""
from io import RawIOBase
from typing import Callable
from ..common.exception import AlreadyUsedError
from ..common.aes_cbc import AesCbcPaddingEncryptor

CHUNK_READER_CB_INPUT_BYTES = "input-bytes"
CHUNK_READER_CB_INPUT_BYTES_MANUAL_APPEND = "input-bytes-append"
CHUNK_READER_CB_CIPHERTEXT = "output-ciphertext"


class ChunkSizeFileReader:
    """Allows reading a file without encryption in chunks of the specified size.
    This is provided to allow consistent interfaces for reading chunk size
    bytes of a file as its encrypted as well as in cases where it is not encrypted.

    Instances can be used as an iterator or by manually calling methods.
    """

    def __init__(
        self,
        chunk_size,
        path,
        fileobj: RawIOBase,
        read_without_size: bool,
        user_func: Callable[[str, bytes], None]
    ):
        self._chunk_size = chunk_size
        self.path = path
        self._file = fileobj
        self.read_without_size = read_without_size
        self._eof_detected = False
        self._is_used = False
        self._user_func = user_func
        self._pending_output = bytes()

    def __iter__(self):
        return self

    def __next__(self):
        if self._eof_detected:
            raise StopIteration(f"No more chunks from file: {self.path}")
        chunk = self.read_chunk()
        return chunk

    def _checkused(self):
        if self._is_used:
            raise AlreadyUsedError(f"This instance cannot be used more than once.")

    def _call_user_func(self, what, data):
        if not self._user_func:
            return None
        return self._user_func(what, data)

    def open(self):
        self._checkused()
        if self._file:
            return
        self._file = open(self.path, "rb")

    def close(self):
        if not self._file:
            return
        self._checkused()
        self._file.close()
        self._file = None
        self._is_used = True

    def queue_data(self, bytes_to_queue, do_not_encrypt: bool = True):
        if not do_not_encrypt:
            raise ValueError(
                f"ChunkSizeFileReader: Encryption is not active, do_not_encrypt=False is disallowed."
            )
        self._checkused()
        if self._eof_detected:
            raise EOFError(
                f"EOF empty bytes already returned to indicate EOF, cannot call read again."
            )
        if not self._file:
            raise Exception(f"The file is not open.")
        if len(bytes_to_queue) == 0:
            raise ValueError(f"The data must contain bytes to write.")
        if len(self._pending_output) == 0:
            # If caller passes bytearray, things work fine here but certain APIs
            # reading chunks choke on bytearray instead of bytes. Regardless,
            # our internal type is be consistent, not defined by caller's insertion
            # using bytearray. At this time insert using write_data is minimal and
            # read_chunk attempts to align on chunk bytes reads to mitigate copying.
            self._pending_output = bytes(bytes_to_queue)
        else:
            self._pending_output += bytes_to_queue
        self._call_user_func(CHUNK_READER_CB_INPUT_BYTES, bytes_to_queue)

    def read_chunk(self):
        self._checkused()
        if self._eof_detected:
            raise EOFError(
                f"EOF empty bytes already returned to indicate EOF, cannot call read again."
            )
        if not self._file:
            raise Exception(
                f"This instance must be entered and not closed in order to properly exit."
            )
        while len(self._pending_output) < self._chunk_size:
            size_to_read = None
            if not self.read_without_size:
                size_to_read = self._chunk_size - len(self._pending_output)
            new_file_bytes = self._file.read(size_to_read)
            if len(new_file_bytes) == 0:
                break
            self._call_user_func(CHUNK_READER_CB_INPUT_BYTES, new_file_bytes)
            if len(self._pending_output) == 0:
                self._pending_output = new_file_bytes
            else:
                self._pending_output += new_file_bytes

        if len(self._pending_output) <= self._chunk_size:
            bytes_to_return = self._pending_output
            self._pending_output = bytes()
        else:
            bytes_to_return = self._pending_output[: self._chunk_size]
            self._pending_output = self._pending_output[self._chunk_size :]
        self._eof_detected = len(bytes_to_return) == 0
        return bytes_to_return

    def read(self, size):
        if size != self._chunk_size:
            raise Exception(
                f"You are only allowed to read chunk sizes of {self._chunk_size} bytes from this instance."
            )
        return self.read_chunk()

    def __enter__(self):
        self._checkused()
        if self._file:
            return self
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._checkused()
        if not self._file:
            raise Exception(
                f"This instance must be entered and not closed in order to properly exit."
            )
        self.close()
        return False


class ChunkSizeEncryptorReader(ChunkSizeFileReader):
    """Read ciphertext of file encrypted with AesCbcPaddingEncryptor in specified chunk size.
    The read_chunk() method will always return one chunk until EOF at which time the remaining
    ciphertext is returned after which zero bytes. This class effectively hides the details of
    any internal overhead or buffering of AesCbcPaddingEncryptor, allowing users of this class
    to see clean chunk sizes of ciphertext until EOF.
    """

    def __init__(
        self,
        chunk_size,
        path,
        fileobj: RawIOBase,
        read_without_size: bool,
        encryptor: AesCbcPaddingEncryptor,
        user_func: Callable[[str, bytes], None],
    ):
        super().__init__(
            chunk_size=chunk_size,
            path=path,
            fileobj=fileobj,
            read_without_size=read_without_size,
            user_func=user_func
        )
        if not isinstance(encryptor, AesCbcPaddingEncryptor):
            raise ValueError(
                f"The encryptor must be an instance of AesCbcPaddingEncryptor."
            )
        self.encryptor = encryptor

    @property
    def is_encryption_finished(self):
        return self.encryptor.finalize

    def queue_data(self, bytes_to_queue, do_not_encrypt: bool = False):
        """Queues data to be read as part of a chunk during a subsequent call to read_chunk.
        This method offers a way to "insert" data into the stream obtained via read_chunk.

        Specify do_not_encrypt=True to insert information which should not be encrypted. This would
        usually only be used at the start of writing to include unecrypted prefix information in a
        storage blob, information such as backup format versioning and option bits, IVs, etc.
        """
        self._checkused()
        if self._eof_detected:
            raise EOFError(
                f"EOF empty bytes already returned to indicate EOF, cannot call read again."
            )
        if not self._file:
            raise Exception(f"The file is not open.")
        if len(bytes_to_queue) == 0:
            raise ValueError(f"The data must contain bytes to write.")
        self._call_user_func(CHUNK_READER_CB_INPUT_BYTES_MANUAL_APPEND, bytes_to_queue)
        if do_not_encrypt:
            if len(self._pending_output) == 0:
                self._pending_output = bytes_to_queue
            else:
                self._pending_output += bytes_to_queue
        else:
            new_cipher_text = self.encryptor.update(input_bytes=bytes_to_queue)
            if len(new_cipher_text) > 0:
                self._call_user_func(CHUNK_READER_CB_CIPHERTEXT, new_cipher_text)
                if len(self._pending_output) == 0:
                    self._pending_output = new_cipher_text
                else:
                    self._pending_output += new_cipher_text

    def read_chunk(self):
        self._checkused()
        if self._eof_detected:
            raise EOFError(
                f"EOF empty bytes already returned to indicate EOF, cannot call read again."
            )
        if not self._file:
            raise Exception(f"The file is not open.")

        if self.encryptor.is_finalized:
            if len(self._pending_output) <= self._chunk_size:
                ciphertext_chunk_to_return = self._pending_output
                self._pending_output = bytes()
            else:
                ciphertext_chunk_to_return = self._pending_output[: self._chunk_size]
                self._pending_output = self._pending_output[self._chunk_size :]
            self._eof_detected = len(ciphertext_chunk_to_return) == 0
            return ciphertext_chunk_to_return

        while len(self._pending_output) < self._chunk_size:
            size_to_read = None
            if not self.read_without_size:
                size_to_read = self._chunk_size - len(self._pending_output) + (self.encryptor.BLOCK_SIZE * 3)
            plaintext_bytes = self._file.read(size_to_read)
            if len(plaintext_bytes) == 0:
                new_cipher_text = self.encryptor.finalize()
            else:
                new_cipher_text = self.encryptor.update(input_bytes=plaintext_bytes)
                self._call_user_func(CHUNK_READER_CB_INPUT_BYTES, plaintext_bytes)
            self._pending_output += new_cipher_text
            if len(new_cipher_text) > 0:
                self._call_user_func(CHUNK_READER_CB_CIPHERTEXT, new_cipher_text)
            if len(plaintext_bytes) == 0:
                break

        if len(self._pending_output) <= self._chunk_size:
            ciphertext_chunk_to_return = self._pending_output
            self._pending_output = bytes()
        else:
            ciphertext_chunk_to_return = self._pending_output[: self._chunk_size]
            self._pending_output = self._pending_output[self._chunk_size :]

        self._eof_detected = len(ciphertext_chunk_to_return) == 0
        return ciphertext_chunk_to_return


def open_chunk_reader(
    chunk_size,
    path,
    fileobj: RawIOBase,
    read_without_size: bool,
    encryptor: AesCbcPaddingEncryptor,
    user_func: Callable[[str, bytes], None],
):
    if encryptor:
        return ChunkSizeEncryptorReader(
            chunk_size=chunk_size,
            path=path,
            fileobj=fileobj,
            read_without_size=read_without_size,
            encryptor=encryptor,
            user_func=user_func,
        )
    return ChunkSizeFileReader(
        chunk_size=chunk_size,
        path=path,
        fileobj=fileobj,
        read_without_size=read_without_size,
        user_func=user_func,
    )
