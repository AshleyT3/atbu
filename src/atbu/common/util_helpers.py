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
r"""Utility/helper functions.
"""

# pylint: disable=missing-class-docstring

import base64
from enum import Enum
from io import SEEK_END, SEEK_SET
import io
import os
from pathlib import Path
import platform
import random
from shutil import copy2
from typing import Union
from datetime import datetime, timezone

from .exception import InvalidFunctionArgument


class AutoNameEnum(Enum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name


def is_platform_path_case_sensitive():
    return os.path.normcase("A") == "A"


def get_trash_bin_name():
    if platform.system() == "Windows":
        return "Recycle Bin"
    else:
        return "Trash"


def get_file_max_pos(fd):
    cur_pos = fd.tell()
    fd.seek(0, SEEK_END)
    end_pos = fd.tell()
    fd.seek(cur_pos, SEEK_SET)
    return end_pos


def prompt_YN(
    prompt_msg: str,
    prompt_question: str = None,
    default_enter_ans: str = "y",
    choices=None,
) -> str:
    """Return 'y' or 'n' depending on the answer entered."""
    if prompt_question is None:
        prompt_question = "Do you want to continue?"
    default_enter_ans = default_enter_ans.lower()
    if choices is None:
        choices = {"y": "[Y/n]", "n": "[y/N]"}
    if default_enter_ans not in choices.keys():
        raise ValueError(
            f"The default_enter_ans of '{default_enter_ans}' is not a possible choice of {choices.keys()}."
        )
    YN_str_to_use = choices.get(default_enter_ans)
    if YN_str_to_use is None:
        raise ValueError(
            f"The default_enter_ans is '{default_enter_ans}' but must be one of {choices.keys()}"
        )
    a = None
    while a not in choices.keys():
        if a is not None:
            print(f"Invalid response: {a}")
        print(prompt_msg)
        a = input(f"{prompt_question} {YN_str_to_use} ").lower()
        if a == "":
            a = default_enter_ans
    return a.lower()[0]


def menu_prompt(menu: dict, prompt: str, random_order: bool = False):
    if not isinstance(menu, dict):
        raise ValueError("The menu argument must be a dict.")
    order = sorted(menu.keys())
    while True:
        if random_order:
            random.shuffle(order)
        for k in order:
            print(f"{k}) {menu[k]['name']}")
        a = input(prompt).lower()
        if a not in menu.keys():
            print("Invalid choice, try again.")
            continue
        break
    func = menu[a].get("func")
    if func:
        return func()
    return a


def deep_union_dicts(dest: dict, src: dict):
    for src_k, src_v in src.items():
        dest_v = dest.get(src_k)
        if isinstance(dest_v, dict) and isinstance(src_v, dict):
            deep_union_dicts(dest_v, src_v)
        else:
            # Overwrite existing d1 value.
            dest[src_k] = src_v
    return dest


def convert_to_pathlib_path(p):
    if p is None:
        return None
    if not isinstance(p, Path):
        p = Path(p)
    return p


def convert_to_str_path(p):
    if p is None:
        return p
    if not isinstance(p, str):
        p = str(p)
    return p


def is_absolute_path(path_to_dir: Union[str, Path]):
    if isinstance(path_to_dir, Path):
        path_to_dir = str(path_to_dir)
    converted_to_abs = os.path.normcase(os.path.abspath(path_to_dir).rstrip("\\/"))
    original_path = os.path.normcase(path_to_dir.rstrip("\\/"))
    return converted_to_abs == original_path


def truncate_posix_timestamp(posix_timestamp):
    """Return a POSIX timestamp with fractional portion that can be represented
    by Python datetime.
    """
    return datetime.fromtimestamp(posix_timestamp, tz=timezone.utc).timestamp()


def posix_timestamp_to_datetime_utc(posix_timestamp):
    return datetime.fromtimestamp(posix_timestamp, tz=timezone.utc)


def posix_timestamp_to_ISO8601_utc_stamp(posix_timestamp):
    return posix_timestamp_to_datetime_utc(posix_timestamp=posix_timestamp).isoformat(
        timespec="microseconds"
    )


def create_numbered_backup_of_file(path: Union[str, Path], not_exist_ok: bool = False):
    path = convert_to_pathlib_path(path)
    for i in range(100000):
        candidate = path.with_name(path.name + f".{i:0>3}")
        if not candidate.exists():
            break
    if not path.exists():
        if not_exist_ok:
            return
        raise FileNotFoundError(
            f"create_numbered_backup_of_file: The source file does not exist: {str(path)}"
        )
    copy2(src=str(path), dst=str(candidate))
    return candidate


def is_valid_base64_string(str_to_check):
    if not isinstance(str_to_check, (str, bytes, bytearray)):
        raise ValueError(f"Expected str_to_check to be a str, bytes, or bytearray.")
    try:
        decoded = base64.b64decode(str_to_check)
        encoded = base64.b64encode(decoded)
        if isinstance(str_to_check, str):
            return encoded == str_to_check.encode("utf-8")
        else:
            return encoded == str_to_check
    except Exception:
        return False


def clear_file(fileobj: Union[io.IOBase, str, Path], byte_pattern: list[int] = None):
    """This should not be considered secure as it
    cannot guarantee filesystem buffering anomalies.
    """
    if isinstance(fileobj, str):
        fileobj = Path(fileobj)
    if isinstance(fileobj, Path):
        fileobj = fileobj.open("w+b")
    if not isinstance(fileobj, io.IOBase):
        raise InvalidFunctionArgument(
            f"Expecting io.IOBase derived fileobj, str path, or Path object."
        )
    if byte_pattern is None:
        byte_pattern = [0xCC, 0x55, 0x00]
    fileobj.seek(0, SEEK_END)
    total_bytes = fileobj.tell()
    for v in byte_pattern:
        b = bytes([v] * (1024 * 1024 * 25))
        num_remaining = total_bytes
        fileobj.seek(0, SEEK_SET)
        while num_remaining > 0:
            num_to_write = min(num_remaining, len(b))
            fileobj.write(b[:num_to_write])
            num_remaining -= num_to_write
        fileobj.flush()
