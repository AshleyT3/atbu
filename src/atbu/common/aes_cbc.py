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
r"""AES CBS paddeded encryptor/decryptor. Encrypt a given plaintext such that
the resulting ciphertext is padded to the block size (16-bytes).
"""

from abc import ABC, abstractmethod
from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    algorithms,
    modes,
    CipherContext,
)
from .exception import AlreadyFinalizedError, EncryptionDecryptionFailure


class AES_CBC_Base(ABC):
    """The base for both the encryptor/decryptor. Provides common 'update' functionality."""

    BLOCK_SIZE: int = 16

    def __init__(self, cc: CipherContext, _max_block_retention: int):
        self._buffered_data = bytearray()
        self._cc = cc
        self._num_block_retention = _max_block_retention
        self._num_byte_retention = AES_CBC_Base.BLOCK_SIZE * self._num_block_retention
        self._finished = False

    @property
    def is_finalized(self):
        return self._finished

    @property
    @abstractmethod
    def IV(self):
        pass

    def update(self, input_bytes: bytes) -> bytes:
        return self._process_data(input_bytes)

    def _process_data(self, data: bytes) -> bytes:
        if self._finished:
            raise AlreadyFinalizedError(f"Instance already finalized.")
        output_text = None
        self._buffered_data.extend(data)
        blocks_available = int(len(self._buffered_data) / AES_CBC_Base.BLOCK_SIZE)
        remainder_available = int(len(self._buffered_data) % AES_CBC_Base.BLOCK_SIZE)
        if remainder_available > 0:
            # Given padding, a remaining amount implies an eventual retained block.
            blocks_to_update = blocks_available
        else:
            # No remainder, subtract retention requirement.
            blocks_to_update = blocks_available - self._num_block_retention
        if blocks_to_update <= 0:
            return bytes()
        bytes_to_update = blocks_to_update * AES_CBC_Base.BLOCK_SIZE
        if bytes_to_update > 0:
            output_text = self._cc.update(self._buffered_data[:bytes_to_update])
            del self._buffered_data[:bytes_to_update]
            if len(self._buffered_data) > max(
                self._num_byte_retention, AES_CBC_Base.BLOCK_SIZE - 1
            ):
                raise EncryptionDecryptionFailure(
                    f"Buffered data of {len(self._buffered_data)} bytes is unexpectedly too much."
                )
        return output_text


class AesCbcPaddingEncryptor(AES_CBC_Base):
    """AES CBC padding encryptor."""

    def __init__(self, key: bytes, IV: bytes):
        super().__init__(
            Cipher(algorithms.AES(key), modes.CBC(IV)).encryptor(),
            _max_block_retention=0,
        )
        self._key = key
        self._IV = IV

    @property
    def IV(self):
        return self._IV

    def finalize(self) -> bytes:
        if self._finished:
            raise AlreadyFinalizedError(f"Instance already finalized.")
        self._finished = True
        #
        # For the encryptor, the length of self._buffered_data should be
        # zero to BLOCK_SIZE-1.
        #
        if len(self._buffered_data) >= AES_CBC_Base.BLOCK_SIZE:
            raise EncryptionDecryptionFailure(
                f"Encryption failed: "
                f"Block size {len(self._buffered_data)} is unexpected. "
                f"Expected no more than {AES_CBC_Base.BLOCK_SIZE - 1} bytes."
            )
        padding_needed = AES_CBC_Base.BLOCK_SIZE - len(self._buffered_data)
        for _ in range(0, padding_needed):
            self._buffered_data.append(padding_needed)
        ciphertext = self._cc.update(self._buffered_data) + self._cc.finalize()
        return ciphertext


class AesCbcPaddingDecryptor(AES_CBC_Base):
    """AES CBC padding decryptor."""

    def __init__(self, key: bytes, IV: bytes):
        self._key = key
        self._IV = IV
        super().__init__(
            cc=Cipher(algorithms.AES(self._key), modes.CBC(self._IV)).decryptor(),
            _max_block_retention=1,
        )

    @property
    def IV(self):
        return self._IV

    def finalize(self) -> bytes:
        if self._finished:
            raise AlreadyFinalizedError(f"Instance already finalized.")
        self._finished = True
        if len(self._buffered_data) != self._num_byte_retention:
            raise EncryptionDecryptionFailure(
                f"Decryption failed: "
                f"Final data of {len(self._buffered_data)} bytes is unexpected. "
                f"Expected {self._num_byte_retention} or more bytes."
            )
        plaintext = self._cc.update(self._buffered_data) + self._cc.finalize()
        amount_of_padding = int(plaintext[-1])
        if amount_of_padding > AES_CBC_Base.BLOCK_SIZE:
            raise EncryptionDecryptionFailure(
                f"Decryption failed: "
                f"Last block end byte is {plaintext[-1]} which is an unexpected padding byte."
            )
        first_padding_index = AES_CBC_Base.BLOCK_SIZE - amount_of_padding
        for i in range(first_padding_index, first_padding_index + amount_of_padding):
            if plaintext[i] != amount_of_padding:
                raise EncryptionDecryptionFailure(
                    f"Decryption failed: "
                    f"Expected padding byte value {amount_of_padding} but got {plaintext[i]}"
                )
        plaintext = plaintext[0:first_padding_index]
        return plaintext
