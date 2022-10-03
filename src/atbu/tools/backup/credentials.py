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

from abc import ABC, abstractmethod
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
    InvalidBase64StringError,
    PasswordAuthenticationFailure,
    CredentialInvalid,
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

def zero_bytearray(ba: bytearray):
    for v in [0xCC, 0x55, 0x00]:
        for i, _ in enumerate(ba):
            ba[i] = v

class CredentialByteArray(bytearray):
    """A bytearray with override to allow zeroing out of bytearray
    on demand or when deleted.
    """

    def __del__(self):
        self.zero_array()
        if hasattr(super(), "__del__"):
            super().__del__()

    def zero_array(self):
        zero_bytearray(self)

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

    def split(self, sep, maxsplit) -> list:
        result = []
        for ba in super().split(sep=sep, maxsplit=maxsplit):
            result.append(CredentialByteArray(ba))
            zero_bytearray(ba)
        return result

    def to_serialization_dict(self) -> dict:
        return self.hex()

    def from_serialization_dict(self, hex_str):
        self.fromhex(hex_str)

    @staticmethod
    def create_from_string(the_string: str):
        return CredentialByteArray(the_string.encode("utf-8"))

class Credential:
    """A Credential instance is one credential, which can be an encryption key or
    any other kind of secret that can be represented as bytes.

    The secret, represented by Credential.the_key, can itself be password-protected
    using key derived by PBKDF2.
    """

    attr_name_list = [
        "password",
        "salt",
        "pbkdf2_result",
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
        **kwargs,
    ) -> None:

        super().__init__(**kwargs)

        self.password = None # The password used by PBKDF2 to derive the KEK and password auth hash.
        self.salt = None # The salt used by PBKDF2.
        self.password_auth_hash = None # The password auth hash resulting from PBKDF2.
        self.key_encryption_key = None # The KEK resulting from PBKDF2.
        self.iv = None # The IV associated with encrypting/decrypting the key.
        self.encrypted_key = None # The encrypted (protected) key.
        self.the_key = None # The unencrypted (unprotected) key (aka "secret").
        self.pbkdf2_result = None # The raw PBKDF2 result.
        self.work_factor = None # The work factor used by PBKDF2.

        self.clear()
        self.set(
            password=password,
            salt=salt,
            password_auth_hash=password_auth_hash,
            key_encryption_key=key_encryption_key,
            iv=iv,
            encrypted_key=encrypted_key,
            the_key=the_key,
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
    def is_password_protected(self):
        """True if the credential is protected by a password, False if not
        protected by a password. This property indications protection regardless
        of whether or not the key is currently unprotected (i.e., user already
        entered password, key already decrypted). This property therefore reflects
        generally whether or not the crednetial is password protected.
        """
        return self.password is not None or self.encrypted_key is not None

    @property
    def is_private_key_ready(self):
        return self.the_key is not None

    def __del__(self):
        self.clear()
        if hasattr(super(), "__del__"):
            super().__del__()

    def clear(self) -> None:
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
        self.pbkdf2_result = None
        self.work_factor = PBKDF2_WORK_FACTOR
        self.clear_password_protection()

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
    ):
        if isinstance(password, str):
            password = CredentialByteArray(password.encode())
        if password is not None:
            if not isinstance(password, CredentialByteArray):
                raise ValueError("The password is not a CredentialByteArray.")
            if self.iv is None or self.salt is None:
                self.prepare_for_new_password()
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

    def prepare_for_new_password(self):
        self.clear_password_protection()
        self.salt = CredentialByteArray(os.urandom(DEFAULT_AES_KEY_BIT_LENGTH // 8))
        self.iv = CredentialByteArray(os.urandom(AES_CBC_Base.BLOCK_SIZE))

    def clear_password_protection(self):
        if self.salt:
            self.salt.zero_array()
        if self.iv:
            self.iv.zero_array()
        if self.password:
            self.password.zero_array()
        if self.password_auth_hash:
            self.password_auth_hash.zero_array()
        if self.key_encryption_key:
            self.key_encryption_key.zero_array()
        if self.encrypted_key:
            self.encrypted_key.zero_array()
        self.salt = None
        self.iv = None
        self.password = None
        self.password_auth_hash = None
        self.key_encryption_key = None
        self.encrypted_key = None

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
        self.pbkdf2_result = CredentialByteArray(
            pbkdf2_hmac(
                hash_name="sha512",
                password=self.password,
                salt=self.salt,
                iterations=self.work_factor,
                dklen=int(512 / 8),
            )
        )

        kek_byte_size = DEFAULT_AES_KEY_BIT_LENGTH // 8
        self.key_encryption_key = self.pbkdf2_result.get_portion(0, kek_byte_size)
        password_auth_hash = self.pbkdf2_result.get_portion(
            kek_byte_size, kek_byte_size * 2
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
        # In the following, we ultimately get everything into a textual/hex format
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

    def get_enc_key_material_as_bytes(self) -> CredentialByteArray:
        return self.get_as_bytes(
            include_work_factor=True,
            include_salt=True,
            include_password_auth_hash=True,
            include_IV=True,
            include_encrypted_key=True,
        )

    def get_unenc_key_material_as_bytes(self) -> CredentialByteArray:
        return self.get_as_bytes(include_key=True)

    def get_material_as_bytes(self) -> CredentialByteArray:
        items_found = []
        expected_items = 4
        if self.salt is not None:
            items_found.append("salt")
        if self.iv is not None:
            items_found.append("iv")
        if self.password_auth_hash is not None:
            items_found.append("password_auth_hash")
        if self.encrypted_key is not None:
            items_found.append("encrypted_key")
        if len(items_found) != 0 and len(items_found) != expected_items:
            raise CredentialInvalid(
                f"The credential has partial password-protection settings: "
                f"count={len(items_found)} expected={expected_items} items_found={items_found}"
            )
        if len(items_found) == 0:
            return self.get_unenc_key_material_as_bytes()
        return self.get_enc_key_material_as_bytes()

    @classmethod
    def create_credential_from_bytes(cls, cred_bytes: CredentialByteArray):
        c = cls()
        c.set_from_bytes(cred_bytes=cred_bytes)
        return c


class CredentialAesKey(Credential):

    def __init__(
        self,
        password: Union[str, CredentialByteArray] = None,
        salt: CredentialByteArray = None,
        password_auth_hash: CredentialByteArray = None,
        key_encryption_key: CredentialByteArray = None,
        iv: CredentialByteArray = None,
        encrypted_key: CredentialByteArray = None,
        the_key: CredentialByteArray = None,
        key_bit_size=DEFAULT_AES_KEY_BIT_LENGTH,
        **kwargs,
    ) -> None:
        super().__init__(
            password=password,
            salt=salt,
            password_auth_hash=password_auth_hash,
            key_encryption_key=key_encryption_key,
            iv=iv,
            encrypted_key=encrypted_key,
            the_key=the_key,
            **kwargs,
        )
        self.key_bit_size = None
        self.key_byte_size = None

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
        super().set(
            password=password,
            salt=salt,
            password_auth_hash=password_auth_hash,
            key_encryption_key=key_encryption_key,
            iv=iv,
            encrypted_key=encrypted_key,
            the_key=the_key,
        )
        if key_bit_size is not None:
            self._set_key_bit_size(key_bit_size=key_bit_size)

    def clear(self, key_bit_size=DEFAULT_AES_KEY_BIT_LENGTH) -> None:
        super().clear()
        self._set_key_bit_size(key_bit_size=key_bit_size)

    def _set_key_bit_size(self, key_bit_size):
        if key_bit_size is None or key_bit_size not in ALLOWED_AES_KEY_BIT_LENGTHS:
            raise ValueError(
                f"The specified key length of '{key_bit_size} is not one of the "
                f"available choices of {ALLOWED_AES_KEY_BIT_LENGTHS}."
            )
        self.key_bit_size = key_bit_size
        self.key_byte_size = int(key_bit_size / 8)

    def create_key(
        self,
        the_key: CredentialByteArray = None,
        key_bit_size=DEFAULT_AES_KEY_BIT_LENGTH,
    ) -> None:
        self.clear(key_bit_size=key_bit_size)
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


class DescribedCredential:
    def __init__(
        self,
        credential: Credential = None,
        config_name: str = "unknown",
        credential_name: str = "unknown",
        credential_kind: str = "unknown",
    ) -> None:
        self.credential = credential
        self.config_name = config_name
        self.credential_name = credential_name
        self.credential_kind = credential_kind

    def get_credential_base64(self) -> CredentialByteArray:
        return CredentialByteArray(
            base64.b64encode(
                self.credential.get_material_as_bytes()
            )
        )

    @staticmethod
    def create_from_base64(
        config_name: str,
        credential_name: str,
        password_type_code: str,
        cba_password_base64: CredentialByteArray,
    ):
        if len(password_type_code) == 0:
            raise CredentialInvalid(
                f"The stored credential is not in the expected format. "
                f"The password type code is not present. "
                f"config_name={config_name} credential_name={credential_name}"
            )

        if len(cba_password_base64) == 0:
            raise CredentialInvalid(
                f"The stored credential is not in the expected format. "
                f"The password is not present. "
                f"config_name={config_name} credential_name={credential_name}"
            )

        if not is_valid_base64_string(cba_password_base64):
            raise InvalidBase64StringError(
                f"Expected stored credential to be in base64 format."
            )

        if password_type_code[0] not in PASSWORD_KIND_CHAR_TO_KIND:
            raise CredentialInvalid(
                f"The stored credential is not in the expected format. "
                f"The password type code '{password_type_code}' is unknown. "
                f"config_name={config_name} credential_name={credential_name}"
            )

        password_type = PASSWORD_KIND_CHAR_TO_KIND[password_type_code[0]]

        cba_password = CredentialByteArray(base64.b64decode(cba_password_base64))

        if credential_name == CONFIG_KEYRING_USERNAME_BACKUP_ENCRYPTION:
            if password_type != CONFIG_PASSWORD_KIND_ACTUAL:
                raise CredentialInvalid(
                    f"The stored credential is type '{password_type}' when "
                    f"'{CONFIG_PASSWORD_KIND_ACTUAL}' was expected."
                )
            credential = CredentialAesKey()
            credential.set_from_bytes(cred_bytes=cba_password)
        elif credential_name == CONFIG_KEYRING_USERNAME_STORAGE_PASSWORD:
            credential = Credential()
            credential.set_from_bytes(cred_bytes=cba_password)

        return DescribedCredential(
            credential=credential,
            config_name=config_name,
            credential_name=credential_name,
            credential_kind=password_type,
        )


def raw_cred_bytes_to_type_base64_cred_bytes(
    cred_ascii_bytes: CredentialByteArray,
) -> tuple[str, CredentialByteArray]:
    """Get the password_type_code and raw credential from complete raw persisted
    credential bytes. This can be further refined, is carried over to limit
    refactor churn.
    """
    if not isinstance(cred_ascii_bytes, CredentialByteArray):
        raise CredentialNotFoundError(
            f"The credential was not found: "
        )
    password_parts = cred_ascii_bytes.split(b":", maxsplit=1)
    if len(password_parts) != 2:
        raise CredentialInvalid(
            f"The stored credential is not in the expected two-part format."
        )
    password_type_code = str(password_parts[0], "utf-8")
    cba_password_base64 = password_parts[1]
    if password_type_code not in PASSWORD_KIND_CHAR_TO_KIND:
        raise CredentialInvalid(
            f"The credential is not in the expected format. "
            f"The password type code '{password_type_code}' is unknown. "
        )
    password_type = PASSWORD_KIND_CHAR_TO_KIND[password_type_code]
    return password_type, cba_password_base64


class CredentialStoreProvider(ABC):

    @abstractmethod
    def set_cred_bytes(
        self,
        config_name: str,
        credential_name: str,
        cred_ascii_bytes: CredentialByteArray
    ):
        pass

    @abstractmethod
    def get_cred_bytes(self, config_name: str, credential_name: str) -> CredentialByteArray:
        pass

    @abstractmethod
    def delete_cred_bytes(self, config_name: str, credential_name: str):
        pass


class CredentialStoreKeyringProvider(CredentialStoreProvider):

    def set_cred_bytes(
        self,
        config_name: str,
        credential_name: str,
        cred_ascii_bytes: CredentialByteArray
    ):
        keyring.set_password(
            service_name=config_name,
            username=credential_name,
            password=str(cred_ascii_bytes, "utf-8"),
        )

    def get_cred_bytes(
        self,
        config_name: str,
        credential_name: str
    ) -> CredentialByteArray:
        return CredentialByteArray(
            keyring.get_password(
                service_name=config_name,
                username=credential_name,
            ).encode("utf-8")
        )

    def delete_cred_bytes(self, config_name: str, credential_name: str) -> None:
        keyring.delete_password(
            service_name=config_name,
            username=credential_name,
        )
        pass


_credential_provider_cls = CredentialStoreKeyringProvider


class CredentialStore:

    def __init__(self, provider: CredentialStoreProvider = None) -> None:
        super().__init__()
        if provider is None:
            provider = _credential_provider_cls()
        self.provider = provider

    def set_credential(
        self,
        desc_cred: DescribedCredential
    ) -> CredentialByteArray:
        if not desc_cred.config_name:
            raise CredentialInvalid(
                f"Cannot store credential. The config_name must be a non-empty string."
            )

        if not desc_cred.credential_name:
            raise CredentialInvalid(
                f"Cannot store credential. The credential_name must be a non-empty string."
            )

        if not desc_cred.credential_kind:
            raise CredentialInvalid(
                f"Cannot store credential. The credential_type must be a non-empty string."
            )

        if desc_cred.credential_kind not in PASSWORD_KINDS:
            raise CredentialInvalid(
                f"Cannot store credential. "
                f"The supplied password type '{desc_cred.credential_kind}' is invalid."
            )

        cba_password_base64 = desc_cred.get_credential_base64()
        cred_ascii_bytes = CredentialByteArray(
            f"{desc_cred.credential_kind[0]}:{str(cba_password_base64, 'utf-8')}".encode("utf-8")
        )

        # For any desired caller rollback, get the existing credential.
        # This assumes no format and does not propagate failre to get any
        # older credential beyond returning None.
        cba_old: CredentialByteArray = None
        try:
            cba_old = self.provider.get_cred_bytes(
                config_name=desc_cred.config_name,
                credential_name=desc_cred.credential_name,
            )
        except Exception:
            cba_old = None

        self.provider.set_cred_bytes(
            config_name=desc_cred.config_name,
            credential_name=desc_cred.credential_name,
            cred_ascii_bytes=cred_ascii_bytes,
        )

        return cba_old

    def get_credential(self, config_name: str, credential_name: str) -> DescribedCredential:

        cred_ascii_bytes = self.provider.get_cred_bytes(
            config_name=config_name,
            credential_name=credential_name,
        )

        (
            password_type,
            cba_password_base64,
        ) = raw_cred_bytes_to_type_base64_cred_bytes(
            cred_ascii_bytes=cred_ascii_bytes,
        )

        desc_cred = DescribedCredential.create_from_base64(
            config_name=config_name,
            credential_name=credential_name,
            password_type_code=password_type,
            cba_password_base64=cba_password_base64,
        )

        return desc_cred

    def delete_credential(self, config_name: str, credential_name: str) -> None:
        self.provider.delete_cred_bytes(
            config_name=config_name,
            credential_name=credential_name,
        )


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

    if password_type_code not in PASSWORD_KIND_CHAR_TO_KIND:
        raise CredentialInvalid(
            f"The stored credential is not in the expected format. "
            f"The password type code '{password_type_code}' is unknown. "
            f"service_name={service_name} username={username}"
        )

    password_type = PASSWORD_KIND_CHAR_TO_KIND[password_type_code]

    return (password_type_code, password_type, cba_password_base64)


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
        password_attempt1 = CredentialByteArray(pw_input_func(prompt).encode("utf-8"))
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


def check_yubikey_presence_with_message(display_presence_message: bool = False):
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
        print(f"The password you entered is {len(password)} byte when UTF-8 encoded.")
        print(
            f"The UTF-8 encoded password cannot be larger than {get_max_challenge_size()} bytes."
        )
        print(f"Please try a shorter password.")
        check_yubikey_presence_with_message()
        return False
    return check_yubikey_presence_with_message()


def prompt_for_password_with_yubikey_opt(
    prompt,
    prompt_again=None,
    hidden: bool = True,
) -> CredentialByteArray:
    is_password_valid_func = None

    while True:
        if is_yubikey_required():
            is_password_valid_func = is_password_valid_yubikey
            check_yubikey_presence_with_message(display_presence_message=True)

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
            password = CredentialByteArray(challenge_response(challenge=password))
            break
        except YubiKeyNotPressedTimeout as ex:
            print(f"You did not press your key in time. Please try again.")
        except OSError as ex:
            if is_a_yubikey_present():
                raise
            print(f"The YubiKey is no longer present.")

    return password


def prompt_for_password_unlock_credential(credential: Union[Credential, CredentialAesKey]):
    """Unlock a CredentialAesKey instance which is to make its private key/secret
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
