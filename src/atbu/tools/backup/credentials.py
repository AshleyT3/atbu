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
r"""Credential-related classes.

    CredentialByteArray: Uses byte_array so cred can be zero'ed out afterwards as
    a form of cleanup. Any such efforts at cleanup are *not* security for several
    good reasons, one of which is that CredentialByteArray is not the only party
    handling secrets, where some others such as the cryptography/keyring packages
    use bytes immutable so do not allow, from Python perspective, the zero'ing
    out the memory area they populate with keys/passwords.

    A best effort toward minimizing the time frame when secrets are exposed would be
    to have all parties handling secrets to use a "SecureByteArray" of sorts, which
    would allow memory locking, enforce clearing at cleanup, etc. Stil, None of
    that would remove the need to keep the machine/process secure, but would merely
    minimize the issue caused by immutables which themselves may well leave secrets
    lying around for much longer time periods, if not spreading copies around beyond
    some original.

    Therefore, to achieve security when using a Python process that handles secrets
    in the clear at *any* time for *however* long a duration, the machine and process
    space must be kept clear of threats.
"""

import base64
import os
from typing import Callable, Union
from hashlib import pbkdf2_hmac
import keyring
import pwinput

from atbu.common.util_helpers import is_valid_base64_string
from atbu.common.aes_cbc import (
    AES_CBC_Base,
    AesCbcPaddingDecryptor,
    AesCbcPaddingEncryptor,
)

from .constants import *
from .exception import (
    CredentialNotFoundError,
    CredentialTypeNotFoundError,
    InvalidBase64StringError,
    PasswordAuthenticationFailure,
    CredentialInvalid,
    CredentialRequestInvalidError,
    CredentialSecretDerivationError,
)
from .yubikey_helpers import (
    get_max_challenge_size,
    is_yubikey_required,
    is_a_yubikey_present,
    challenge_response,
    YubiKeyNotPressedTimeout,
)

_MAX_PASSWORD = 100

class CredentialByteArray(bytearray):
    """A bytearray with override to allow zeroing out of bytearray
    on demand or when deleted.
    """

    def __del__(self):
        self.zero_array()
        if hasattr(super(), "__del__"):
            super().__del__()

    def zero_array(self):
        for v in [0xCC, 0x55, 0x00]:
            for i, _ in enumerate(self):
                self[i] = v

    def get_portion(self, start_pos=None, end_pos=None):
        if not start_pos:
            start_pos = 0
        if not end_pos:
            end_pos = len(self)
        portion_len = end_pos - start_pos
        r = CredentialByteArray(portion_len)
        idx_r = 0
        for i in range(start_pos, end_pos):
            r[idx_r] = self[i]
            idx_r += 1
        return r

    def to_serialization_dict(self) -> dict:
        return self.hex()

    def from_serialization_dict(self, hex_str):
        self.fromhex(hex_str)


class Credential:

    attr_name_list = [
        "password",
        "salt",
        "pbkdf2",
        "password_auth_hash",
        "key_encryption_key",
        "iv",
        "encrypted_key",
        "the_key",
    ]

    def __init__(
        self,
        password: Union[str, CredentialByteArray] = None,
        salt: CredentialByteArray = None,
        password_auth_hash: CredentialByteArray = None,
        key_encryption_key: CredentialByteArray = None,
        iv: CredentialByteArray = None,
        encrypted_key: CredentialByteArray = None,
        the_key: CredentialByteArray = None,
        key_bit_size=DEFAULT_KEY_BIT_LENGTH,
    ) -> None:

        self.password = None
        self.salt = None
        self.password_auth_hash = None
        self.key_encryption_key = None
        self.iv = None
        self.encrypted_key = None
        self.the_key = None
        self.key_bit_size = None
        self.key_byte_size = None
        self.pbkdf2 = None
        self.work_factor = None

        self.clear(key_bit_size=key_bit_size)
        self.set(
            password=password,
            salt=salt,
            password_auth_hash=password_auth_hash,
            key_encryption_key=key_encryption_key,
            iv=iv,
            encrypted_key=encrypted_key,
            the_key=the_key,
            key_bit_size=key_bit_size,
        )

    @property
    def is_private_key_possible(self):
        """True if a private key is achievable either as is or with a password,
        False if not possible no matter what. See is_password_required.
        Generally, use is_private_key_possible to see if a private is available
        at all by any means. Then, if this is True, use is_password_required to
        determine is the user should be prompted for a password.
        """
        if self.the_key is not None:
            return True
        if self.encrypted_key is None:
            return False
        if self.salt is None or self.iv is None:
            return False
        return True

    @property
    def is_password_required(self):
        """True if password is required, False if not required.
        See is_private_key_possible.
        """
        if self.the_key is not None:
            return False
        if self.key_encryption_key is not None:
            return False
        if self.password is not None:
            return False
        return True

    @property
    def is_private_key_ready(self):
        return self.the_key is not None

    def _set_key_bit_size(self, key_bit_size):
        if key_bit_size is None or key_bit_size not in ALLOWED_KEY_BIT_LENGTHS:
            raise ValueError(
                f"The specified key length of '{key_bit_size} is not one of the "
                f"available choices of {ALLOWED_KEY_BIT_LENGTHS}."
            )
        self.key_bit_size = key_bit_size
        self.key_byte_size = int(key_bit_size / 8)

    def __del__(self):
        self.clear()
        if hasattr(super(), "__del__"):
            super().__del__()

    def clear(self, key_bit_size=DEFAULT_KEY_BIT_LENGTH) -> None:
        for member in Credential.attr_name_list:
            if hasattr(self, member) and isinstance(member, CredentialByteArray):
                cba: CredentialByteArray = getattr(self, member)
                cba.zero_array()
        self.password = None
        self.salt = None
        self.password_auth_hash = None
        self.key_encryption_key = None
        self.iv = None
        self.encrypted_key = None
        self.the_key = None
        self.pbkdf2 = None
        self.work_factor = PBKDF2_WORK_FACTOR
        self._set_key_bit_size(key_bit_size=key_bit_size)

    def clear_password(self):
        if self.password:
            self.password.zero_array()
        self.password = None

    def set(
        self,
        password: Union[str, CredentialByteArray] = None,
        salt: CredentialByteArray = None,
        password_auth_hash: CredentialByteArray = None,
        key_encryption_key: CredentialByteArray = None,
        iv: CredentialByteArray = None,
        encrypted_key: CredentialByteArray = None,
        the_key: CredentialByteArray = None,
        key_bit_size=None,
    ):
        if key_bit_size is not None:
            self._set_key_bit_size(key_bit_size=key_bit_size)

        if isinstance(password, str):
            password = CredentialByteArray(password.encode())
        if password is not None:
            if not isinstance(password, CredentialByteArray):
                raise ValueError("The password is not a CredentialByteArray.")
            self.password = password

        if salt is not None:
            if not isinstance(salt, CredentialByteArray):
                raise ValueError("The salt is not a CredentialByteArray.")
            self.salt = salt

        if password_auth_hash is not None:
            if not isinstance(password_auth_hash, CredentialByteArray):
                raise ValueError("The password_auth_hash is not a CredentialByteArray.")
            self.password_auth_hash = password_auth_hash

        if key_encryption_key is not None:
            if not isinstance(key_encryption_key, CredentialByteArray):
                raise ValueError("The key_encryption_key is not a CredentialByteArray.")
            self.key_encryption_key = password_auth_hash

        if iv is not None:
            if not isinstance(iv, CredentialByteArray):
                raise ValueError("The iv is not a CredentialByteArray.")
            self.iv = iv

        if encrypted_key is not None:
            if not isinstance(encrypted_key, CredentialByteArray):
                raise ValueError("The encrypted_key is not a CredentialByteArray.")
            self.encrypted_key = encrypted_key

        if the_key is not None:
            if not isinstance(the_key, CredentialByteArray):
                raise ValueError("The key is not a CredentialByteArray.")
            self.the_key = the_key

    def create_key(
        self,
        password: Union[str, CredentialByteArray] = None,
        salt: CredentialByteArray = None,
        iv: CredentialByteArray = None,
        the_key: CredentialByteArray = None,
        key_bit_size=DEFAULT_KEY_BIT_LENGTH,
    ) -> None:
        self.clear()
        self._set_key_bit_size(key_bit_size=key_bit_size)

        #
        # Create a password if none was provided.
        #
        if not password:
            password = CredentialByteArray(os.urandom(self.key_byte_size))
        if isinstance(password, str):
            password = CredentialByteArray(password.encode())
        if not isinstance(password, CredentialByteArray):
            raise ValueError(
                f"The password is not either str or bytes. type={type(password)}"
            )
        self.password = password

        #
        # Create a salt if none was provided.
        #
        if not salt:
            salt = CredentialByteArray(os.urandom(self.key_byte_size))
        if not isinstance(salt, CredentialByteArray):
            raise ValueError(f"The salt is not bytes. type={type(salt)}")
        self.salt = salt

        #
        # Create an IV if none was provided.
        #
        if not iv:
            iv = CredentialByteArray(os.urandom(AES_CBC_Base.BLOCK_SIZE))
        if (
            not isinstance(iv, CredentialByteArray)
            or len(iv) != AES_CBC_Base.BLOCK_SIZE
        ):
            raise ValueError(
                f"The salt is not {AES_CBC_Base.BLOCK_SIZE} bytes. type={type(iv)}"
            )
        self.iv = iv

        #
        # Create a key if none was provided.
        #
        if not the_key:
            the_key = CredentialByteArray(os.urandom(self.key_byte_size))
        else:
            if (
                not isinstance(the_key, CredentialByteArray)
                or len(the_key) != self.key_byte_size
            ):
                raise ValueError(
                    f"The key must be the specified length of {self.key_bit_size} bits"
                )
        self.the_key = the_key

    def prepare_for_new_password(self):
        if self.salt:
            self.salt.zero_array()
        self.salt = CredentialByteArray(os.urandom(self.key_byte_size))
        if self.iv:
            self.iv.zero_array()
        self.iv = CredentialByteArray(os.urandom(AES_CBC_Base.BLOCK_SIZE))

    def encrypt_key(self):
        self.password_auth_hash = self._derive_key_encryption_key()
        enc = AesCbcPaddingEncryptor(self.key_encryption_key, self.iv)
        encrypted_key_bytes = enc.update(input_bytes=self.the_key) + enc.finalize()
        self.encrypted_key = CredentialByteArray(encrypted_key_bytes)

    def decrypt_key(self):
        if self.encrypted_key is None:
            raise ValueError("No encrypted key to decrypt.")
        derived_password_auth_hash = self._derive_key_encryption_key()
        if self.password_auth_hash != derived_password_auth_hash:
            raise PasswordAuthenticationFailure(
                "The password and/or stored secrets do not match."
            )
        dec = AesCbcPaddingDecryptor(key=self.key_encryption_key, IV=self.iv)
        decrypted_key_bytes = (
            dec.update(input_bytes=self.encrypted_key) + dec.finalize()
        )
        self.the_key = CredentialByteArray(decrypted_key_bytes)

    def _derive_key_encryption_key(self):
        if self.password is None:
            raise ValueError("A password is required to derive the key encryption key.")
        if self.salt is None:
            raise ValueError("A salt is required to derive the key encryption key.")
        if self.work_factor is None:
            raise ValueError("A work factor is needed for PBDKF2.")
        self.pbkdf2 = CredentialByteArray(
            pbkdf2_hmac(
                hash_name="sha512",
                password=self.password,
                salt=self.salt,
                iterations=self.work_factor,
                dklen=int(512 / 8),
            )
        )
        self.key_encryption_key = self.pbkdf2.get_portion(0, self.key_byte_size)
        password_auth_hash = self.pbkdf2.get_portion(
            self.key_byte_size, self.key_byte_size * 2
        )
        return password_auth_hash

    def get_as_bytes(
        self,
        include_work_factor: bool = False,
        include_salt: bool = False,
        include_password_auth_hash: bool = False,
        include_IV: bool = False,
        include_key_encryption_key: bool = False,
        include_key: bool = False,
        include_encrypted_key: bool = False,
    ) -> CredentialByteArray:

        #
        # In the following, we ultiamtely get everything into a textual/hex format
        # where fields are separated by the equal sign (=) and commas (,). After
        # TODO: Loop back around to encode with struct pack/unpack.
        #

        r = CredentialByteArray()

        if include_work_factor:
            if len(r) > 0:
                r += b","
            r += b"W="
            r += (
                int(PBKDF2_WORK_FACTOR)
                .to_bytes(length=4, byteorder="little")
                .hex()
                .encode()
            )

        if include_salt:
            if len(r) > 0:
                r += b","
            r += b"S="
            r += self.salt.hex().encode()

        if include_password_auth_hash:
            if len(r) > 0:
                r += b","
            r += b"H="
            r += self.password_auth_hash.hex().encode()

        if include_key_encryption_key:
            if len(r) > 0:
                r += b","
            r += b"E="
            r += self.key_encryption_key.hex().encode()

        if include_IV:
            if len(r) > 0:
                r += b","
            r += b"I="
            r += self.iv.hex().encode()

        if include_encrypted_key:
            if len(r) > 0:
                r += b","
            r += b"C="
            r += self.encrypted_key.hex().encode()

        if include_key:
            if len(r) > 0:
                r += b","
            r += b"K="
            r += self.the_key.hex().encode()

        if len(r) == 0:
            raise ValueError(f"Requesting no secrets.")
        return r

    def set_from_bytes(self, cred_bytes: CredentialByteArray):
        cred_dict = dict(
            kv_pair.split("=") for kv_pair in cred_bytes.decode().split(",")
        )
        for k, v in cred_dict.items():
            c: CredentialByteArray = CredentialByteArray(bytearray.fromhex(v))
            if k == "W":
                self.work_factor = int.from_bytes(bytes=c, byteorder="little")
                if self.work_factor != PBKDF2_WORK_FACTOR:
                    # Until handling for this is in place.
                    raise CredentialInvalid(
                        f"The PBDKF2 work factor "
                        f"{self.work_factor} is invalid. "
                        f"Only {PBKDF2_WORK_FACTOR} is supported."
                    )
            elif k == "S":
                self.salt = c
            elif k == "H":
                self.password_auth_hash = c
            elif k == "E":
                self.key_encryption_key = c
            elif k == "I":
                self.iv = c
            elif k == "C":
                self.encrypted_key = c
            elif k == "K":
                self.the_key = c
            else:
                raise ValueError(f"Cannot interpret value code '{k}'.")

    @staticmethod
    def create_credential_from_bytes(cred_bytes: CredentialByteArray):
        c = Credential()
        c.set_from_bytes(cred_bytes=cred_bytes)
        return c

def default_is_password_valid(password: CredentialByteArray):
    if len(password) > _MAX_PASSWORD:
        print(f"Your password is too long.")
        print(f"The maximum length password is {_MAX_PASSWORD} UTF-8 encoded bytes.")
        return False
    return True

def prompt_for_password(
    prompt,
    prompt_again=None,
    hidden: bool = True,
    is_password_valid_func: Callable[[CredentialByteArray], bool] = None,
) -> CredentialByteArray:
    if is_password_valid_func is None:
        is_password_valid_func = default_is_password_valid
    pw_input_func = pwinput.pwinput if hidden else input
    while True:
        password_attempt1 = CredentialByteArray(
            pw_input_func(prompt).encode("utf-8")
        )
        if len(password_attempt1) == 0:
            print("Blank passwords are not allowed, try again.")
            continue
        if not is_password_valid_func(password_attempt1):
            continue
        if not prompt_again:
            return password_attempt1
        password_attempt2 = CredentialByteArray(pw_input_func(prompt_again).encode())
        if password_attempt1 == password_attempt2:
            del password_attempt2
            return password_attempt1
        print("The passwords did not match, try again.")

def check_yubikey_presence_with_message(display_presence_message: bool=False):
    if not is_a_yubikey_present():
        print(
            f"IMPORTANT: No YubiKey was detected. "
            f"Please insert your YubiKey before entering your password."
        )
        return False
    if display_presence_message:
        print(f"A YubiKey was detected.")
    return True

def is_password_valid_yubikey(password: CredentialByteArray):
    if len(password) > get_max_challenge_size():
        print(
            f"The password you entered is {len(password)} byte when UTF-8 encoded."
        )
        print(
            f"The UTF-8 encoded password cannot be larger than {get_max_challenge_size()} bytes."
        )
        print(
            f"Please try a shorter password."
        )
        check_yubikey_presence_with_message()
        return False
    return check_yubikey_presence_with_message()

def prompt_for_password_with_yubikey_opt(
    prompt,
    prompt_again = None,
    hidden: bool = True,
):
    is_password_valid_func = None

    while True:
        if is_yubikey_required():
            is_password_valid_func = is_password_valid_yubikey
            check_yubikey_presence_with_message(
                display_presence_message=True
            )

        password = prompt_for_password(
            prompt=prompt,
            prompt_again=prompt_again,
            hidden=hidden,
            is_password_valid_func=is_password_valid_func,
        )

        if not is_yubikey_required():
            break

        try:
            print(f"Press your key now to allow challenge/response...")
            password = CredentialByteArray(
                challenge_response(
                    challenge=password
                )
            )
            break
        except YubiKeyNotPressedTimeout as ex:
            print(f"You did not press your key in time. Please try again.")
        except OSError as ex:
            if is_a_yubikey_present():
                raise
            print(f"The YubiKey is no longer present.")

    return password

def get_base64_password_from_keyring(
    service_name: str,
    username: str,
) -> tuple[str, str, CredentialByteArray]:
    raw_password = keyring.get_password(service_name=service_name, username=username)
    if raw_password is None:
        raise CredentialNotFoundError(
            f"The credential was not found in the keyring: "
            f"service_name={service_name} username={username}"
        )
    password_parts = raw_password.split(":", maxsplit=1)
    if len(password_parts) != 2:
        raise CredentialInvalid(
            f"The stored credential is not in the expected two-part format."
        )
    password_type_code = password_parts[0]
    cba_password_base64 = CredentialByteArray(password_parts[1].encode("utf-8"))

    if len(password_type_code) == 0:
        raise CredentialInvalid(
            f"The stored credential is not in the expected format. "
            f"The password type code is not present. "
            f"service_name={service_name} username={username}"
        )

    if len(cba_password_base64) == 0:
        raise CredentialInvalid(
            f"The stored credential is not in the expected format. "
            f"The password is not present. "
            f"service_name={service_name} username={username}"
        )

    if not is_valid_base64_string(cba_password_base64):
        raise InvalidBase64StringError(
            f"Expected stored credential to be in base64 format."
        )

    if password_type_code not in PASSWORD_TYPE_CHAR_TO_TYPE:
        raise CredentialInvalid(
            f"The stored credential is not in the expected format. "
            f"The password type code '{password_type_code}' is unknown. "
            f"service_name={service_name} username={username}"
        )

    password_type = PASSWORD_TYPE_CHAR_TO_TYPE[password_type_code]

    return (password_type_code, password_type, cba_password_base64)


def unlock_credential(credential: Credential):
    """Unlock a Credential instance which is to make its private key/secret
    available in the clear. If the private key is password-protected, ask
    for a password. The result of calling this function is an unlocked
    credential or an exception.

        Exceptions:
            PasswordAuthenticationFailure: Too many attempts with incorrect password.
            CredentialSecretDerivationError: Something unexpected indicates the key
            is not available despite having been decrypted (likely a program bug or
            something esoteric such as system corruption).
    """
    if not credential.is_private_key_possible:
        raise CredentialInvalid(
            f"The private key is not available. "
            f"The credential is invalid or corrupt."
        )
    if not credential.is_private_key_ready:
        if not credential.is_password_required:
            credential.decrypt_key()
        else:
            attempts = 5
            while True:
                password = prompt_for_password_with_yubikey_opt(
                    prompt="Enter the password for this backup:"
                )
                credential.set(password=password)
                try:
                    attempts -= 1
                    credential.decrypt_key()
                    break
                except PasswordAuthenticationFailure:
                    if attempts > 0:
                        print(f"The password appears to be invalid, try again.")
                    else:
                        print(f"Still incorrect.")
                        raise
        if not credential.is_private_key_ready:
            raise CredentialSecretDerivationError(
                "Unexpected failure, canonot access the credential."
            )


def get_password_from_keyring(
    service_name: str,
    username: str,
    keep_secret_base64_encoded: bool,
) -> tuple[str, str, CredentialByteArray]:
    (
        password_type_code,
        password_type,
        cba_password_base64,
    ) = get_base64_password_from_keyring(
        service_name=service_name,
        username=username,
    )

    if keep_secret_base64_encoded:
        return (password_type_code, password_type, cba_password_base64)

    cba_password = CredentialByteArray(base64.b64decode(cba_password_base64))

    #
    # Caller wants direct secret in the clear.
    # Secret has been base64 decoded.
    # Enryption secrets are persisted Credential information.
    # To give caller direct secret, perform the following...
    #

    if (
        username == CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION
        and password_type == CONFIG_PASSWORD_TYPE_ACTUAL
    ):
        credential = Credential.create_credential_from_bytes(cred_bytes=cba_password)
        unlock_credential(credential=credential)
        cba_password = credential.the_key
        del credential

    return (password_type_code, password_type, cba_password)


def get_enc_credential_from_keyring(
    service_name: str, username: str, unlock: bool = False
) -> Credential:

    if username != CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION:
        raise CredentialRequestInvalidError(
            f"A request for a Credential instance is only valid for the backup encryption secret."
        )

    (
        password_type_code,
        password_type,
        cba_password_base64,
    ) = get_base64_password_from_keyring(
        service_name=service_name,
        username=username,
    )

    if password_type != CONFIG_PASSWORD_TYPE_ACTUAL:
        raise CredentialTypeNotFoundError(
            f"Expected credential type={CONFIG_PASSWORD_TYPE_ACTUAL} but got {password_type_code}. "
            f"Cannot derive Credential instance."
        )

    cba_password = CredentialByteArray(base64.b64decode(cba_password_base64))
    credential = Credential.create_credential_from_bytes(cred_bytes=cba_password)
    if not credential.is_private_key_possible:
        raise CredentialInvalid(
            f"The private key is not available. The credential is invalid or corrupt."
        )

    if unlock:
        unlock_credential(credential=credential)

    return credential


def set_password_to_keyring(
    service_name: str,
    username: str,
    password_type: str,
    password_bytes: CredentialByteArray,
    password_is_base64: bool = False,
) -> None:
    if not service_name:
        raise CredentialInvalid(
            f"Cannot store credential. The supplied service name must be a non-empty string."
        )

    if not username:
        raise CredentialInvalid(
            f"Cannot store credential. The supplied user name must be a non-empty string."
        )

    if not password_type:
        raise CredentialInvalid(
            f"Cannot store credential. The supplied password type must be a non-empty string."
        )

    password_type_code = password_type[0]
    if password_type_code not in PASSWORD_TYPE_CHAR_TO_TYPE:
        raise CredentialInvalid(
            f"Cannot store credential. The supplied password type '{password_type}' is invalid."
        )

    if not password_bytes:
        raise CredentialInvalid(
            f"Cannot store credential. The password was not supplied."
        )

    if not password_is_base64:
        password_bytes = CredentialByteArray(base64.b64encode(password_bytes))

    if not is_valid_base64_string(str_to_check=password_bytes):
        raise InvalidBase64StringError(
            f"Expected password_bytes to be a base64-encoded string."
        )

    keyring.set_password(
        service_name=service_name,
        username=username,
        password=f"{password_type_code}:{str(password_bytes, 'utf-8')}",
    )
