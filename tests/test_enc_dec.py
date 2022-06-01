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
from pytest import LogCaptureFixture, CaptureFixture, fail, raises
from atbu.common.aes_cbc import (
    AES_CBC_Base,
    AesCbcPaddingEncryptor,
    AesCbcPaddingDecryptor,
)

LOGGER = logging.getLogger(__name__)


def setup_module(module):
    pass


def teardown_module(module):
    pass


def test_encryption_decryption_simple(tmp_path: Path):
    key = bytes(os.urandom(int(256 / 8)))
    iv = bytes(os.urandom(AES_CBC_Base.BLOCK_SIZE))
    LOGGER.debug(f"key={key.hex(' ')}")
    LOGGER.debug(f"IV={iv.hex(' ')}")

    for i in range(0, AES_CBC_Base.BLOCK_SIZE * 16):
        pt = bytes([0x55] * i)
        enc = AesCbcPaddingEncryptor(key=key, IV=iv)
        assert not enc.is_finalized
        ct = enc.update(pt)
        assert not enc.is_finalized
        ct += enc.finalize()
        assert enc.is_finalized

        dec = AesCbcPaddingDecryptor(key=key, IV=iv)
        assert not dec.is_finalized
        pt2 = dec.update(ct)
        assert not dec.is_finalized
        pt2 += dec.finalize()
        assert dec.is_finalized

        LOGGER.debug(f"Count={i}:")
        LOGGER.debug(f"    ct={ct.hex(' ')}")
        LOGGER.debug(f"    pt={pt.hex(' ')}")
        LOGGER.debug(f"    pt={pt2.hex(' ')}")

        assert pt == pt2


def test_encryption_decryption_edge(tmp_path: Path):
    key = bytes(os.urandom(int(256 / 8)))
    iv = bytes(os.urandom(AES_CBC_Base.BLOCK_SIZE))
    LOGGER.debug(f"key={key.hex(' ')}")
    LOGGER.debug(f"IV={iv.hex(' ')}")

    for i in range(0, AES_CBC_Base.BLOCK_SIZE * 16):
        pt = bytes([0x55] * i)
        enc = AesCbcPaddingEncryptor(key=key, IV=iv)
        assert not enc.is_finalized
        ct = enc.update(pt)
        assert not enc.is_finalized
        ct += enc.finalize()
        assert enc.is_finalized

        NUM_DECRYPTORS = AES_CBC_Base.BLOCK_SIZE * 3
        for d in range(NUM_DECRYPTORS):
            dec = AesCbcPaddingDecryptor(key=key, IV=iv)
            assert not dec.is_finalized
            pt2 = dec.update(ct[:d])
            assert not dec.is_finalized
            pt2 += dec.update(ct[d:])
            assert not dec.is_finalized
            pt2 += dec.finalize()
            assert dec.is_finalized
            LOGGER.debug(f"Count={i} Edge={d}:")
            LOGGER.debug(f"    ct={ct.hex(' ')}")
            LOGGER.debug(f"    pt={pt.hex(' ')}")
            LOGGER.debug(f"    pt={pt2.hex(' ')}")
            assert pt == pt2
