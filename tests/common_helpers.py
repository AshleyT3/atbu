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
r"""Common test helpers.
"""

# pylint: disable=line-too-long

from dataclasses import dataclass
from io import SEEK_END, SEEK_SET
import os
from concurrent.futures import ProcessPoolExecutor
import glob
import hashlib
import platform
import random
from pathlib import Path
from random import randint
import re
import shutil

# pylint: disable=unused-import,wrong-import-position
from pytest import (
    Pytester,
    RunResult,
    ExitCode,
)

# Even for local-only tests, include chunk sizes for
# max-related potential edge cases.
from libcloud.storage.drivers.azure_blobs import (
    AZURE_DOWNLOAD_CHUNK_SIZE,
    AZURE_UPLOAD_CHUNK_SIZE,
)
from atbu.tools.backup.credentials import CredentialAesKey

# Even for local-only tests, include chunk sizes for
# max-related potential edge cases.
from atbu.tools.backup.storage_interface.base import (
    DEFAULT_CHUNK_DOWNLOAD_SIZE,
    DEFAULT_CHUNK_UPLOAD_SIZE,
)

from atbu.tools.backup.config import AtbuConfig
from atbu.tools.backup.storage_def_credentials import StorageDefCredentialSet
from atbu.common.exception import InvalidStateError  # pylint: disable=unused-import


def copy2_pacifier_patch(src, dst, *args, **kwargs):
    print(f"Copying {src} -> {dst}")
    return shutil.copy2(src=src, dst=dst, *args, **kwargs)


def duplicate_tree(src_dir, dst_dir, no_pacifier: bool = False):
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)
    assert src_dir.is_dir()
    assert not dst_dir.exists()
    copy_func = copy2_pacifier_patch
    if no_pacifier:
        copy_func = shutil.copy2
    shutil.copytree(src=src_dir, dst=dst_dir, copy_function=copy_func)


class TestValues:
    def __init__(self, values, some_limit) -> None:
        self._orig_values = values
        self._pending_values = values
        self._some_limit = some_limit

    @property
    def remaining_values(self):
        return len(self._pending_values)

    def get_some_values(self) -> list:
        num = randint(0, self._some_limit)
        result = self._pending_values[0:num]
        del self._pending_values[0:num]
        return result

    def get_remaining_values(self) -> list:
        result = self._pending_values[0:]
        del self._pending_values[0:]
        return result


class RandomTestValues(TestValues):
    def __init__(
        self,
        low_count_inclusive,
        high_count_inclusive,
        low_inclusive,
        high_inclusive,
        some_limit,
    ) -> None:
        self.low_count_inclusive = low_count_inclusive
        self.high_count_inclusive = high_count_inclusive
        self.low_inclusive = low_inclusive
        self.high_inclusive = high_inclusive
        count = randint(self.low_count_inclusive, self.high_count_inclusive)
        super().__init__(
            values=[self._get_a_value() for _ in range(count)], some_limit=some_limit
        )

    def _get_a_value(self):
        return randint(self.low_inclusive, self.high_inclusive)


def establish_random_seed(tmp_path, random_seed: bytes = None):
    if random_seed is None:
        random_seed = os.urandom(4)
    random_seed_file = tmp_path.joinpath("random_seed.txt")
    if not random_seed_file.is_file():
        random_seed_file.write_text(random_seed.hex())
    else:
        # Use existing seed file.
        random_seed = bytes.fromhex(random_seed_file.read_text())
    random.seed(random_seed)
    return random_seed


def create_test_data_file(file_path, size):
    SIZE_1MB = 1024 * 1024
    b_1mb = bytes(
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] * int(SIZE_1MB / 16)
    )
    with open(file_path, "wb") as f:
        while size >= SIZE_1MB:
            f.write(b_1mb)
            size -= SIZE_1MB
        f.write(b_1mb[0:size])


def create_test_files(
    path_to_dir: Path,
    file_size_def: list[TestValues],
    use_remaining: bool,
    add_files_to_existing: bool,
):
    total_files_created = 0
    for fsd in file_size_def:
        if use_remaining:
            sizes = fsd.get_remaining_values()
        else:
            sizes = fsd.get_some_values()
        for size in sizes:
            i = total_files_created
            while True:
                add_str = ""
                if add_files_to_existing:
                    add_str = "add-"
                file_path = path_to_dir / f"TestFile-{add_str}{i:03}.bin"
                if not file_path.exists():
                    break
                if not add_files_to_existing:
                    raise InvalidStateError(
                        f"Unexpected: File already existed: {str(file_path)}"
                    )
                i += 1
            create_test_data_file(file_path, size)
            total_files_created += 1
    return total_files_created


def create_test_data_directory(
    path_to_dir: Path,
    max_levels: int,
    max_dirs_per_level: int,
    per_level_file_size_def: list[TestValues],
    add_files_to_existing: bool,
):
    def create_recurse(
        path_to_dir: Path,
        max_levels: int,
        max_dirs_per_level: int,
        per_level_file_size_def: list[TestValues],
        add_files_to_existing: bool,
        level: int = 0,
    ):
        total_files = 0
        path_to_dir.mkdir(parents=True, exist_ok=True)
        if max_levels > 0:
            if level == 0:
                num_dirs = randint(min(2, max_dirs_per_level), max_dirs_per_level)
            else:
                num_dirs = randint(0, max_dirs_per_level)
            for dir_num in range(num_dirs):
                add_str = ""
                if add_files_to_existing:
                    add_str = "add-"
                i = dir_num
                while True:
                    subdir_path = path_to_dir / f"TestDir-{add_str}{i:03}"
                    if not subdir_path.exists():
                        break
                    if not add_files_to_existing:
                        raise InvalidStateError(
                            f"Unexpected: Directory already existed: {str(subdir_path)}"
                        )
                    i += 1

                total_files += create_recurse(
                    path_to_dir=subdir_path,
                    max_levels=max_levels - 1,
                    max_dirs_per_level=max_dirs_per_level,
                    per_level_file_size_def=per_level_file_size_def,
                    add_files_to_existing=add_files_to_existing,
                    level=level + 1,
                )
        total_files += create_test_files(
            path_to_dir=path_to_dir,
            file_size_def=per_level_file_size_def,
            use_remaining=(level == 0),
            add_files_to_existing=add_files_to_existing,
        )
        return total_files

    return create_recurse(
        path_to_dir=path_to_dir,
        max_levels=max_levels,
        max_dirs_per_level=max_dirs_per_level,
        per_level_file_size_def=per_level_file_size_def,
        add_files_to_existing=add_files_to_existing,
    )


def get_file_digest(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(1024 * 1024 * 5)
            if len(data) == 0:
                break
            h.update(data)
    return h.digest().hex()


class FileInfo:
    def __init__(self, file_path, size: int = None, modified_time=None, digest=None):
        self._file_path = file_path
        self._size = size
        self._modified_time = modified_time
        self._digest = digest

    @property
    def path(self):
        return self._file_path

    @property
    def nc_path(self):
        return os.path.normcase(self._file_path)

    @property
    def digest(self):
        return self._digest

    @property
    def size(self):
        return self._size

    @property
    def modified_time(self):
        return self._modified_time

    def __eq__(self, o) -> bool:
        if not isinstance(o, FileInfo):
            raise ValueError("Expecting TestFileInfo for 'o' other arg.")
        print(f"test_backup: path={self.path}")
        print(f"test_backup:     d1={self.digest} d2={o.digest}")
        print(f"test_backup:     d1_size={self.size} d2_size={o.size}")
        print(
            f"test_backup:     d1_modified={self.modified_time} modified={o.modified_time}"
        )
        return (
            self.size == o.size
            and self.modified_time == o.modified_time
            and self.digest == o.digest
        )


class LocallyPersistedFileInfo(FileInfo):
    def __init__(self, file_path, process_exec: ProcessPoolExecutor):
        super().__init__(file_path=file_path)
        sr: os.stat_result = os.stat(self._file_path)
        self._modified_time = sr.st_mtime
        self._size = sr.st_size
        self._work_future = None
        self.process_exec = process_exec

    def start_update_digest(self, wait: bool = False):
        if self._work_future is None:
            self._work_future = self.process_exec.submit(
                get_file_digest, self._file_path
            )
        if wait:
            self.wait_update_digest()

    def reset_digest(self):
        f = self._work_future
        self._work_future = None
        self._digest = None
        if f is not None and not f.done():
            f.cancel()

    def wait_update_digest(self):
        if not self._work_future:
            raise ValueError("Digest is not being updated.")
        self._work_future.result()

    @property
    def digest(self):
        if self._digest is None:
            self.start_update_digest(wait=True)
            self._digest = self._work_future.result()
        return super().digest


class DirInfo:
    def __init__(self, dir_path=None):
        self.dir_path = dir_path
        self.file_db = {}
        self.file_list = []
        self.process_exec = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process_exec:
            try:
                print("Waiting for ProcessPoolExecutor to shutdown...")
                self.process_exec.shutdown(wait=True)
                print("ProcessPoolExecutor is shutdown.")
                self.process_exec = None
            except Exception as ex:
                print(f"Failure shutting down process exec: {ex}")
                if exc_type is not None:
                    raise
        return False

    def add_file_info(self, finfo: FileInfo):
        self.file_db[finfo.nc_path] = finfo
        self.file_list.append(finfo)

    def gather_info(self, start_gathering_digests: bool = False):
        for p in glob.iglob(os.path.join(self.dir_path, "**"), recursive=True):
            if not os.path.isfile(p):
                continue
            if self.process_exec is None:
                self.process_exec = ProcessPoolExecutor()
            finfo = LocallyPersistedFileInfo(
                file_path=p, process_exec=self.process_exec
            )
            if start_gathering_digests:
                finfo.start_update_digest()
            self.file_db[finfo.nc_path] = finfo
            self.file_list.append(finfo)
        self.file_list.sort(key=lambda fi: fi.nc_path)


def directories_match_entirely_by_order(di1: DirInfo, di2: DirInfo):
    if len(di1.file_list) != len(di2.file_list):
        return False
    for f1, f2 in zip(di1.file_list, di2.file_list):
        if f1 != f2:
            return False
    return True


def directories_match_entirely_by_path(di1: DirInfo, di2: DirInfo):
    if len(di1.file_list) != len(di2.file_list):
        return False
    d1_db = dict(di1.file_db)
    d1_db_tracker = dict(di1.file_db)
    for k, di1_fi in d1_db.items():
        di2_fi = di2.file_db.get(k)
        if di2_fi is None:
            return False
        if di1_fi != di2_fi:
            return False
        del d1_db_tracker[k]
    return len(d1_db_tracker) == 0


def directories_have_no_matches_by_path(di1: DirInfo, di2: DirInfo):
    if len(di1.file_list) == len(di2.file_list):
        return False
    d1_db = dict(di1.file_db)
    d1_db_tracker = dict(di1.file_db)
    for k, di1_fi in d1_db.items():
        di2_fi = di2.file_db.get(k)
        if di2_fi is None:
            del d1_db_tracker[k]
            continue
        if di1_fi == di2_fi:
            return False
        del d1_db_tracker[k]
    return len(d1_db_tracker) == 0


def extract_dir_info_from_verify_log(output_lines: list[str]):
    # pylint: disable=line-too-long
    result = DirInfo()
    # Example:
    # VerifyFile: path=<path_name_here> backup_size=8851403 verified_bytes=8851403 backup_sha256=<digest_here> verify_sha256=<digest_here>
    re_extract = re.compile(
        r".*VerifyFile:\s+path=([^\s]+)\s+backup_size=(\d+)\s+verify_size=(\d+)\s+backup_modified=([^\s]+)\s+backup_sha256=([^\s]+)\s+verify_sha256=([^\s]+).*"
    )
    for line in output_lines:
        m = re_extract.match(line)
        if m is None:
            continue
        file_path = m.groups()[0]
        backup_size = int(m.groups()[1])
        verify_size = int(m.groups()[2])
        backup_modified_time = float(m.groups()[3])
        backup_sha256 = m.groups()[4]
        verify_sha256 = m.groups()[5]
        assert backup_size == verify_size
        assert backup_sha256 == verify_sha256
        result.add_file_info(
            FileInfo(
                file_path=file_path,
                size=verify_size,
                modified_time=backup_modified_time,
                digest=verify_sha256,
            )
        )
    return result


def extract_storage_definition_and_config_file_path(
    output_lines: list[str],
) -> list[tuple[str, str]]:
    result = []
    # Example:
    #  Storage definition atbu-gcs-backup-5b497bb3-c9ef-48a9-af7b-2327fc17fb65 saved to C:\Users\User\AppData\Local\Temp\pytest-of-User\pytest-13\test_create_storage_definition1\.atbu\atbu-config.json
    re_extract = re.compile(r".*Storage definition\s+([^\s]+)\s+saved to ([^\s]+).*")
    for line in output_lines:
        m = re_extract.match(line)
        if m is None:
            continue
        storage_def_name = m.groups()[0]
        atbu_config_path = m.groups()[1]
        result.append(
            (
                storage_def_name,
                atbu_config_path,
            )
        )
    return result


def extract_backup_names_from_log(output_lines: list[str]) -> list[str]:
    names = []
    re_extract_backup_name = re.compile(r"^\s*([^\s]+-\d{8}-\d{6})")
    for line in output_lines:
        m = re_extract_backup_name.match(line)
        if m is None:
            continue
        names.append(m.groups()[0])
    return names


@dataclass
class LogSummaryInfo:
    total_files: int = -1
    total_unchanged_files: int = -1
    total_backup_operations: int = -1
    total_errors: int = -1
    total_successful_backups: int = -1
    bitrot_detection_files: list[str] = None
    total_bitrot_detection_warning: int = 0
    total_bitrot_detection_info: int = 0


def extract_backup_summary_from_log(output_lines: list[str]) -> LogSummaryInfo:
    lsi = LogSummaryInfo()
    lsi.bitrot_detection_files = []
    re_extract_summary = re.compile(
        r"^(Total files|Total unchanged files|Total backup operations|Total errors|Total successful backups)\s+\.+\s+(\d+).*"
    )
    re_extract_detect_bitrot = re.compile(
        r"^(WARNING: |)Potential bitrot or sneaky corruption:.*\s+path=(.*)\s+modified_utc=.*"
    )
    for line in output_lines:
        m = re_extract_summary.match(line)
        if m is not None:
            text = m.groups()[0]
            count = int(m.groups()[1])
            if text == "Total files":
                lsi.total_files = count
            elif text == "Total unchanged files":
                lsi.total_unchanged_files = count
            elif text == "Total backup operations":
                lsi.total_backup_operations = count
            elif text == "Total errors":
                lsi.total_errors = count
            elif text == "Total successful backups":
                lsi.total_successful_backups = count
            continue
        m = re_extract_detect_bitrot.match(line)
        if m is None:
            continue
        warning_str = m.groups()[0]
        path_str = m.groups()[1]
        lsi.bitrot_detection_files.append(path_str)
        if warning_str.find("WARNING") != -1:
            lsi.total_bitrot_detection_warning += 1
        else:
            lsi.total_bitrot_detection_info += 1
    return lsi


def run_atbu(
    pytester: Pytester,
    tmp_path: Path,
    *args,
    stdin=None,
    timeout=120,
    log_base_name: str = None,
):
    if platform.system() == "Windows":
        atbu_path = shutil.which("atbu.exe")
    else:
        atbu_path = shutil.which("atbu")
    assert atbu_path is not None
    if log_base_name is None:
        log_base_name = "main"
    log_file = tmp_path / f"atbu-{log_base_name}.log"
    rr = pytester.run(
        atbu_path,
        *args,
        "--loglevel",
        "DEBUG",
        "--logfile",
        str(log_file),
        timeout=timeout,
        stdin=stdin,
    )
    return rr


def get_file_size_defs_01_basic():
    return [
        TestValues(values=list(range(64)), some_limit=2),
        RandomTestValues(
            low_count_inclusive=5,
            high_count_inclusive=5,
            low_inclusive=1 * 1024 * 1024,
            high_inclusive=10 * 1024 * 1024,
            some_limit=2,
        ),
        RandomTestValues(
            low_count_inclusive=25,
            high_count_inclusive=25,
            low_inclusive=0,
            high_inclusive=1024,
            some_limit=2,
        ),
        TestValues(
            values=list(
                range(DEFAULT_CHUNK_DOWNLOAD_SIZE - 1, DEFAULT_CHUNK_DOWNLOAD_SIZE + 2)
            ),
            some_limit=1,
        ),
        TestValues(
            values=list(
                range(DEFAULT_CHUNK_UPLOAD_SIZE - 1, DEFAULT_CHUNK_UPLOAD_SIZE + 2)
            ),
            some_limit=1,
        ),
        TestValues(
            values=list(
                range(AZURE_DOWNLOAD_CHUNK_SIZE - 1, AZURE_DOWNLOAD_CHUNK_SIZE + 2)
            ),
            some_limit=1,
        ),
        TestValues(
            values=list(
                range(AZURE_UPLOAD_CHUNK_SIZE - 1, AZURE_UPLOAD_CHUNK_SIZE + 2)
            ),
            some_limit=1,
        ),
    ]


def get_file_size_defs_02_minimal():
    return [
        RandomTestValues(
            low_count_inclusive=10,
            high_count_inclusive=10,
            low_inclusive=0,
            high_inclusive=1024,
            some_limit=1,
        ),
    ]


def get_file_size_defs_03_minimal_vary():
    return [
        RandomTestValues(
            low_count_inclusive=1,
            high_count_inclusive=5,
            low_inclusive=0,
            high_inclusive=1024,
            some_limit=1,
        ),
    ]


def get_min_files_expected(file_size_defs):
    total_files = 0
    for fsd in file_size_defs:
        total_files += fsd.remaining_values
    return total_files


def create_test_data_directory_basic(path_to_dir: Path):
    file_size_defs = get_file_size_defs_01_basic()
    min_files_expected = get_min_files_expected(file_size_defs=file_size_defs)
    assert min_files_expected > 0

    num_files_created = create_test_data_directory(
        path_to_dir=path_to_dir,
        max_levels=5,
        max_dirs_per_level=3,
        per_level_file_size_def=file_size_defs,
        add_files_to_existing=False,
    )
    assert num_files_created >= min_files_expected
    return num_files_created


def create_test_data_directory_minimal(
    path_to_dir: Path,
    add_files_to_existing: bool = False,
):
    file_size_defs = get_file_size_defs_02_minimal()
    min_files_expected = get_min_files_expected(file_size_defs=file_size_defs)
    assert min_files_expected > 0

    num_files_created = create_test_data_directory(
        path_to_dir=path_to_dir,
        max_levels=5,
        max_dirs_per_level=3,
        per_level_file_size_def=file_size_defs,
        add_files_to_existing=add_files_to_existing,
    )
    assert num_files_created >= min_files_expected
    return num_files_created


def create_test_data_directory_minimal_vary(
    path_to_dir: Path,
    add_files_to_existing: bool = False,
):
    file_size_defs = get_file_size_defs_03_minimal_vary()
    min_files_expected = get_min_files_expected(file_size_defs=file_size_defs)
    assert min_files_expected > 0

    num_files_created = create_test_data_directory(
        path_to_dir=path_to_dir,
        max_levels=5,
        max_dirs_per_level=3,
        per_level_file_size_def=file_size_defs,
        add_files_to_existing=add_files_to_existing,
    )
    assert num_files_created >= min_files_expected
    return num_files_created


def simulate_bitrot(
    lucky_path: Path,
    lucky_position: int = None,
):
    sr: os.stat_result = os.stat(lucky_path)
    with open(str(lucky_path), "r+b") as the_file:
        the_file.seek(0, SEEK_END)
        file_size = the_file.tell()
        if file_size == 0:
            raise InvalidStateError(
                f"Cannot simulate bitrot on zero-byte file: {str(lucky_path)}"
            )
        if lucky_position is None:
            lucky_position = randint(0, file_size - 1)
        the_file.seek(lucky_position, SEEK_SET)
        b = the_file.read(1)
        the_file.seek(lucky_position, SEEK_SET)
        the_file.write(bytes([b[0] + 1]))
    os.utime(
        path=str(lucky_path),
        times=(
            sr.st_atime,
            sr.st_mtime,
        ),
    )


def induce_simulated_bitrot(
    path_to_dir: Path,
    num_files: int,
) -> list[Path]:
    paths_affected = []
    search_pattern = path_to_dir / "**"
    file_list = list(
        filter(os.path.isfile, glob.iglob(pathname=str(search_pattern), recursive=True))
    )
    if len(file_list) < num_files:
        raise InvalidStateError(
            f"Not enough files: file_list={len(file_list)} num_files={num_files}"
        )
    winners = set()
    for _ in range(num_files):
        attempts_remaining = 100000
        while attempts_remaining > 0:
            attempts_remaining -= 1
            fn = randint(0, len(file_list) - 1)
            if os.path.getsize(file_list[fn]) == 0:
                continue
            if fn not in winners:
                break
        if attempts_remaining <= 0:
            raise InvalidStateError(f"Unexpected: Cannot find file to simulate bitrot.")
        winners.add(fn)
        super_lucky_path = file_list[fn]
        simulate_bitrot(
            lucky_path=str(super_lucky_path),
            lucky_position=None,
        )
        paths_affected.append(super_lucky_path)
    return paths_affected


def duplicate_files(
    path_to_dir: Path,
    num_files: int,
    num_bitrot: int,
) -> list[tuple[Path, Path]]:
    files_duplicated: list[tuple[Path, Path]] = []
    if not isinstance(num_files, int) or num_files <= 0:
        raise ValueError(f"Expecting positive int for num_files.")
    if num_bitrot is not None and (
        not isinstance(num_bitrot, int) or num_bitrot <= 0 or num_bitrot > num_files
    ):
        raise ValueError(
            f"num_bitrot must be a positive int that is less than num_files."
        )
    search_pattern = path_to_dir / "**"
    dirs_and_files = glob.glob(pathname=str(search_pattern), recursive=True)
    file_list = list(
        filter(
            os.path.isfile,
            dirs_and_files,
        )
    )
    dir_list = list(
        filter(
            os.path.isdir,
            dirs_and_files,
        )
    )
    if len(file_list) == 0:
        raise InvalidStateError(f"No files to duplicate.")
    if len(dir_list) == 0:
        raise InvalidStateError(f"No directories to place duplicate.")
    for _ in range(num_files):
        fn = randint(0, len(file_list) - 1)
        file_path = Path(file_list[fn])
        dn = randint(0, len(dir_list) - 1)
        dir_path = Path(dir_list[dn])
        for i in range(100000):
            candidate_dup_file_path = (
                dir_path / f"{file_path.stem}-duplicate-{i:03}{file_path.suffix}"
            )
            if not candidate_dup_file_path.exists():
                break
        if candidate_dup_file_path.exists():
            raise InvalidStateError(
                f"Cannot find duplicate path. last={str(candidate_dup_file_path)}"
            )
        shutil.copy2(src=file_path, dst=candidate_dup_file_path)
        files_duplicated.append(
            (
                file_path,
                candidate_dup_file_path,
            )
        )
    if num_bitrot is None:
        return files_duplicated
    br_winners = set()
    for _ in range(num_bitrot):
        attempts_remaining = 100000
        while attempts_remaining > 0:
            bn = randint(0, len(files_duplicated) - 1)
            path_to_br = files_duplicated[bn][1]
            if bn not in br_winners and os.path.getsize(path_to_br) != 0:
                break
            attempts_remaining -= 1
        if attempts_remaining <= 0:
            raise InvalidStateError(
                f"Cannot find another duplicate to simulate bitrot."
            )
        br_winners.add(bn)
        simulate_bitrot(
            lucky_path=str(path_to_br),
            lucky_position=None,
        )
        files_duplicated[bn] = (*files_duplicated[bn], "bitrot")
    return files_duplicated


def validate_cred_export_import(
    pytester,
    tmp_path,
    atbu_cfg_path,
    source_directory,
    expected_total_files,
    storage_def_name,
    storage_specifier,
):
    # pylint: disable=unused-variable

    restore1_dir_expect_success = tmp_path / "Restore1ExpectSuccess"
    restore2_dir_expect_fail = tmp_path / "Restore2ExpectFail"
    restore3_dir_expect_fail = tmp_path / "Restore3ExpectFail"
    restore4_dir_expect_success = tmp_path / "Restore4ExpectSuccess"
    cred_export_directory = tmp_path / "CredBackup"
    cred_export_filename = cred_export_directory / "exported_creds.json"

    with DirInfo(source_directory) as source_dir_info:
        source_dir_info.gather_info(start_gathering_digests=True)
        assert len(source_dir_info.file_list) == expected_total_files

        #
        # Initial restore should succeed.
        #
        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore1_dir_expect_success,
            timeout=60 * 5,
            log_base_name="restore1-expect-success",
        )
        assert rr.ret == ExitCode.OK
        with DirInfo(restore1_dir_expect_success) as restore1_dir_info:
            restore1_dir_info.gather_info(start_gathering_digests=True)
            assert len(restore1_dir_info.file_list) == expected_total_files
            assert directories_match_entirely_by_order(
                di1=source_dir_info, di2=restore1_dir_info
            )

        #
        # Export credentials.
        #
        cred_export_directory.mkdir(parents=True, exist_ok=True)
        cred_export_filename = cred_export_directory / "exported_creds.json"
        rr = run_atbu(
            pytester,
            tmp_path,
            "creds",
            "export",
            storage_specifier,
            cred_export_filename,
            log_base_name="cred-export",
        )
        assert rr.ret == ExitCode.OK

        #
        # Change encryption key to observe failure afterwards.
        #
        atbu_cfg = AtbuConfig.create_from_file(path=atbu_cfg_path)

        # TODO: review unlock/lock state, save state, dirty.
        cred_set = StorageDefCredentialSet(
            storage_def_name=storage_def_name.lower(),
            storage_def_dict=atbu_cfg.get_storage_def_dict(
                storage_def_name=storage_def_name.lower(),
                must_exist=True,
            ),
        )
        cred_set.populate()
        cred_set.unprotect()
        credential_orig = cred_set.get_encryption_desc_cred().credential
        assert credential_orig.is_private_key_ready
        credential_new = CredentialAesKey()
        credential_new.create_key()
        cred_set.get_encryption_desc_cred().credential = credential_new
        cred_set.protect()
        cred_set.save()

        #
        # Attempt restore without encryption key, observe failure.
        #
        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore2_dir_expect_fail,
            timeout=60 * 5,
            log_base_name="restore2-expect-fail",
        )
        assert rr.ret == ExitCode.TESTS_FAILED
        with DirInfo(restore2_dir_expect_fail) as restore2_dir_info:
            restore2_dir_info.gather_info(start_gathering_digests=True)
            assert len(restore2_dir_info.file_list) == 0
            assert directories_have_no_matches_by_path(
                di1=source_dir_info, di2=restore2_dir_info
            )

        #
        # Delete the storage definition configuration and credentials.
        #
        atbu_cfg = AtbuConfig.create_from_file(path=atbu_cfg_path)
        atbu_cfg.delete_storage_def(storage_def_name=storage_def_name)
        atbu_cfg.save_config_file()

        #
        # Attempt restore without the configuration, observe failure.
        #
        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore3_dir_expect_fail,
            timeout=60 * 5,
            log_base_name="restore3-expect-fail",
        )
        assert rr.ret == ExitCode.TESTS_FAILED
        with DirInfo(restore3_dir_expect_fail) as restore3_dir_info:
            restore3_dir_info.gather_info(start_gathering_digests=True)
            assert len(restore3_dir_info.file_list) == 0
            assert directories_have_no_matches_by_path(
                di1=source_dir_info, di2=restore3_dir_info
            )

        #
        # Import credentials to re-establish the the storage definition itself
        # along with its storage and encryption secrets.
        #

        # Enter 'y' and press ENTER.
        stdin_bytes = f"y{os.linesep}".encode()
        rr = run_atbu(
            pytester,
            tmp_path,
            "creds",
            "import",
            storage_specifier,
            cred_export_filename,
            stdin=stdin_bytes,
            log_base_name="cred-import",
        )
        assert rr.ret == ExitCode.OK

        #
        # Attempt restore with restored config, observe success.
        #
        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore4_dir_expect_success,
            timeout=60 * 5,
            log_base_name="restore4-expect-success",
        )
        assert rr.ret == ExitCode.OK
        with DirInfo(restore4_dir_expect_success) as restore_dir_info:
            restore_dir_info.gather_info(start_gathering_digests=True)
            assert len(source_dir_info.file_list) == expected_total_files
            assert len(restore_dir_info.file_list) == expected_total_files
            assert directories_match_entirely_by_order(
                di1=source_dir_info, di2=restore_dir_info
            )
        pass


def validate_backup_recovery(
    pytester,
    tmp_path,
    atbu_cfg_path,
    source_directory,
    expected_total_files,
    storage_def_name,
    storage_specifier,
):
    # pylint: disable=unused-variable

    restore1_dir_expect_success = tmp_path / "Restore1ExpectSuccess"
    restore2_dir_expect_fail = tmp_path / "Restore2ExpectFail"
    restore3_dir_expect_fail = tmp_path / "Restore3ExpectFail"
    restore4_dir_expect_success = tmp_path / "Restore4ExpectSuccess"
    cred_export_directory = tmp_path / "CredBackup"
    cred_export_filename = cred_export_directory / "exported_creds.json"

    with DirInfo(source_directory) as source_dir_info:
        source_dir_info.gather_info(start_gathering_digests=True)
        assert len(source_dir_info.file_list) == expected_total_files

        #
        # Initial restore should succeed.
        #
        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore1_dir_expect_success,
            timeout=60 * 5,
            log_base_name="restore1-expect-success",
        )
        assert rr.ret == ExitCode.OK
        with DirInfo(restore1_dir_expect_success) as restore1_dir_info:
            restore1_dir_info.gather_info(start_gathering_digests=True)
            assert len(restore1_dir_info.file_list) == expected_total_files
            assert directories_match_entirely_by_order(
                di1=source_dir_info, di2=restore1_dir_info
            )

        #
        # Export credentials.
        #
        cred_export_directory.mkdir(parents=True, exist_ok=True)
        cred_export_filename = cred_export_directory / "exported_creds.json"
        rr = run_atbu(
            pytester,
            tmp_path,
            "creds",
            "export",
            storage_specifier,
            cred_export_filename,
            log_base_name="cred-export",
        )
        assert rr.ret == ExitCode.OK

        #
        # Change encryption key to observe failure afterwards.
        #
        atbu_cfg = AtbuConfig.create_from_file(path=atbu_cfg_path)

        # TODO: review unlock/lock state, save state, dirty.
        cred_set = StorageDefCredentialSet(
            storage_def_name=storage_def_name.lower(),
            storage_def_dict=atbu_cfg.get_storage_def_dict(
                storage_def_name=storage_def_name.lower(),
                must_exist=True,
            ),
        )
        cred_set.populate()
        cred_set.unprotect()
        credential_orig = cred_set.get_encryption_desc_cred().credential
        assert credential_orig.is_private_key_ready
        credential_new = CredentialAesKey()
        credential_new.create_key()
        cred_set.get_encryption_desc_cred().credential = credential_new
        cred_set.protect()
        cred_set.save()

        #
        # Attempt restore without encryption key, observe failure.
        #
        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore2_dir_expect_fail,
            timeout=60 * 5,
            log_base_name="restore2-expect-fail",
        )
        assert rr.ret == ExitCode.TESTS_FAILED
        with DirInfo(restore2_dir_expect_fail) as restore2_dir_info:
            restore2_dir_info.gather_info(start_gathering_digests=True)
            assert len(restore2_dir_info.file_list) == 0
            assert directories_have_no_matches_by_path(
                di1=source_dir_info, di2=restore2_dir_info
            )

        #
        # Delete the storage definition configuration and credentials.
        #
        atbu_cfg = AtbuConfig.create_from_file(path=atbu_cfg_path)
        atbu_cfg.delete_storage_def(storage_def_name=storage_def_name)
        atbu_cfg.save_config_file()

        #
        # Attempt restore without the configuration, observe failure.
        #
        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore3_dir_expect_fail,
            timeout=60 * 5,
            log_base_name="restore3-expect-fail",
        )
        assert rr.ret == ExitCode.TESTS_FAILED
        with DirInfo(restore3_dir_expect_fail) as restore3_dir_info:
            restore3_dir_info.gather_info(start_gathering_digests=True)
            assert len(restore3_dir_info.file_list) == 0
            assert directories_have_no_matches_by_path(
                di1=source_dir_info, di2=restore3_dir_info
            )

        backup_info_dir = atbu_cfg.get_backup_info_dir()
        shutil.rmtree(backup_info_dir, ignore_errors=False, onerror=None)
        assert not os.path.exists(backup_info_dir)

        if os.path.isdir(storage_specifier):
            rr = run_atbu(
                pytester,
                tmp_path,
                "recover",
                storage_specifier,
                cred_export_filename,
                "--no-prompt",
                log_base_name="cred-import-and-recovery",
            )
        else:
            rr = run_atbu(
                pytester,
                tmp_path,
                "recover",
                cred_export_filename,
                "--no-prompt",
                log_base_name="cred-import-and-recovery",
            )
        assert rr.ret == ExitCode.OK

        #
        # Attempt restore after recovery, observe success.
        #
        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore4_dir_expect_success,
            timeout=60 * 5,
            log_base_name="restore4-expect-success",
        )
        assert rr.ret == ExitCode.OK
        with DirInfo(restore4_dir_expect_success) as restore_dir_info:
            restore_dir_info.gather_info(start_gathering_digests=True)
            assert len(source_dir_info.file_list) == expected_total_files
            assert len(restore_dir_info.file_list) == expected_total_files
            assert directories_match_entirely_by_order(
                di1=source_dir_info, di2=restore_dir_info
            )
        pass


def validate_backup_restore(
    pytester,
    tmp_path,
    source_directory,
    expected_total_files,
    storage_specifier,
    compression_type,
    backup_timeout,
    restore_timeout,
    initial_backup_stdin=None,
):
    restore1_dir_expect_success = tmp_path / "Restore1ExpectSuccess"
    restore2_dir_expect_success = tmp_path / "Restore2AfterIncBackupSuccess"
    restore3_dir_expect_success = tmp_path / "Restore3AfterIncPlucBackupSuccess"
    restore4_dir_expect_success = tmp_path / "Restore4AfterIncPlucDedupBackupSuccess"

    # pylint: disable=unused-variable
    with DirInfo(source_directory) as source_dir_info:
        source_dir_info.gather_info(start_gathering_digests=True)

        rr = run_atbu(
            pytester,
            tmp_path,
            "backup",
            "--full",
            source_directory,
            storage_specifier,
            "-z",
            compression_type,
            stdin=initial_backup_stdin,
            timeout=backup_timeout,
            log_base_name="backup1",
        )
        assert rr.ret == ExitCode.OK

        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore1_dir_expect_success,
            timeout=restore_timeout,
            log_base_name="restore1",
        )
        assert rr.ret == ExitCode.OK
        with DirInfo(restore1_dir_expect_success) as restore_dir_info:
            restore_dir_info.gather_info(start_gathering_digests=True)
            assert len(source_dir_info.file_list) == expected_total_files
            assert len(restore_dir_info.file_list) == expected_total_files
            assert directories_match_entirely_by_order(
                di1=source_dir_info, di2=restore_dir_info
            )

    total_files_added = create_test_data_directory_minimal(
        path_to_dir=source_directory,
        add_files_to_existing=True,
    )
    expected_total_files_b = expected_total_files + total_files_added

    with DirInfo(source_directory) as source_dir_info:
        source_dir_info.gather_info(start_gathering_digests=True)

        rr = run_atbu(
            pytester,
            tmp_path,
            "backup",
            "--incremental",
            source_directory,
            storage_specifier,
            "-z",
            compression_type,
            stdin=initial_backup_stdin,
            timeout=backup_timeout,
            log_base_name="backup2",
        )
        assert rr.ret == ExitCode.OK

        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore2_dir_expect_success,
            timeout=restore_timeout,
            log_base_name="restore2",
        )
        assert rr.ret == ExitCode.OK
        with DirInfo(restore2_dir_expect_success) as restore_dir_info:
            restore_dir_info.gather_info(start_gathering_digests=True)
            assert len(source_dir_info.file_list) == expected_total_files_b
            assert len(restore_dir_info.file_list) == expected_total_files_b
            assert directories_match_entirely_by_order(
                di1=source_dir_info, di2=restore_dir_info
            )

    # Simulating bitrot also simulates modified files w/touched
    # modified date that hides change without digest.
    num_bitrot = min(5, int(expected_total_files_b / 2))
    files_modified = induce_simulated_bitrot(
        path_to_dir=source_directory,
        num_files=num_bitrot,
    )

    total_files_added = create_test_data_directory_minimal(
        path_to_dir=source_directory,
        add_files_to_existing=True,
    )
    expected_total_files_c = expected_total_files_b + total_files_added

    rr = run_atbu(
        pytester,
        tmp_path,
        "backup",
        "--incremental-plus",
        source_directory,
        storage_specifier,
        "-z",
        compression_type,
        stdin=initial_backup_stdin,
        timeout=backup_timeout,
        log_base_name="backup3a-detect-bitrot",
    )
    assert rr.ret == ExitCode.TESTS_FAILED

    lsi = extract_backup_summary_from_log(
        output_lines=rr.outlines,
    )
    assert lsi.total_files == expected_total_files_c
    assert lsi.total_errors == num_bitrot
    assert lsi.total_bitrot_detection_warning == num_bitrot
    assert lsi.total_bitrot_detection_info == 0
    assert lsi.total_successful_backups == (total_files_added + num_bitrot)
    assert lsi.total_successful_backups == lsi.total_backup_operations
    assert lsi.total_unchanged_files == lsi.total_files - (
        total_files_added + num_bitrot
    )

    files_modified = induce_simulated_bitrot(
        path_to_dir=source_directory,
        num_files=num_bitrot,
    )

    with DirInfo(source_directory) as source_dir_info:
        source_dir_info.gather_info(start_gathering_digests=True)

        rr = run_atbu(
            pytester,
            tmp_path,
            "backup",
            "--incremental-plus",
            "--no-detect-bitrot",
            source_directory,
            storage_specifier,
            "-z",
            compression_type,
            stdin=initial_backup_stdin,
            timeout=backup_timeout,
            log_base_name="backup3b-no-detect-bitrot",
        )
        assert rr.ret == ExitCode.OK

        lsi = extract_backup_summary_from_log(
            output_lines=rr.outlines,
        )
        assert lsi.total_files == expected_total_files_c
        assert lsi.total_errors == 0
        assert lsi.total_bitrot_detection_warning == 0
        assert lsi.total_bitrot_detection_info == num_bitrot
        assert lsi.total_successful_backups == lsi.total_backup_operations
        assert lsi.total_successful_backups == num_bitrot
        assert (
            lsi.total_unchanged_files == lsi.total_files - lsi.total_backup_operations
        )

        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore3_dir_expect_success,
            timeout=restore_timeout,
            log_base_name="restore3",
        )
        assert rr.ret == ExitCode.OK
        with DirInfo(restore3_dir_expect_success) as restore_dir_info:
            restore_dir_info.gather_info(start_gathering_digests=True)
            assert len(source_dir_info.file_list) == expected_total_files_c
            assert len(restore_dir_info.file_list) == expected_total_files_c
            assert directories_match_entirely_by_order(
                di1=source_dir_info, di2=restore_dir_info
            )

    num_duplicates = int(expected_total_files_c / 2)
    num_duplicates_with_bitrot = int(min(5, num_duplicates / 4))
    orig_dup_path_list = duplicate_files(
        path_to_dir=source_directory,
        num_files=num_duplicates,
        num_bitrot=num_duplicates_with_bitrot,
    )
    expected_total_files_d = expected_total_files_c + len(orig_dup_path_list)

    with DirInfo(source_directory) as source_dir_info:
        source_dir_info.gather_info(start_gathering_digests=True)

        rr = run_atbu(
            pytester,
            tmp_path,
            "backup",
            "--incremental-plus",
            "--dedup",
            "digest",
            source_directory,
            storage_specifier,
            "-z",
            compression_type,
            stdin=initial_backup_stdin,
            timeout=backup_timeout,
            log_base_name="backup4",
        )
        # Duplicates with bitrot or the like have no
        # history as this is the first time being
        # backed up. Check results accordingly.
        assert rr.ret == ExitCode.OK

        lsi = extract_backup_summary_from_log(
            output_lines=rr.outlines,
        )
        assert lsi.total_files == expected_total_files_d
        assert lsi.total_errors == 0
        assert lsi.total_bitrot_detection_warning == 0
        assert lsi.total_bitrot_detection_info == 0
        assert lsi.total_successful_backups == lsi.total_backup_operations
        assert lsi.total_successful_backups == num_duplicates_with_bitrot
        assert lsi.total_unchanged_files == lsi.total_files - num_duplicates_with_bitrot

        rr = run_atbu(
            pytester,
            tmp_path,
            "restore",
            storage_specifier,
            "backup:last",
            "files:*",
            restore4_dir_expect_success,
            timeout=restore_timeout,
            log_base_name="restore4",
        )
        assert rr.ret == ExitCode.OK
        with DirInfo(restore4_dir_expect_success) as restore_dir_info:
            restore_dir_info.gather_info(start_gathering_digests=True)
            assert len(source_dir_info.file_list) == expected_total_files_d
            assert len(restore_dir_info.file_list) == expected_total_files_d
            assert directories_match_entirely_by_order(
                di1=source_dir_info, di2=restore_dir_info
            )

    pass


@dataclass
class SourceDirInfo:
    total_files: int
    dir_path: Path
    restore_path: Path


def validate_backup_restore_history(
    pytester,
    tmp_path,
    max_history,
    source_directory,
    expected_total_files,
    storage_specifier,
    compression_type,
    backup_timeout,
    restore_timeout,
    initial_backup_stdin=None,
):
    source_directory = Path(source_directory)
    test_backup_restore_dir_info: list[SourceDirInfo] = [
        SourceDirInfo(
            total_files=expected_total_files,
            dir_path=source_directory,
            restore_path=source_directory.with_name(
                name=source_directory.name + "-Restore"
            ),
        )
    ]
    last_br_info = test_backup_restore_dir_info[0]
    for i in range(1, max_history):
        new_dir_path = source_directory.with_name(name=source_directory.name + f"-{i}")
        new_restore_path = source_directory.with_name(
            name=source_directory.name + f"-{i}-Restore"
        )
        duplicate_tree(
            src_dir=last_br_info.dir_path,
            dst_dir=new_dir_path,
        )
        new_dir_total_files = create_test_data_directory_minimal_vary(
            path_to_dir=new_dir_path,
            add_files_to_existing=True,
        )
        last_br_info = SourceDirInfo(
            total_files=last_br_info.total_files + new_dir_total_files,
            dir_path=new_dir_path,
            restore_path=new_restore_path,
        )
        test_backup_restore_dir_info.append(last_br_info)

    for i, br_info in enumerate(test_backup_restore_dir_info):
        rr = run_atbu(
            pytester,
            tmp_path,
            "backup",
            "-f" if i == 0 else "-i",
            str(br_info.dir_path),
            storage_specifier,
            "-z",
            compression_type,
            stdin=initial_backup_stdin if i == 0 else None,
            timeout=backup_timeout,
            log_base_name=f"backup{i}",
        )
        assert rr.ret == ExitCode.OK

    rr = run_atbu(
        pytester,
        tmp_path,
        "list",
        storage_specifier,
        "backup:*",
        log_base_name=f"list-backups",
    )
    assert rr.ret == ExitCode.OK

    backup_names = extract_backup_names_from_log(output_lines=rr.outlines)
    assert len(backup_names) == len(test_backup_restore_dir_info)
    backup_names = backup_names[::-1]

    for i, br_info in enumerate(test_backup_restore_dir_info):
        backup_name = backup_names[i]
        with DirInfo(br_info.dir_path) as source_dir_info:
            source_dir_info.gather_info(start_gathering_digests=True)
            rr = run_atbu(
                pytester,
                tmp_path,
                "restore",
                storage_specifier,
                f"backup:{backup_name}",
                "files:*",
                br_info.restore_path,
                timeout=restore_timeout,
                log_base_name=f"restore{i}-{backup_name}",
            )
            assert rr.ret == ExitCode.OK
            with DirInfo(br_info.restore_path) as restore_dir_info:
                restore_dir_info.gather_info(start_gathering_digests=True)
                assert len(source_dir_info.file_list) == br_info.total_files
                assert len(restore_dir_info.file_list) == br_info.total_files
                assert directories_match_entirely_by_order(
                    di1=source_dir_info, di2=restore_dir_info
                )
    pass
