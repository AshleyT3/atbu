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
r"""YubiKey helpers.
A layer of helpers between ATBU and yubikey-manager.
"""

from typing import Any, Tuple
from atbu.common.exception import exc_to_string, InvalidFunctionArgument

from .exception import (
    YubiKeyBackendNotAvailableError,
    YubiKeyNotPressedTimeout,
)

_IS_YUBIKEY_REQUIRED = False
_IS_YUBIKEY_INFRA_INIT = False


def set_require_yubikey(is_required: bool):
    global _IS_YUBIKEY_REQUIRED
    _IS_YUBIKEY_REQUIRED = is_required


def is_yubikey_required():
    return _IS_YUBIKEY_REQUIRED


def setup_yubikey_infra():
    # pylint: disable=import-outside-toplevel,unused-import
    global _IS_YUBIKEY_INFRA_INIT
    if _IS_YUBIKEY_INFRA_INIT:
        return
    try:
        global ykman
        global yubikit
        import ykman
        import ykman.device
        import yubikit.core
        import yubikit.yubiotp

        _IS_YUBIKEY_INFRA_INIT = True
    except Exception as ex:
        raise YubiKeyBackendNotAvailableError(
            f"Failure access YubiKey backend. "
            f"Ensure you have yubikey-manager installed: "
            f"pip install yubikey-manager. {exc_to_string(ex)}"
        ).with_traceback(ex.__traceback__) from ex


def _get_list_yubikey_devices() -> list[Tuple[Any, Any]]:
    # pylint: disable=undefined-variable
    setup_yubikey_infra()
    l = ykman.device.list_all_devices()
    return l if l else None


def is_a_yubikey_present():
    l = _get_list_yubikey_devices()
    if l is None:
        return False
    return len(l) > 0


def get_first_yubikey_device():
    l = _get_list_yubikey_devices()
    return l[0] if l else (None, None)


def get_max_challenge_size():
    # pylint: disable=undefined-variable
    return yubikit.yubiotp.HMAC_CHALLENGE_SIZE


def challenge_response(
    challenge: bytes,
    slot_num: int = 2,
):
    # pylint: disable=undefined-variable
    setup_yubikey_infra()
    if len(challenge) > get_max_challenge_size():
        raise InvalidFunctionArgument(
            f"The challenge must be {get_max_challenge_size()} bytes or less."
        )
    device, _ = get_first_yubikey_device()
    if device is None:
        raise YubiKeyBackendNotAvailableError("First YubiKey not found.")
    with device.open_connection(yubikit.core.otp.OtpConnection) as c:
        s = yubikit.yubiotp.YubiOtpSession(c)
        try:
            response = s.calculate_hmac_sha1(
                slot=slot_num,  # Will use CONFIG_SLOT.CHAL_HMAC_n
                challenge=challenge,
            )
            return response
        except yubikit.core.TimeoutError as ex:
            raise YubiKeyNotPressedTimeout(
                f"The YubiKey was not pressed in time."
            ).with_traceback(ex.__traceback__) from ex
