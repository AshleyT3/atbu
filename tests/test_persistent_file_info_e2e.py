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
r"""E2E tests for persistent file information.
"""

# pylint: disable=unnecessary-pass
# pylint: disable=unused-import,wrong-import-position
# pylint: disable=line-too-long

from asyncio import InvalidStateError
from collections import namedtuple
from dataclasses import dataclass
from io import SEEK_END, SEEK_SET
import os
from pathlib import Path
from random import randint
import random
import re
import string
from typing import Any
import logging

LOGGER = logging.getLogger(__name__)
import pytest
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

from atbu.common.util_helpers import is_platform_path_case_sensitive
from atbu.tools.backup.global_hasher import GlobalHasherDefinitions
from atbu.tools.backup.constants import (
    ATBU_PERSIST_TYPE_PER_BOTH,
    ATBU_PERSIST_TYPE_PER_DIR,
    ATBU_PERSIST_TYPE_PER_FILE,
    ATBU_PERSISTENT_INFO_DB_EXTENSION,
)
from atbu.tools.persisted_info.file_info import (
    ATBU_PERSISTENT_INFO_EXTENSION,
    FileInformation,
    FileInformationPersistent,
)
from atbu.tools.persisted_info.database import (
    FileInformationDatabaseCollection,
)

from .common_helpers import (
    DirInfo,
    StaticTestValues,
    create_test_data_directory_default_levels,
    directories_match_entirely_by_order,
    duplicate_tree,
    establish_random_seed,
    get_rel_path,
    get_rel_path_nc,
    run_atbu,
)

SIZE_1MB = 1024 * 1024
SIZE_2MB = 2 * SIZE_1MB
SIZE_BINARY_CONTENTS_1 = SIZE_1MB
SIZE_BINARY_CONTENTS_2 = SIZE_1MB + 1
SIZE_BINARY_CONTENTS_3 = SIZE_1MB + 2
SIZE_BINARY_CONTENTS_4 = SIZE_2MB
SIZE_BINARY_CONTENTS_5 = SIZE_2MB + 1
BYTES_16 = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
TEXT_FILE_CONTENTS_1 = "What a wonderful day!"
TEXT_FILE_CONTENTS_2 = "What a wonderful day!!"
TEXT_FILE_CONTENTS_4 = "What a wonderful day!!!"
TEXT_FILE_CONTENTS_5 = "What a wonderful evening!"

STATE_ORIGINAL = "original"
STATE_DELETED = "deleted"
STATE_BITROT = "bitrot"


def setup_module(module):  # pylint: disable=unused-argument
    pass


def teardown_module(module):  # pylint: disable=unused-argument
    pass


LayoutEntry = namedtuple("LayoutEntry", "directory, file_name, content_type, content")

basic_dir_layout1: list[LayoutEntry] = [
    LayoutEntry(
        "Folder1",
        "Folder1File1-SIZE_BINARY_CONTENTS_1.bin",
        "binary",
        SIZE_BINARY_CONTENTS_1,
    ),
    LayoutEntry(
        "Folder1", "Folder1File2-TEXT_FILE_CONTENTS_1.txt", "text", TEXT_FILE_CONTENTS_1
    ),
    LayoutEntry(
        "Folder1", "Folder1File3-TEXT_FILE_CONTENTS_4.txt", "text", TEXT_FILE_CONTENTS_4
    ),
    LayoutEntry(
        "Folder1",
        "Folder1File4-SIZE_BINARY_CONTENTS_5.bin",
        "binary",
        SIZE_BINARY_CONTENTS_5,
    ),
    LayoutEntry(
        "Folder2",
        "Folder2File1-SIZE_BINARY_CONTENTS_2.bin",
        "binary",
        SIZE_BINARY_CONTENTS_2,
    ),
    LayoutEntry(
        "Folder2",
        "Folder2File2-SIZE_BINARY_CONTENTS_3.bin",
        "binary",
        SIZE_BINARY_CONTENTS_3,
    ),
    LayoutEntry(
        "Folder2/Folder2Folder1",
        "Folder2Folder1File1-SIZE_BINARY_CONTENTS_1.bin",
        "binary",
        SIZE_BINARY_CONTENTS_1,
    ),
    LayoutEntry(
        "Folder2/Folder2Folder1",
        "Folder2Folder1File2-SIZE_BINARY_CONTENTS_4.bin",
        "binary",
        SIZE_BINARY_CONTENTS_4,
    ),
    LayoutEntry(
        "Folder2/Folder2Folder1",
        "Folder2Folder1File3-SIZE_BINARY_CONTENTS_4.bin",
        "binary",
        SIZE_BINARY_CONTENTS_4,
    ),
    LayoutEntry(
        "Folder2/Folder2Folder1",
        "Folder2Folder1File4-SIZE_BINARY_CONTENTS_5.bin",
        "binary",
        SIZE_BINARY_CONTENTS_5,
    ),
    LayoutEntry(
        "Folder2/Folder2Folder1",
        "Folder2Folder1File5-TEXT_FILE_CONTENTS_4.txt",
        "text",
        TEXT_FILE_CONTENTS_4,
    ),
    LayoutEntry(
        "Folder2/Folder2Folder1",
        "Folder2Folder1File6-TEXT_FILE_CONTENTS_1.txt",
        "text",
        TEXT_FILE_CONTENTS_1,
    ),
    LayoutEntry(
        "Folder2/Folder2Folder1",
        "Folder2Folder1File7-TEXT_FILE_CONTENTS_2.txt",
        "text",
        TEXT_FILE_CONTENTS_2,
    ),
]

OutputExtractionDefinition = namedtuple(
    "OutputExtractionDefinition", "name, regex, cls"
)
UpdatedFileInfo = namedtuple("UpdatedFileHash", "path, hash_name, hash")
AddedFileInfo = namedtuple("AddedFileInfo", "path, hash_name, hash")
UpToDateFileInfo = namedtuple("UpToDateFileInfo", "path, hash_name, hash")
AddedFileInfoDetailed = namedtuple(
    "AddedFileInfo", "path, config_path, size_in_bytes, last_modified, hash_name, hash"
)
output_extraction_definitions: list[OutputExtractionDefinition] = [
    OutputExtractionDefinition(
        name="UpdatedFileInfo",
        # Example: Updated info: path=<path_name_here> sha256=<digest_here>
        regex=re.compile(
            f".*The.*file info was updated: path=([^\\s]+)\\s+([^=]+)=([0-9a-fA-F]+).*"
        ),
        cls=UpdatedFileInfo,
    ),
    OutputExtractionDefinition(
        name="AddedFileInfo",
        # Example: Updated info: path=<path_name_here> sha256=<digest_here>
        regex=re.compile(
            f".*The.*file info was added: path=([^\\s]+)\\s+([^=]+)=([0-9a-fA-F]+).*"
        ),
        cls=AddedFileInfo,
    ),
    OutputExtractionDefinition(
        name="UpToDateFileInfo",
        # Example: Updated info: path=<path_name_here> sha256=<digest_here>
        regex=re.compile(
            f".*The.*file info was up to date: path=([^\\s]+)\\s+([^=]+)=([0-9a-fA-F]+).*"
        ),
        cls=UpToDateFileInfo,
    ),
    OutputExtractionDefinition(
        name="AddedFileInfoDetailed",
        # Example: Adding file information to results: path=<path_name_here>\nconfig_path=<path_name_here>\ninfo_current...\n  sizeinbytes=1048576\n  lastmodified=2022/03/28-00:17:40\n  sha256=<digest_here>\ninfo_history...\n  INFO.0000:\n    sizeinbytes=1048576\n    lastmodified=2022/03/28-00:17:40\n    sha256=<digest_here>'
        regex=re.compile(
            f".*The.*file info was added:"
            f".*path=([^\\s]+).*\n.*config_path=([^\\s]+).*\n.*info_current.*\n.*sizeinbytes=(\\d+).*\n.*lastmodified=([^\\s]+).*\n.*\\s([^\\s=]+)=([0-9a-zA-Z]+).*\n.*info_history.*"
        ),
        cls=AddedFileInfoDetailed,
    ),
]


def get_persist_type_option(persist_types: list[str]) -> str:
    if len(persist_types) == 1:
        persist_type_prefix = persist_types[0]
    else:
        persist_type_prefix = ATBU_PERSIST_TYPE_PER_BOTH
    return persist_type_prefix


@dataclass
class SpecificLayoutEntry:
    parent: object
    dir_path: Path
    file_path: Path
    config_file_path: Path
    file_name: Path
    content_type: string
    content: Any
    state: string
    old_digest: string
    validated: bool = False


class SpecificLayout:
    def __init__(
        self,
        root_path: Path,
        layout: list[LayoutEntry],
        persist_types: list[str] = None,
    ):
        if persist_types is None:
            persist_types = [ATBU_PERSIST_TYPE_PER_FILE]
        self.persist_types = persist_types
        self.root_path = root_path
        self.dbc: FileInformationDatabaseCollection = None
        self.dict_ncpath_to_fi: dict[str, FileInformationPersistent] = None
        self._entries: list[SpecificLayoutEntry] = []
        for le in layout:
            dir_path: Path = root_path / le.directory
            file_path: Path = dir_path / le.file_name
            config_file_path: Path = file_path.with_suffix(
                file_path.suffix + ATBU_PERSISTENT_INFO_EXTENSION
            )
            self._entries.append(
                SpecificLayoutEntry(
                    parent=self,
                    dir_path=dir_path,
                    file_path=file_path,
                    config_file_path=config_file_path,
                    file_name=le.file_name,
                    content_type=le.content_type,
                    content=le.content,
                    state=STATE_ORIGINAL,
                    old_digest=None,
                    validated=False,
                )
            )

    def load_db(self):
        if self.dbc is not None:
            return self.dbc
        self.dbc = FileInformationDatabaseCollection(
            source_path=self.root_path, persist_types=self.persist_types
        )
        self.dbc.load()
        self.dict_ncpath_to_fi = self.dbc.get_dict_nc_path_to_fi()
        return self.dbc

    def reload_db(self):
        self.dbc = None
        self.load_db()

    def get_file_info_from_db_cfg(self, sle: SpecificLayoutEntry):
        self.load_db()
        nc_file_path = os.path.normcase(str(sle.file_path))
        fi = self.dict_ncpath_to_fi.get(nc_file_path)
        return fi

    def get_file_info(self, sle: SpecificLayoutEntry, is_read: bool = False):
        if ATBU_PERSIST_TYPE_PER_FILE in self.persist_types:
            fi = FileInformationPersistent(path=str(sle.file_path))
            if is_read:
                fi.read_info_data_file()
        elif ATBU_PERSIST_TYPE_PER_DIR in self.persist_types:
            fi = self.get_file_info_from_db_cfg(sle=sle)
            if fi is None:
                fi = FileInformationPersistent(path=str(sle.file_path))
        return fi

    def is_config_present(self, sle: SpecificLayoutEntry):
        for pt in self.persist_types:
            if pt == ATBU_PERSIST_TYPE_PER_DIR:
                return self.get_file_info_from_db_cfg(sle=sle) is not None
            elif pt == ATBU_PERSIST_TYPE_PER_FILE:
                return sle.config_file_path.exists()
            else:
                raise InvalidStateError(f"Expected value persist type but got {pt}")

    def delete_config_file(self, sle: SpecificLayoutEntry):
        for pt in self.persist_types:
            if pt == ATBU_PERSIST_TYPE_PER_DIR:
                # Do nothing for DB case because, in
                # real user scenario, DB does not
                # auto-update, user must run update-digests
                # which tests within do themselves.
                pass
            elif pt == ATBU_PERSIST_TYPE_PER_FILE:
                # Simulate user deleted config file (along
                # with the data file).
                sle.config_file_path.unlink()
            else:
                raise InvalidStateError(f"Expected value persist type but got {pt}")

    @property
    def is_per_file_config(self) -> bool:
        return ATBU_PERSIST_TYPE_PER_FILE in self.persist_types

    @property
    def entries(self):
        return self._entries

    def __iter__(self):
        return self.entries.__iter__()

    def __getitem__(self, key):
        return self.entries.__getitem__(key)


def reset_specific_layout_validated_state(layout: SpecificLayout):
    for sle in layout:
        sle.validated = False


def create_binary_file(file_path: Path, size):
    LOGGER.debug(f"Creating binary file: path={file_path} size={size}")
    with open(file_path, "wb") as f:
        b = BYTES_16 * int(SIZE_1MB / len(BYTES_16))  # 1MB
        while size >= SIZE_1MB:
            f.write(b)
            size -= SIZE_1MB
        while size >= len(BYTES_16):
            f.write(BYTES_16)
            size -= len(BYTES_16)
        while size > 0:
            size_to_write = min(size, len(BYTES_16))
            f.write(BYTES_16[:size_to_write])
            size -= size_to_write


def create_text_file(file_path: Path, contents):
    LOGGER.debug(
        f"Creating text file: path={file_path} size={len(contents)} contents={contents[:128]}"
    )
    with open(file_path, "wt", encoding="utf-8") as f:
        f.write(contents)


def create_test_dir_layout(root_path: Path, specific_layout: SpecificLayout):
    LOGGER.debug(f"Creating test dir layout in {root_path}")
    for sle in specific_layout:
        LOGGER.debug(f"Creating directory: {sle.dir_path}")
        sle.dir_path.mkdir(exist_ok=True)
        if sle.content_type == "binary":
            create_binary_file(sle.file_path, sle.content)
        elif sle.content_type == "text":
            create_text_file(sle.file_path, sle.content)


def extract_info_from_output(output_lines: list[str]):
    info = []
    for output in output_lines:
        for oed in output_extraction_definitions:
            mo = oed.regex.match(output)
            if mo is not None:
                info.append(oed.cls(*mo.groups()))
    return info


def is_digest_in_output(digest: str, output_lines: list[str]):
    digest = digest.lower()
    for output in output_lines:
        if output.lower().find(digest) != -1:
            return True
    return False


def verify_specific_layout_validated(specific_layout: SpecificLayout):
    for sle in specific_layout:
        assert sle.validated


def verify_output_file_hash_info(
    output_info_list: list,
    file_path: Path,
    state: str,
    digest_from_config_file: str,
    hashing_algo_name: str,
):
    for o in output_info_list:
        if isinstance(o, UpdatedFileInfo):
            # if isinstance(oi, UpdatedFileInfo):
            ufh: UpdatedFileInfo = o
            if Path(ufh.path) == file_path:
                assert state != STATE_DELETED
                assert ufh.hash_name == hashing_algo_name
                assert ufh.hash == digest_from_config_file
                return True
        elif isinstance(o, AddedFileInfo):
            afi: AddedFileInfo = o
            if Path(afi.path) == file_path:
                assert state != STATE_DELETED
                assert afi.hash_name == hashing_algo_name
                assert afi.hash == digest_from_config_file
                return True
        elif isinstance(o, UpToDateFileInfo):
            afi: UpToDateFileInfo = o
            if Path(afi.path) == file_path:
                assert state != STATE_DELETED
                assert afi.hash_name == hashing_algo_name
                assert afi.hash == digest_from_config_file
                return True
    if state != STATE_DELETED:
        fail(
            f"File name and hash not found in test output and not expected to be {state}: path={file_path}"
        )


def verify_expected_vs_actual(specific_layout: SpecificLayout, info: list):
    primary_hashing_algo_name = (
        GlobalHasherDefinitions().get_primary_hashing_algo_name()
    )
    for sle in specific_layout:
        sl: SpecificLayout = sle.parent
        fidf = None
        digest = None
        calculated_hash = None
        if sle.state == STATE_ORIGINAL:
            assert sle.file_path.exists()
            assert sl.is_config_present(sle)
            fidf = sl.get_file_info(sle=sle, is_read=True)
            assert str(sle.file_path) == fidf.path
            if sl.is_per_file_config:
                assert sle.config_file_path == Path(fidf.info_data_file_path)
                assert str(sle.file_path) == fidf.path
                assert sle.config_file_path == Path(fidf.info_data_file_path)
            digest = fidf.get_current_digest()
            verify_output_file_hash_info(
                output_info_list=info,
                file_path=sle.file_path,
                state=sle.state,
                digest_from_config_file=digest,
                hashing_algo_name=primary_hashing_algo_name,
            )
            calculated_hash = FileInformation(path=str(sle.file_path)).primary_digest
            assert digest == calculated_hash
            sle.validated = True
        elif sle.state == STATE_DELETED:
            assert not sle.file_path.exists()
            assert not sl.is_config_present(sle)
            fidf = sl.get_file_info(sle=sle)
            with raises(FileNotFoundError):
                fidf.read_info_data_file()
            verify_output_file_hash_info(
                output_info_list=info,
                file_path=sle.file_path,
                state=sle.state,
                digest_from_config_file="",
                hashing_algo_name=primary_hashing_algo_name,
            )
            sle.validated = True
        elif sle.state == STATE_BITROT:
            assert sle.file_path.exists()
            assert sl.is_config_present(sle)
            fidf = sl.get_file_info(sle=sle, is_read=True)
            digest = fidf.get_current_digest()
            verify_output_file_hash_info(
                output_info_list=info,
                file_path=sle.file_path,
                state=sle.state,
                digest_from_config_file=digest,
                hashing_algo_name=primary_hashing_algo_name,
            )
            calculated_hash = FileInformation(path=str(sle.file_path)).primary_digest
            assert digest == calculated_hash
            assert (
                sle.old_digest != digest
            )  # pre-bitrot digest does not equal post-bitrot digest.
            sle.validated = True
        else:
            fail("Unknown state.")
    verify_specific_layout_validated(specific_layout=specific_layout)


def verify_config_files_exist(root_path: Path, layout: list[LayoutEntry]):
    specific_layout = SpecificLayout(root_path=root_path, layout=layout)
    for sle in specific_layout:
        assert sle.file_path.exists()
        assert sle.config_file_path.exists()


def verify_config_files_exist2(
    persist_types: list[str],
    root_path: Path,
    layout: list[LayoutEntry],
):
    specific_layout = SpecificLayout(
        root_path=root_path,
        layout=layout,
        persist_types=persist_types,
    )
    for sle in specific_layout:
        assert sle.file_path.exists()
        assert specific_layout.is_config_present(sle)


def create_layout1(
    persist_types: list[str],
    tmp_path: Path,
) -> tuple[Path, SpecificLayout, Path, SpecificLayout,]:
    locA_path = tmp_path / "LocationA"
    locB_path = tmp_path / "LocationB"
    locA_path.mkdir()
    locB_path.mkdir()
    locA_specific_layout = SpecificLayout(
        root_path=locA_path,
        layout=basic_dir_layout1,
        persist_types=persist_types,
    )
    locB_specific_layout = SpecificLayout(
        root_path=locB_path,
        layout=basic_dir_layout1,
        persist_types=persist_types,
    )
    create_test_dir_layout(root_path=locA_path, specific_layout=locA_specific_layout)
    create_test_dir_layout(root_path=locB_path, specific_layout=locB_specific_layout)
    return locA_path, locA_specific_layout, locB_path, locB_specific_layout


def create_layout1_with_config_files(
    persist_types: list[str], tmp_path: Path, pytester: Pytester
):
    persist_type_option = get_persist_type_option(persist_types=persist_types)
    locA_path, locA_specific_layout, locB_path, locB_specific_layout = create_layout1(
        persist_types=persist_types,
        tmp_path=tmp_path,
    )
    argv = [
        "update-digests",
        f"--{persist_type_option}",
        "--locations",
        str(locA_path),
        str(locB_path),
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="update-digests",
    )
    assert rr.ret == ExitCode.OK
    verify_config_files_exist2(
        persist_types=persist_types, root_path=locA_path, layout=basic_dir_layout1
    )
    verify_config_files_exist2(
        persist_types=persist_types, root_path=locB_path, layout=basic_dir_layout1
    )
    return locA_path, locA_specific_layout, locB_path, locB_specific_layout


def update_digests(
    persist_types: list[str],
    location: str,
    is_digest_change_detection: bool,
    tmp_path: Path,
    pytester: Pytester,
):
    persist_type_option = get_persist_type_option(persist_types=persist_types)

    if is_digest_change_detection:
        # The default is date/time and size changes (faster), but
        # at caller's discretion, use digest-based (recalc all digests).
        argv = [
            "update-digests",
            "--change-detection-type",
            "digest",
            f"--{persist_type_option}",
            "--locations",
            location,
        ]
    else:
        argv = [
            "update-digests",
            f"--{persist_type_option}",
            "--locations",
            location,
        ]

    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="update-digests",
    )
    assert rr.ret == ExitCode.OK


def update_digests_specific_layout(
    specific_layout: SpecificLayout,
    is_digest_change_detection: bool,
    update_only_db_cfg: bool,
    tmp_path: Path,
    pytester: Pytester,
):
    if not update_only_db_cfg or not specific_layout.is_per_file_config:
        # DB case will not have its config "deleted" until rescan.
        # Rescan to update digests/db.
        update_digests(
            persist_types=specific_layout.persist_types,
            location=str(specific_layout.root_path),
            is_digest_change_detection=is_digest_change_detection,
            tmp_path=tmp_path,
            pytester=pytester,
        )
        if not specific_layout.is_per_file_config:
            specific_layout.reload_db()


persist_type_parameters = [
    pytest.param(
        [ATBU_PERSIST_TYPE_PER_DIR],
        id=ATBU_PERSIST_TYPE_PER_DIR.replace("-", "_"),
    ),
    pytest.param(
        [ATBU_PERSIST_TYPE_PER_FILE],
        id=ATBU_PERSIST_TYPE_PER_FILE.replace("-", "_"),
    ),
]


@pytest.mark.parametrize(
    "persist_types",
    persist_type_parameters,
)
def test_create_info(
    persist_types: list[str],
    tmp_path: Path,
    pytester: Pytester,
):
    create_layout1_with_config_files(persist_types, tmp_path, pytester)


@pytest.mark.parametrize(
    "persist_types",
    persist_type_parameters,
)
def test_diff(
    persist_types: list[str],
    tmp_path: Path,
    capsys: CaptureFixture,  # pylint: disable=unused-argument
    caplog: LogCaptureFixture,
    pytester: Pytester,
):
    caplog.set_level("DEBUG")
    (
        locA_path,
        locA_specific_layout,
        locB_path,
        locB_specific_layout,
    ) = create_layout1_with_config_files(
        persist_types=persist_types,
        tmp_path=tmp_path,
        pytester=pytester,
    )

    persist_type_option = get_persist_type_option(persist_types=persist_types)

    argv = [
        "diff",
        f"--{persist_type_option}",
        "--location-a",
        str(locA_path),
        "--location-b",
        str(locB_path),
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff1",
    )
    assert rr.ret == ExitCode.OK
    info = extract_info_from_output(output_lines=rr.outlines)

    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)

    reset_specific_layout_validated_state(layout=locA_specific_layout)
    reset_specific_layout_validated_state(layout=locB_specific_layout)

    caplog.clear()
    argv = [
        "diff",
        f"--{persist_type_option}",
        "--location-a",
        str(locA_path),
        "--location-b",
        str(locB_path),
        "--loglevel",
        "DEBUG",
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff2",
    )
    assert rr.ret == ExitCode.OK
    info = extract_info_from_output(output_lines=rr.outlines)

    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)

    pass


@pytest.mark.parametrize(
    "persist_types",
    persist_type_parameters,
)
def test_diff_with_deleted_files(
    persist_types: list[str],
    tmp_path: Path,
    capsys: CaptureFixture,  # pylint: disable=unused-argument
    caplog: LogCaptureFixture,
    pytester: Pytester,
):
    persist_type_option = get_persist_type_option(persist_types=persist_types)

    (
        locA_path,
        locA_specific_layout,
        locB_path,
        locB_specific_layout,
    ) = create_layout1_with_config_files(
        persist_types=persist_types, tmp_path=tmp_path, pytester=pytester
    )

    argv = [
        "diff",
        f"--{persist_type_option}",
        "--la",
        str(locA_path),
        "--lb",
        str(locB_path),
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff1",
    )
    info = extract_info_from_output(output_lines=rr.outlines)

    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)

    # Delete from Location A

    reset_specific_layout_validated_state(layout=locA_specific_layout)
    reset_specific_layout_validated_state(layout=locB_specific_layout)

    sle: SpecificLayoutEntry = locA_specific_layout[3]
    sle.file_path.unlink()
    locA_specific_layout.delete_config_file(sle)
    sle.state = STATE_DELETED

    sle: SpecificLayoutEntry = locA_specific_layout[6]
    sle.file_path.unlink()
    locA_specific_layout.delete_config_file(sle)
    sle.state = STATE_DELETED

    update_digests_specific_layout(
        specific_layout=locA_specific_layout,
        is_digest_change_detection=False,
        update_only_db_cfg=True,
        tmp_path=tmp_path,
        pytester=pytester,
    )

    caplog.clear()
    argv = [
        "diff",
        f"--{persist_type_option}",
        "--location-a",
        str(locA_path),
        "--location-b",
        str(locB_path),
        "--loglevel",
        "DEBUG",
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff2",
    )
    info = extract_info_from_output(output_lines=rr.outlines)

    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)

    # Delete from Location B

    reset_specific_layout_validated_state(layout=locA_specific_layout)
    reset_specific_layout_validated_state(layout=locB_specific_layout)

    sle: SpecificLayoutEntry = locB_specific_layout[3]
    sle.file_path.unlink()
    locB_specific_layout.delete_config_file(sle)
    sle.state = STATE_DELETED

    sle: SpecificLayoutEntry = locB_specific_layout[7]
    sle.file_path.unlink()
    locB_specific_layout.delete_config_file(sle)
    sle.state = STATE_DELETED

    update_digests_specific_layout(
        specific_layout=locB_specific_layout,
        is_digest_change_detection=False,
        update_only_db_cfg=True,
        tmp_path=tmp_path,
        pytester=pytester,
    )

    caplog.clear()
    argv = [
        "diff",
        f"--{persist_type_option}",
        "--location-a",
        str(locA_path),
        "--location-b",
        str(locB_path),
        "--loglevel",
        "DEBUG",
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff3",
    )
    info = extract_info_from_output(output_lines=rr.outlines)

    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)

    # Delete from Location A and B

    reset_specific_layout_validated_state(layout=locA_specific_layout)
    reset_specific_layout_validated_state(layout=locB_specific_layout)

    sle: SpecificLayoutEntry = locA_specific_layout[4]
    sle.file_path.unlink()
    locA_specific_layout.delete_config_file(sle)
    sle.state = STATE_DELETED

    sle: SpecificLayoutEntry = locB_specific_layout[8]
    sle.file_path.unlink()
    locB_specific_layout.delete_config_file(sle)
    sle.state = STATE_DELETED

    update_digests_specific_layout(
        specific_layout=locA_specific_layout,
        is_digest_change_detection=False,
        update_only_db_cfg=True,
        tmp_path=tmp_path,
        pytester=pytester,
    )

    update_digests_specific_layout(
        specific_layout=locB_specific_layout,
        is_digest_change_detection=False,
        update_only_db_cfg=True,
        tmp_path=tmp_path,
        pytester=pytester,
    )

    caplog.clear()
    argv = [
        "diff",
        f"--{persist_type_option}",
        "--location-a",
        str(locA_path),
        "--location-b",
        str(locB_path),
        "--loglevel",
        "DEBUG",
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff4",
    )
    info = extract_info_from_output(output_lines=rr.outlines)

    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)

    # Delete remaining files of SIZE_BINARY_CONTENTS_5
    # No digests of SIZE_BINARY_CONTENTS_5 should exists afterwards.
    # layout entries at index 3 and 9 are for content #5.

    reset_specific_layout_validated_state(layout=locA_specific_layout)
    reset_specific_layout_validated_state(layout=locB_specific_layout)

    sle: SpecificLayoutEntry = locA_specific_layout[9]
    file_info = locA_specific_layout.get_file_info(sle, is_read=True)
    the_digest = file_info.get_current_digest()
    assert is_digest_in_output(the_digest, rr.outlines)
    sle.file_path.unlink()
    locA_specific_layout.delete_config_file(sle)
    sle.state = STATE_DELETED

    sle: SpecificLayoutEntry = locB_specific_layout[9]
    file_info = locB_specific_layout.get_file_info(sle, is_read=True)
    assert the_digest == file_info.get_current_digest()
    sle.file_path.unlink()
    locB_specific_layout.delete_config_file(sle)
    sle.state = STATE_DELETED

    update_digests_specific_layout(
        specific_layout=locA_specific_layout,
        is_digest_change_detection=False,
        update_only_db_cfg=True,
        tmp_path=tmp_path,
        pytester=pytester,
    )

    update_digests_specific_layout(
        specific_layout=locB_specific_layout,
        is_digest_change_detection=False,
        update_only_db_cfg=True,
        tmp_path=tmp_path,
        pytester=pytester,
    )

    caplog.clear()
    argv = [
        "diff",
        f"--{persist_type_option}",
        "--la",
        str(locA_path),
        "--lb",
        str(locB_path),
        "--loglevel",
        "DEBUG",
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff5",
    )
    info = extract_info_from_output(output_lines=rr.outlines)

    assert not is_digest_in_output(the_digest, rr.outlines)
    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)
    pass


@pytest.mark.parametrize(
    "persist_types",
    persist_type_parameters,
)
def test_diff_bit_rot(
    persist_types: list[str],
    tmp_path: Path,
    capsys: CaptureFixture,  # pylint: disable=unused-argument
    caplog: LogCaptureFixture,
    pytester: Pytester,
):
    persist_type_option = get_persist_type_option(persist_types=persist_types)

    (
        locA_path,
        locA_specific_layout,
        locB_path,
        locB_specific_layout,
    ) = create_layout1_with_config_files(
        persist_types=persist_types, tmp_path=tmp_path, pytester=pytester
    )

    argv = [
        "diff",
        f"--{persist_type_option}",
        "--location-a",
        str(locA_path),
        "--lb",
        str(locB_path),
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff1",
    )
    info = extract_info_from_output(output_lines=rr.outlines)

    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)

    # Simulate bitrot in Location B

    reset_specific_layout_validated_state(layout=locA_specific_layout)
    reset_specific_layout_validated_state(layout=locB_specific_layout)

    sle: SpecificLayoutEntry = locB_specific_layout[3]
    sle.old_digest = locB_specific_layout.get_file_info(sle).primary_digest
    sr: os.stat_result = os.stat(sle.file_path)
    with open(sle.file_path, "r+b") as the_file:
        the_file.seek(0, SEEK_END)
        file_size = the_file.tell()
        mod_pos = int(file_size / 2)
        the_file.seek(mod_pos, SEEK_SET)
        b = the_file.read(1)
        the_file.seek(mod_pos, SEEK_SET)
        the_file.write(bytes([b[0] + 1]))
    os.utime(
        path=sle.file_path,
        times=(
            sr.st_atime,
            sr.st_mtime,
        ),
    )
    sle.state = STATE_BITROT

    update_digests_specific_layout(
        specific_layout=locB_specific_layout,
        is_digest_change_detection=True,
        update_only_db_cfg=False,
        tmp_path=tmp_path,
        pytester=pytester,
    )

    caplog.clear()
    argv = [
        "diff",
        f"--{persist_type_option}",
        "--la",
        str(locA_path),
        "--location-b",
        str(locB_path),
        "--loglevel",
        "DEBUG",
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="diff2-bitrot-detect",
    )
    info = extract_info_from_output(output_lines=rr.outlines)

    verify_expected_vs_actual(specific_layout=locA_specific_layout, info=info)
    verify_expected_vs_actual(specific_layout=locB_specific_layout, info=info)
    pass


def perform_validate_arrange_basic(
    persist_type_option: str,
    original_test_data_directory: Path,
    current_template_root: Path,
    outdated_target_source_root: Path,
    outdated_target_source_root_orig: Path,
    arranged_target_dest_root: Path,
    arrange_undofile_path: Path,
    tmp_path: Path,
    caplog: LogCaptureFixture,
    pytester: Pytester,

):
    is_per_file = True if persist_type_option == ATBU_PERSIST_TYPE_PER_FILE else False

    initial_dir_size_defs = [
        StaticTestValues(values=list(range(64)), some_limit=2),
    ]

    dirs_list, files_list = create_test_data_directory_default_levels(
        path_to_dir=original_test_data_directory,
        file_size_defs=initial_dir_size_defs,
    )

    duplicate_tree(
        src_dir=original_test_data_directory,
        dst_dir=current_template_root,
    )

    duplicate_tree(
        src_dir=current_template_root,
        dst_dir=outdated_target_source_root,
    )

    duplicate_tree(
        src_dir=outdated_target_source_root,
        dst_dir=outdated_target_source_root_orig,
    )

    with DirInfo(dir_path=current_template_root) as template_di:
        template_di.gather_info()

        removed_or_moved_old_rel_paths = set()
        removed_or_moved_new_rel_paths = set()

        # Delete a file.
        files_deleted, files_remaining = template_di.delete_randomly_chosen_files(
            num_to_delete=1,
        )
        deleted_file_rel_path = os.path.normcase(get_rel_path(
                root_path=current_template_root,
                path_within_root=files_deleted[0],
            )
        )
        removed_or_moved_old_rel_paths.add(deleted_file_rel_path)

        idx_available_for_tests = [*range(0, len(template_di.file_list))]
        random.shuffle(idx_available_for_tests)

        # Move a file to a newly created directory.
        idx_to_move = idx_available_for_tests.pop()
        move_src_path = template_di.file_list[idx_to_move].path
        move_src_rel_path = os.path.normcase(get_rel_path(
                root_path=current_template_root,
                path_within_root=move_src_path,
            )
        )
        removed_or_moved_old_rel_paths.add(move_src_rel_path)
        basename_to_move = os.path.basename(move_src_path)
        dest_dir = os.path.join(current_template_root, "NewDir")
        move_dest_path = os.path.join(dest_dir, basename_to_move)
        move_dest_rel_path = os.path.normcase(get_rel_path(
                root_path=current_template_root,
                path_within_root=move_dest_path,
            )
        )
        removed_or_moved_new_rel_paths.add(move_dest_rel_path)
        os.renames(
            old=move_src_path,
            new=move_dest_path,
        )

        # Rename an existing file, keeping in the same directory.
        idx_to_rename = idx_available_for_tests.pop()
        rename_src_path = template_di.file_list[idx_to_rename].path
        rename_src_rel_path = os.path.normcase(get_rel_path(
                root_path=current_template_root,
                path_within_root=rename_src_path,
            )
        )
        removed_or_moved_old_rel_paths.add(rename_src_rel_path)
        base, ext = os.path.splitext(os.path.basename(rename_src_path))
        new_basename_of_rename = f"Rename-{base}-Rename{ext}"
        rename_dest_path = os.path.join(os.path.dirname(rename_src_path), new_basename_of_rename)
        rename_dest_rel_path = os.path.normcase(get_rel_path(
                root_path=current_template_root,
                path_within_root=rename_dest_path,
            )
        )
        removed_or_moved_new_rel_paths.add(rename_dest_rel_path)
        os.renames(
            old=rename_src_path,
            new=rename_dest_path,
        )

        # Rename an existing file, moving it to another directory.
        idx_to_move_rename = idx_available_for_tests.pop()
        move_rename_src_path = template_di.file_list[idx_to_move_rename].path
        move_rename_src_rel_path = os.path.normcase(get_rel_path(
                root_path=current_template_root,
                path_within_root=move_rename_src_path,
            )
        )
        removed_or_moved_old_rel_paths.add(move_rename_src_rel_path)
        base, ext = os.path.splitext(os.path.basename(move_rename_src_path))
        new_basename_of_move_rename = f"Rename-{base}-Rename{ext}"
        move_rename_dest_dir = os.path.join(current_template_root, "NewDirRenamedFile")
        move_rename_dest_path = os.path.join(move_rename_dest_dir, new_basename_of_move_rename)
        move_rename_dest_rel_path = os.path.normcase(get_rel_path(
                root_path=current_template_root,
                path_within_root=move_rename_dest_path,
            )
        )
        removed_or_moved_new_rel_paths.add(move_rename_dest_rel_path)
        os.renames(
            old=move_rename_src_path,
            new=move_rename_dest_path,
        )

    add_files_size_defs = [
        StaticTestValues(values=list(range(1000,1020)), some_limit=2),
    ]

    dirs_added, files_added = create_test_data_directory_default_levels(
        path_to_dir=current_template_root,
        file_size_defs=add_files_size_defs,
        add_files_to_existing=True
    )

    files_remaining.extend(files_added)

    caplog.clear()
    argv = [
        "arrange",
        f"--{persist_type_option}",
        "-t",
        str(current_template_root),
        "-s",
        str(outdated_target_source_root),
        "-d",
        str(arranged_target_dest_root),
        "--undofile",
        str(arrange_undofile_path),
        "--loglevel",
        "DEBUG",
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="arrange1",
    )
    assert rr.ret == ExitCode.OK

    with (
        DirInfo(dir_path=original_test_data_directory) as original_di,
        DirInfo(dir_path=current_template_root) as template_di,
        DirInfo(dir_path=outdated_target_source_root) as target_source_di,
        DirInfo(dir_path=arranged_target_dest_root) as target_dest_di,
    ):
        original_di.gather_info(start_gathering_digests=True)
        template_di.gather_info()
        target_source_di.gather_info()
        target_dest_di.gather_info(start_gathering_digests=True)

        original_set = original_di.get_nc_rel_path_set()
        template_set = template_di.get_nc_rel_path_set()
        target_source_set = target_source_di.get_nc_rel_path_set()
        target_dest_set = target_dest_di.get_nc_rel_path_set()

        #
        # Sanity and test checks for deleted/moved files.
        #

        # The deleted file is in original, not in updated template and target destination.
        assert deleted_file_rel_path in original_set
        assert deleted_file_rel_path in target_source_set
        assert deleted_file_rel_path not in template_set
        assert deleted_file_rel_path not in target_dest_set

        # The original moved file location is in original, not in template and target dest. 
        assert move_src_rel_path in original_set
        assert move_src_rel_path not in template_set
        if is_per_file:
            assert f"{move_src_rel_path}{ATBU_PERSISTENT_INFO_EXTENSION}" not in template_set
        assert move_src_rel_path not in target_source_set
        if is_per_file:
            assert f"{move_src_rel_path}{ATBU_PERSISTENT_INFO_EXTENSION}" not in target_source_set
        assert move_src_rel_path not in target_dest_set
        if is_per_file:
            assert f"{move_src_rel_path}{ATBU_PERSISTENT_INFO_EXTENSION}" not in target_dest_set

        # The moved file dest is not in the original but in template and target dest.
        assert move_dest_rel_path not in original_set
        assert move_dest_rel_path in template_set
        if is_per_file:
            assert f"{move_dest_rel_path}{ATBU_PERSISTENT_INFO_EXTENSION}" in template_set
        assert move_dest_rel_path not in target_source_set
        if is_per_file:
            assert f"{move_dest_rel_path}{ATBU_PERSISTENT_INFO_EXTENSION}" not in target_source_set
        assert move_dest_rel_path in target_dest_set
        if is_per_file:
            assert f"{move_dest_rel_path}{ATBU_PERSISTENT_INFO_EXTENSION}" in target_dest_set

        # The target destination less the template should contain 0 paths because
        # the destination is built based on what is observed in the template.
        target_dest_less_template = target_dest_set.difference(template_set)
        assert len(target_dest_less_template) == 0

        # The original less the newly created target destination set should contain any paths
        # which were removed or moved.
        original_less_target_dest = original_set.difference(target_dest_set)
        assert original_less_target_dest == removed_or_moved_old_rel_paths
        #removed_or_moved_old_rel_paths !!! remove
        #removed_or_moved_new_rel_paths

        # Files added to the template did not exist in the target source, which means they
        # will not exist in the target destination. If 'per-file' is used, .atbu files will
        # exist for all added files which doubles the count (i.e., if 20 files added, 40 
        # additional files will exist in the template). Verify all files added are present
        # in the delta with the target destination. For per-dir, the .atbudb will be present
        # hence +1.
        dest_files_added_count = len(files_added)*2 if is_per_file else len(files_added) + 1
        template_less_target_dest = template_set.difference(target_dest_set)
        assert len(template_less_target_dest) == dest_files_added_count
        files_added_nc_rel_path_set = set([get_rel_path_nc(current_template_root, fa) for fa in files_added])
        assert files_added_nc_rel_path_set.issubset(template_less_target_dest)


        target_source_less_target_dest = target_source_set.difference(target_dest_set)
        assert len(target_source_less_target_dest) == 2
        assert deleted_file_rel_path in target_source_less_target_dest
        if is_per_file:
            assert f"{deleted_file_rel_path}{ATBU_PERSISTENT_INFO_EXTENSION}" in target_source_less_target_dest

        original_rp_fi_dict = original_di.get_nc_rel_path_dict()
        for dest_rp, dest_fi in target_dest_di.get_nc_rel_path_dict().items():
            orig_fi = original_rp_fi_dict.get(dest_rp)
            if orig_fi is None:
                if dest_rp == move_dest_rel_path:
                    orig_fi = original_rp_fi_dict.get(move_src_rel_path)
                elif dest_rp == rename_dest_rel_path:
                    orig_fi = original_rp_fi_dict.get(rename_src_rel_path)
                elif dest_rp == move_rename_dest_rel_path:
                    orig_fi = original_rp_fi_dict.get(move_rename_src_rel_path)
            if orig_fi is not None:
                assert dest_fi == orig_fi
                if is_per_file:
                    fip = FileInformationPersistent(path=dest_fi.path)
                    assert fip.info_data_file_exists()
                    fip.read_info_data_file()
                    assert dest_fi.digest == fip.primary_digest
            elif os.path.splitext(dest_rp)[1] == ATBU_PERSISTENT_INFO_EXTENSION:
                continue
            else:
                fail(f"Expected to validate all target destination files: {dest_rp}")
        pass  # pylint: disable=unnecessary-pass


@pytest.mark.parametrize(
    "persist_types",
    persist_type_parameters,
)
def test_arrange_basic(
    persist_types: list[str],
    tmp_path: Path,
    caplog: LogCaptureFixture,
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    persist_type_option = get_persist_type_option(persist_types=persist_types)
    is_per_file = True if persist_type_option == ATBU_PERSIST_TYPE_PER_FILE else False

    original_test_data_directory = tmp_path / "OriginalTestDataDir"
    current_template_root = tmp_path / "TemplateRoot"
    outdated_target_source_root = tmp_path / "TargetSourceRoot"
    outdated_target_source_root_orig = tmp_path / "TargetSourceRootOrig"
    arranged_target_dest_root = tmp_path / "TargetDestRoot"
    undofile_directory = tmp_path / "UndoFiles"
    undofile_directory.mkdir(parents=True, exist_ok=False)
    arrange1_undofile_path = undofile_directory / "arrange1_undo.json"

    perform_validate_arrange_basic(
        persist_type_option=persist_type_option,
        original_test_data_directory=original_test_data_directory,
        current_template_root=current_template_root,
        outdated_target_source_root=outdated_target_source_root,
        outdated_target_source_root_orig=outdated_target_source_root_orig,
        arranged_target_dest_root=arranged_target_dest_root,
        arrange_undofile_path=arrange1_undofile_path,
        tmp_path=tmp_path,
        caplog=caplog,
        pytester=pytester,
    )


@pytest.mark.parametrize(
    "persist_types",
    persist_type_parameters,
)
def test_arrange_undo(
    persist_types: list[str],
    tmp_path: Path,
    caplog: LogCaptureFixture,
    pytester: Pytester,
):
    establish_random_seed(tmp_path)  # bytes([0,1,2,3])

    persist_type_option = get_persist_type_option(persist_types=persist_types)
    is_per_file = True if persist_type_option == ATBU_PERSIST_TYPE_PER_FILE else False

    original_test_data_directory = tmp_path / "OriginalTestDataDir"
    current_template_root = tmp_path / "TemplateRoot"
    outdated_target_source_root = tmp_path / "TargetSourceRoot"
    outdated_target_source_root_orig = tmp_path / "TargetSourceRootOrig"
    arranged_target_dest_root = tmp_path / "TargetDestRoot"
    undofile_directory = tmp_path / "UndoFiles"
    undofile_directory.mkdir(parents=True, exist_ok=False)
    arrange1_undofile_path = undofile_directory / "arrange1_undo.json"

    perform_validate_arrange_basic(
        persist_type_option=persist_type_option,
        original_test_data_directory=original_test_data_directory,
        current_template_root=current_template_root,
        outdated_target_source_root=outdated_target_source_root,
        outdated_target_source_root_orig=outdated_target_source_root_orig,
        arranged_target_dest_root=arranged_target_dest_root,
        arrange_undofile_path=arrange1_undofile_path,
        tmp_path=tmp_path,
        caplog=caplog,
        pytester=pytester,
    )

    caplog.clear()
    argv = [
        "undo",
        "--undofile",
        str(arrange1_undofile_path),
        "--loglevel",
        "DEBUG",
    ]
    rr = run_atbu(
        pytester,
        tmp_path,
        *argv,
        log_base_name="undo_arrange1",
    )
    assert rr.ret == ExitCode.OK

    with (
        DirInfo(dir_path=outdated_target_source_root_orig) as target_source_orig,
        DirInfo(dir_path=outdated_target_source_root) as target_source_undo,
    ):
        # For this test, .atbu and atbudb files are generated as part of the arrange command
        # so are not part of the original target source content.
        re_pat_exclude_atbu = re.compile(
            pattern=(
                rf".*("
                rf"{re.escape(ATBU_PERSISTENT_INFO_EXTENSION)}|"
                rf"{re.escape(ATBU_PERSISTENT_INFO_DB_EXTENSION)})$"
            ),
            flags=0 if is_platform_path_case_sensitive() else re.IGNORECASE
        )
        target_source_orig.gather_info(
            start_gathering_digests=True,
            re_pattern_exclude=re_pat_exclude_atbu,
        )
        target_source_undo.gather_info(
            start_gathering_digests=True,
            re_pattern_exclude=re_pat_exclude_atbu,
        )
        assert len(target_source_orig.file_list) == len(target_source_undo.file_list)
        assert directories_match_entirely_by_order(
            di1=target_source_orig, di2=target_source_undo
        )
    pass