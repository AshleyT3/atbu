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

# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=unused-import
# pylint: disable=wrong-import-position

import os
from pathlib import Path
import logging
from pytest import (
    LogCaptureFixture,
    CaptureFixture,
    fail,
    raises,
    Pytester,
    FixtureRequest,
    Config,
    RunResult,
    ExitCode,
)
import pytest
from atbu.tools.backup.constants import DEFAULT_AES_KEY_BIT_LENGTH

from atbu.tools.backup.exception import (
    PasswordAuthenticationFailure,
)
from atbu.tools.backup.credentials import (
    CredentialByteArray,
    Credential,
    CredentialAesKey
)

LOGGER = logging.getLogger(__name__)

ATBU_TEST_BACKUP_NAME = "AtbuTestBackup-5b497bb3-c9ef-48a9-af7b-2327fc17fb65"

# import pdb; pdb.set_trace()
# import pdb; pdb.set_trace()

SIMPLE_SECRET = "secret-1234567890!"
SIMPLE_PASSWORD = "1234567890abcdefghij$"

def setup_module(module):  # pylint: disable=unused-argument
    pass

def teardown_module(module):  # pylint: disable=unused-argument
    pass

def test_credential():
    cred1 = Credential(
        the_key=CredentialByteArray.create_from_string(SIMPLE_SECRET),
        password=CredentialByteArray.create_from_string(SIMPLE_PASSWORD),
    )
    cred1.encrypt_key()
    enc_key_bytes = cred1.get_enc_key_material_as_bytes()

    cred2 = Credential.create_credential_from_bytes(enc_key_bytes)
    assert isinstance(cred2, Credential)
    assert cred1.the_key != cred2.the_key
    cred2.set(password=SIMPLE_PASSWORD)
    cred2.decrypt_key()
    assert cred1.the_key == cred2.the_key

    cred2b = Credential.create_credential_from_bytes(cred2.get_unenc_key_material_as_bytes())
    assert isinstance(cred2b, Credential)
    assert cred2.the_key == cred2b.the_key

    cred3 = Credential.create_credential_from_bytes(enc_key_bytes)
    assert isinstance(cred3, Credential)
    assert cred1.the_key != cred3.the_key
    cred3.set(password=SIMPLE_PASSWORD + "-incorrect")
    with pytest.raises(PasswordAuthenticationFailure):
        cred3.decrypt_key()
    assert cred1.the_key != cred3.the_key

    cred4 = Credential(
        password=CredentialByteArray.create_from_string(SIMPLE_PASSWORD),
        iv=cred1.iv,
        password_auth_hash=cred1.password_auth_hash,
        salt=cred1.salt,
        encrypted_key=cred1.encrypted_key,
    )
    assert cred1.the_key != cred4.the_key
    cred4.decrypt_key()
    assert cred1.the_key == cred4.the_key


def test_credential_AES():
    the_key = CredentialByteArray(os.urandom(DEFAULT_AES_KEY_BIT_LENGTH // 8))
    cred1 = CredentialAesKey(
        the_key=the_key,
        password=CredentialByteArray.create_from_string(SIMPLE_PASSWORD),
    )
    cred1.encrypt_key()
    enc_key_bytes = cred1.get_enc_key_material_as_bytes()

    cred2 = CredentialAesKey.create_credential_from_bytes(enc_key_bytes)
    assert isinstance(cred2, CredentialAesKey)
    assert cred1.the_key != cred2.the_key
    cred2.set(password=SIMPLE_PASSWORD)
    cred2.decrypt_key()
    assert cred1.the_key == cred2.the_key

    cred2b = CredentialAesKey.create_credential_from_bytes(cred2.get_unenc_key_material_as_bytes())
    assert isinstance(cred2b, CredentialAesKey)
    assert cred2.the_key == cred2b.the_key

    cred3 = CredentialAesKey.create_credential_from_bytes(enc_key_bytes)
    assert isinstance(cred3, CredentialAesKey)
    assert cred1.the_key != cred3.the_key
    cred3.set(password=SIMPLE_PASSWORD + "-incorrect")
    with pytest.raises(PasswordAuthenticationFailure):
        cred3.decrypt_key()
    assert cred1.the_key != cred3.the_key

    cred4 = Credential(
        password=CredentialByteArray.create_from_string(SIMPLE_PASSWORD),
        iv=cred1.iv,
        password_auth_hash=cred1.password_auth_hash,
        salt=cred1.salt,
        encrypted_key=cred1.encrypted_key,
    )
    assert cred1.the_key != cred4.the_key
    cred4.decrypt_key()
    assert cred1.the_key == cred4.the_key

def test_credential_AES_create_key():
    cred1 = CredentialAesKey()
    cred1.create_key()
    cred1.set(password=SIMPLE_PASSWORD)
    cred1.encrypt_key()
    enc_key_bytes = cred1.get_enc_key_material_as_bytes()

    cred2 = CredentialAesKey.create_credential_from_bytes(enc_key_bytes)
    assert isinstance(cred2, CredentialAesKey)
    assert cred1.the_key != cred2.the_key
    cred2.set(password=SIMPLE_PASSWORD)
    cred2.decrypt_key()
    assert cred1.the_key == cred2.the_key

    cred3 = CredentialAesKey()
    cred3b = CredentialAesKey()
    cred3.create_key()
    cred3b.create_key()
    assert cred1.the_key != cred3.the_key
    assert cred3.the_key != cred3b.the_key
