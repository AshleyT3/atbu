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
r"""Classes representing file information.
"""

from collections import defaultdict
from dataclasses import dataclass
import logging
import os
from datetime import datetime, timezone
import re
import configparser
from typing import Callable, Union

from atbu.mp_pipeline.mp_global import get_verbosity_level
from atbu.common.exception import (
    exc_to_string,
    AtbuException,
    FileChangedWhileCalculatingHash,
    InvalidStateError,
    StateChangeDisallowedError,
    AlreadyUsedError,
)
from atbu.common.hasher import (
    Hasher,
    HasherDefinitions,
)

from ..backup.exception import (
    PersistentFileInfoError,
    InvalidPersistentFileInfoError,
    PersistentFileInfoVersionMismatch,
)
from ..backup.constants import *
from ..backup.global_hasher import GlobalHasherDefinitions

CHANGE_DETECTION_TYPE_DATESIZE = "datesize"
CHANGE_DETECTION_TYPE_DIGEST = "digest"
CHANGE_DETECTION_TYPE_FORCE = "force"
CHANGE_DETECTION_CHOICES = [
    CHANGE_DETECTION_TYPE_DATESIZE,
    CHANGE_DETECTION_TYPE_DIGEST,
    CHANGE_DETECTION_TYPE_FORCE,
]


def has_atbu_extension(path):
    ext: str = os.path.splitext(path)[1]
    return ext.lower() in ATBU_SKIP_EXTENSIONS


class FileInformation:
    """Each instance represents information about a file."""

    FILE_READ_SIZE_5MB = 1024 * 1024 * 5

    def __init__(self, path: str):
        self._implicit_refresh_allowed = True
        self.path = path
        self.dirname = os.path.dirname(path)
        self.basename = os.path.basename(path)
        self.basename_no_ext, self.ext = os.path.splitext(self.basename)
        self._size_in_bytes = None
        self._modified_time_posix = None
        self._accessed_time_posix = None  # Retained to allow use of utime.
        self.digests = None

    def refresh(self):
        self.refresh_stat_info()
        self.refresh_digests(GlobalHasherDefinitions().create_hasher())

    @property
    def nc_path(self):
        return os.path.normcase(self.path)

    @property
    def size_in_bytes(self):
        if self._size_in_bytes is None:
            self.refresh_stat_info()
        return self._size_in_bytes

    @size_in_bytes.setter
    def size_in_bytes(self, value):
        self._size_in_bytes = value

    @property
    def modified_time_posix(self):
        if self._modified_time_posix is None:
            self.refresh_stat_info()
        return self._modified_time_posix

    @modified_time_posix.setter
    def modified_time_posix(self, v):
        self._modified_time_posix = v

    @property
    def accessed_time_posix(self):
        if self._accessed_time_posix is None:
            self.refresh_stat_info()
        return self._accessed_time_posix

    @accessed_time_posix.setter
    def accessed_time_posix(self, v):
        self._accessed_time_posix = v

    @property
    def implicit_refresh_allowed(self):
        return self._implicit_refresh_allowed

    @implicit_refresh_allowed.setter
    def implicit_refresh_allowed(self, value):
        self._implicit_refresh_allowed = value

    def calculate_hashes(self, hasher: Hasher = None, max_attempts=None) -> Hasher:
        if not self._implicit_refresh_allowed:
            raise StateChangeDisallowedError(
                f"Value should be set from persisted state, refresh disallowed."
            )
        if max_attempts is not None and max_attempts <= 0:
            raise ValueError(
                f"max_attempts must be None for forever, "
                f"or a positive number indicating max attempts."
            )
        if hasher is None:
            hasher = GlobalHasherDefinitions().create_hasher()
        while True:
            modified_time_before, size_in_bytes_before = self.refresh_stat_info()
            with open(self.path, "rb") as file:
                while True:
                    data = file.read(FileInformation.FILE_READ_SIZE_5MB)
                    if not data:
                        break
                    hasher.update_all(data)
            modified_time_after, size_in_bytes_after = self.refresh_stat_info()
            if (
                modified_time_before == modified_time_after
                and size_in_bytes_before == size_in_bytes_after
            ):
                # File did not change (from OS perspective).
                break
            if max_attempts is None:
                # try forever
                continue
            max_attempts -= 1
            if max_attempts <= 0:
                raise FileChangedWhileCalculatingHash(
                    f"The file changed while calculating hashes: {self.path}"
                )
        return hasher

    def refresh_stat_info(self) -> tuple[float, int]:
        if not self._implicit_refresh_allowed:
            raise StateChangeDisallowedError(
                f"Value should be set from persisted state, refresh disallowed."
            )
        sr: os.stat_result = os.stat(self.path)
        self._size_in_bytes = sr.st_size
        self._modified_time_posix = sr.st_mtime
        self._accessed_time_posix = sr.st_atime
        return self._modified_time_posix, self._size_in_bytes

    def refresh_digests(self, hasher: Hasher = None, max_attempts: int = None) -> dict:
        hasher = self.calculate_hashes(hasher=hasher, max_attempts=max_attempts)
        self.digests = hasher.get_hexdigests()
        return self.digests

    @property
    def has_primary_digest(self):
        """True if digest already generated, False if not."""
        return (
            self.digests is not None
            and self.digests.get(
                GlobalHasherDefinitions().get_primary_hashing_algo_name()
            )
            is not None
        )

    @property
    def primary_digest(self) -> str:
        if self.digests is None:
            self.refresh_digests()
        return self.digests[GlobalHasherDefinitions().get_primary_hashing_algo_name()]

    @primary_digest.setter
    def primary_digest(self, value):
        if self.digests is None:
            self.digests = {}
        self.digests[GlobalHasherDefinitions().get_primary_hashing_algo_name()] = value

    @property
    def primary_digest_algo_name(self) -> str:
        return GlobalHasherDefinitions().get_primary_hashing_algo_name()

    def _get_date_stamp_ISO8601_with_refresh(self, posix_timestamp: float, tz=None):
        if posix_timestamp is None:
            self.refresh_stat_info()
        return FileInformation.get_datetime_stamp_ISO8601(
            datetime.fromtimestamp(posix_timestamp, tz=tz)
        )

    @property
    def modified_date_stamp_ISO8601_local(self):
        return self._get_date_stamp_ISO8601_with_refresh(
            posix_timestamp=self._modified_time_posix
        )

    @property
    def modified_date_stamp_ISO8601_utc(self):
        return self._get_date_stamp_ISO8601_with_refresh(
            posix_timestamp=self._modified_time_posix, tz=timezone.utc
        )

    @property
    def accessed_date_stamp_ISO8601_local(self):
        return self._get_date_stamp_ISO8601_with_refresh(
            posix_timestamp=self._accessed_time_posix
        )

    @property
    def accessed_date_stamp_ISO8601_utc(self):
        return self._get_date_stamp_ISO8601_with_refresh(
            posix_timestamp=self._accessed_time_posix, tz=timezone.utc
        )

    @staticmethod
    def get_datetime_stamp_v01(dt):
        return dt.strftime("%Y/%m/%d-%H:%M:%S")

    @staticmethod
    def get_datetime_stamp_ISO8601(dt: datetime):
        return dt.isoformat(timespec="microseconds")

    @staticmethod
    def get_datetime_from_ISO8601(iso8601: str):
        return datetime.fromisoformat(iso8601)

    def to_serialization_dict(self) -> dict:
        d = {
            "_type": "FileInformation",
            "path": self.path,
            # The original POSIX timestamp returned by Python's stat.
            "lastmodified": self._modified_time_posix,
            "lastaccessed": self._accessed_time_posix,
            # The stamp rounds to microseconds (given datetime instances have
            # microsecond accuracy to whatever degree supported by the platform).
            "lastmodified_stamp": self.modified_date_stamp_ISO8601_utc,
            "size_in_bytes": self.size_in_bytes,
            "digests": self.digests,
        }
        return d

    def from_serialization_dict(self, d: dict):
        # By default, disallowed refresh of loaded persisted state.
        self._implicit_refresh_allowed = False
        self.path = d["path"]
        # Follwoing saves original POSIX stamp for potential usage in
        # debugging and/or later time-handling code mods.
        self._modified_time_posix = d["lastmodified"]
        self._accessed_time_posix = d["lastaccessed"]
        # This sets self._modified_time to "datetime microsecond"
        # truncated original.
        self.size_in_bytes = d["size_in_bytes"]
        self.digests = d["digests"]


class FileInformationPersistent(FileInformation):
    """Like FileInformation, instances of FileInformationPersistent
    represent information about a file, but are instances that represent
    file information as obtained from one of several mechanisms...

        Originally, the information is likely obtained from a file
        within a file system.

        The original information can be stored in per-file .atbu file
        information files, where it can be later retrieved for use in
        comparing with other files or even with its own current state.

        The original information can also be stored in a file information
        database (json db) where it can be compared with either another
        json db or a live file system.

    In all the above cases, once information is retrieved, whether from
    the file system, a json db, or a .atbu file information file, the
    information is stored in instances of FileInformationPersistent in
    a "firewalled" manner from the live OS information.

    Therefore, any testing of FileInformationPersistent should ensure that
    file information read from any other source is never polluted from live
    OS information until such time as someone calls a method on the instance
    (i.e., refresh_info_from_phys_file) to do so.

    With all that said, keep in mind quite simply that FileInformation and
    FileInformationPersistent are different. FileInformation deals with
    information just read from the file system (not info saved in a db or
    .atbu file), whereas FileInformationPersistent, aside from its initial
    sampling of information from the file system, never deals with live OS
    data until commanded to do so.
    """

    def __init__(
        self,
        path,
        info_current=None,
        info_history=None,
        is_loaded_from_db: bool = False,
    ):
        self.version = None  # added for persistence v2.
        self.is_loaded_from_db = is_loaded_from_db  # Not persisted.
        if info_current is None:
            info_current = {}
        if info_history is None:
            info_history = []
        super().__init__(path=path)
        self.config_basename = self.basename + ATBU_PERSISTENT_INFO_EXTENSION
        self.info_data_file_path = os.path.join(self.dirname, self.config_basename)
        self.info_current = info_current
        digest_from_current = info_current.get(
            GlobalHasherDefinitions().get_primary_hashing_algo_name()
        )
        if digest_from_current:
            self.primary_digest = digest_from_current
        self.info_history = info_history
        # Not yet persisted but updated via update_stat_info
        # for comparison or usage generally before such updates.
        self.cached_digests = None
        self.cached_statinfo = None

    @property
    def size_in_bytes_cached(self) -> int:
        """Return the current size in bytes."""
        if not self.has_cached_size_in_bytes:
            raise KeyError("'sizeinbytes' not cached yet, refresh required first.")
        return int(self.cached_statinfo["sizeinbytes"])

    @property
    def has_cached_size_in_bytes(self) -> bool:
        return (
            self.cached_statinfo is not None and "sizeinbytes" in self.cached_statinfo
        )

    @property
    def size_in_bytes(self):
        """Return the current size in bytes."""
        if "sizeinbytes" not in self.info_current:
            raise KeyError("SizeInBytes not saved or loaded to/from file information.")
        return int(self.info_current["sizeinbytes"])

    @property
    def modified_date_stamp_local_cached(self) -> str:
        if "lastmodified" not in self.cached_statinfo:
            raise KeyError("lastmodified not cached yet, refresh required first.")
        return self._get_date_stamp_ISO8601_with_refresh(
            posix_timestamp=float(self.cached_statinfo["lastmodified"]),
        )

    @property
    def has_cached_modified_date(self) -> bool:
        return (
            self.cached_statinfo is not None and "lastmodified" in self.cached_statinfo
        )

    @property
    def modified_date_stamp_local(self) -> str:
        if "lastmodified" not in self.info_current:
            raise KeyError("lastmodified not cached yet, refresh required first.")
        return self._get_date_stamp_ISO8601_with_refresh(
            posix_timestamp=float(self.info_current["lastmodified"]),
        )

    def get_digest_cached(self, hashing_algo_name=None) -> str:
        if hashing_algo_name is None:
            hashing_algo_name = (
                GlobalHasherDefinitions().get_primary_hashing_algo_name()
            )
        return self.cached_digests.get(hashing_algo_name.lower())

    def has_cached_digest(self, hashing_algo_name=None) -> bool:
        if hashing_algo_name is None:
            hashing_algo_name = (
                GlobalHasherDefinitions().get_primary_hashing_algo_name()
            )
        return (
            self.cached_digests is not None and hashing_algo_name in self.cached_digests
        )

    def get_digest(self, hashing_algo_name=None) -> str:
        if hashing_algo_name is None:
            hashing_algo_name = (
                GlobalHasherDefinitions().get_primary_hashing_algo_name()
            )
        return self.info_current.get(hashing_algo_name.lower())

    def is_modified_date_or_size_changed(self):
        if len(self.info_current) == 0:
            return True
        if "lastmodified" not in self.info_current:
            return True
        if "sizeinbytes" not in self.info_current:
            return True
        self.refresh_stat_info()
        if float(self.info_current["lastmodified"]) != float(
            self.cached_statinfo["lastmodified"]
        ):
            return True
        if int(self.info_current["sizeinbytes"]) != int(
            self.cached_statinfo["sizeinbytes"]
        ):
            return True
        return False

    def is_primary_digest_changed(self, hasher: Hasher) -> bool:
        if len(self.info_current) == 0:
            return True
        primary_hasher_name = hasher.get_primary_hashing_algo_name()
        if primary_hasher_name not in self.info_current:
            return True
        self.refresh_digests(hasher)
        if (
            self.info_current[primary_hasher_name]
            != self.cached_digests[primary_hasher_name]
        ):
            return True
        return False

    def refresh_info_from_phys_file(self, hashers):
        if self.cached_digests is None:
            self.refresh_digests(hashers)
        if self.cached_statinfo is None:
            self.refresh_stat_info()
        info_new = self.cached_statinfo | self.cached_digests
        if self.info_current == info_new:
            return
        self.info_current = info_new
        self.info_history.append(info_new)

    def clear_cached_info(self):
        self.cached_digests = None
        self.cached_statinfo = None

    def info_data_file_exists(self):
        return os.path.exists(self.info_data_file_path)

    def _create_config_parser(self):
        return configparser.ConfigParser(interpolation=None)

    def read_info_data_file(self):
        if not self.info_data_file_exists():
            raise FileNotFoundError(
                f"Config does not exist: {self.info_data_file_path}"
            )
        self.info_current = {}
        self.info_history = []
        cp = self._create_config_parser()
        cp.read(self.info_data_file_path)
        if "MAIN" not in cp.sections():
            raise InvalidPersistentFileInfoError(
                f"The persistent info does not have "
                f"the expected MAIN section: "
                f"{self.info_data_file_path}"
            )
        if "INFO.CURRENT" in cp.sections():
            self.info_current = dict(cp["INFO.CURRENT"])
        re_info_history = re.compile(r"^INFO.\d{4}$")
        history_sections = list(sorted(filter(re_info_history.match, cp.sections())))
        for history_section in history_sections:
            self.info_history.append(dict(cp[history_section]))
        self.version = dict(cp["MAIN"])["version"]
        if self.version != "2":
            raise PersistentFileInfoVersionMismatch(
                f"The persistent info file version is mismatched: "
                f"v={self.version} {self.info_data_file_path}"
            )

    def write_info_data_file(self):
        cp = self._create_config_parser()
        cp["MAIN"] = {
            "Version": ATBU_PERSISTENT_INFO_VERSION_STRING,
            "BaseName": self.basename,
        }
        cp["INFO.CURRENT"] = self.info_current
        for index, info_item in enumerate(self.info_history):
            cp[f"INFO.{index:04d}"] = info_item
        with open(self.info_data_file_path, "w", encoding="utf-8") as cf:
            cp.write(cf)

    def update_info_data_file_to_latest_version(self, hashers):
        # There has been only version 1 and 2, current being 2.
        # Following logic is therefore to upgrade from 1 to 2.
        # Modify accordingly for subsequent upgrades.

        if self.version != "0.1":
            # Caller should have attempted read_info_data_file
            # which sets version.
            raise PersistentFileInfoError(
                f"update_info_data_file_to_latest_version cannot "
                f"be called for anything but version 1.0."
            )

        self.clear_cached_info()
        self.refresh_stat_info()

        stamp = FileInformation.get_datetime_stamp_v01(
            datetime.fromtimestamp(self._modified_time_posix, tz=timezone.utc)
        )

        is_changed = (
            len(self.info_current) == 0
            or "lastmodified" not in self.info_current
            or "sizeinbytes" not in self.info_current
            or self.info_current["lastmodified"] != stamp
            or int(self.info_current["sizeinbytes"])
            != int(self.cached_statinfo["sizeinbytes"])
        )

        if is_changed:
            # Perform full update including digests if either of
            # date/size has changed.
            self.refresh_info_from_phys_file(hashers)
            self.write_info_data_file()
            self.read_info_data_file()
            return

        # Otherwise, perform a quicker upgrade of simply stat info.
        # Merge in updated state info while retaining already calculated digests.
        self.info_current = self.info_current | self.cached_statinfo
        self.info_history.append(self.info_current)
        self.write_info_data_file()
        self.read_info_data_file()

    def refresh_stat_info(self) -> tuple[float, int]:
        mod_time, size = super().refresh_stat_info()
        self.cached_statinfo = {
            "sizeinbytes": self._size_in_bytes,
            "lastmodified": self.modified_time_posix,
            "lastmodified_stamp": self.modified_date_stamp_ISO8601_utc,
        }
        return mod_time, size

    def refresh_digests(self, hasher: Hasher = None, max_attempts: int = None):
        # For the purposes of this class, if the cached digests
        # are updated, the cached dict date/size info should be
        # matching that which existed which hashes sampled.
        self.refresh_stat_info()
        r = super().refresh_digests(hasher=hasher, max_attempts=max_attempts)
        # Digests are already in dict and therefore config
        # file format, just copy them to our digest info cache.
        # This is unlike _update_cached_stat_info converts to dict.
        self.cached_digests = self.digests
        return r

    def __str__(self) -> str:
        s = []
        s.append(f"path={self.path}")
        s.append(f"config_path={self.info_data_file_path}")
        s.append("info_current...")
        if len(self.info_current) > 0:
            for k, v in self.info_current.items():
                s.append(f"  {k}={v}")
        else:
            s.append("  Empty")
        s.append("info_history...")
        if len(self.info_history) > 0:
            for index, item in enumerate(self.info_history):
                s.append(f"  INFO.{index:04d}:")
                for k, v in item.items():
                    s.append(f"    {k}={v}")
        else:
            s.append("  Empty")
        return "\n".join(s)

    def to_serialization_dict(self) -> dict:
        return {
            "_type": "FileInformationPersistent",
            "path": self.path,
            "info_current": self.info_current,
            "info_history": self.info_history,
        }


@dataclass
class SneakyCorruptionPotential:
    file_info: FileInformationPersistent
    old_size_in_bytes: int
    cur_size_in_bytes: int
    old_modified_time: str
    cur_modified_time: str
    old_digest: str
    cur_digest: str


class LocationFileInfoUpdater:
    def __init__(
        self,
        file_info_list: list[FileInformationPersistent],
        update_stale: bool,
        change_detection_type: str,
        per_file_persistence: bool = True,
        whatif: bool = False,
        hasher_defs: HasherDefinitions = None,
    ):
        if not isinstance(file_info_list, list):
            raise ValueError(
                "file_info_list must be an Interable of FileInformationPersistent instances."
            )
        if hasher_defs is None:
            hasher_defs = GlobalHasherDefinitions()
        if not change_detection_type:
            raise ValueError(
                "change_detection_type must be one of datesize, digest, force."
            )
        self.whatif = whatif
        self.whatif_str = "(--whatif) " if self.whatif else ""
        self.file_info_list = file_info_list
        self.hasher_defs = hasher_defs
        self.update_stale = update_stale
        self.change_detection_type = change_detection_type
        self.per_file_persistence = per_file_persistence
        self.primary_hasher_name = hasher_defs.get_primary_hashing_algo_name()
        self.skipped_files: list[tuple[FileInformationPersistent, str]] = []
        # Counters
        self.total_files = 0
        self.total_file_info_created = 0
        self.total_file_info_updated = 0
        self.total_files_stale_info_skipped = 0
        self.total_files_no_update_required = 0
        self.total_files_without_primary_digest = 0
        self.sneaky_corruption_potentials: list[SneakyCorruptionPotential] = []
        self.is_used = False

    def _process_file_info(self, file_info: FileInformationPersistent):
        self.total_files += 1
        some_updating_occurred = False
        info_data_file_existed = False
        try:
            # If a file info came from a DB file, it effectively
            # represents a file info read from disk.
            if not file_info.is_loaded_from_db:
                if self.per_file_persistence:
                    file_info.read_info_data_file()
                else:
                    # This is a "new file" for a DB-only scan because
                    # is_loaded_from_db==False and per_file_persistence==False.
                    # Note, combo scans, scans for both per-dir and per-file for
                    # a location, will perform a per-file scan whose results
                    # feed the DB, but not so in this case.
                    raise FileNotFoundError(
                        f"New DB item FileNotFoundError: {file_info.path}"
                    )
            info_data_file_existed = True
        except FileNotFoundError:
            if not self.update_stale:
                logging.warning(f"File info does not exist, skipping {file_info.path}.")
                self.total_files_stale_info_skipped += 1
                self.skipped_files.append(
                    (file_info, f"The {ATBU_PERSISTENT_INFO_EXTENSION} info is missing")
                )
                return
            logging.info(f"{self.whatif_str}Creating info for {file_info.path}...")
            if not self.whatif:
                file_info.refresh_info_from_phys_file(self.hasher_defs.create_hasher())
                if self.per_file_persistence:
                    file_info.write_info_data_file()
                self.total_file_info_created += 1
            some_updating_occurred = True
        except PersistentFileInfoVersionMismatch as ex:
            if not self.update_stale:
                raise AtbuException(
                    f"Cannot upgrade persistent file info because "
                    f"option to update not specified. {exc_to_string(ex)}"
                ).with_traceback(ex.__traceback__) from ex
            logging.info(f"{self.whatif_str}Creating info for {file_info.path}...")
            if not self.whatif:
                file_info.update_info_data_file_to_latest_version(
                    self.hasher_defs.create_hasher()
                )
                self.total_file_info_updated += 1
            some_updating_occurred = True
        primary_digest = file_info.get_digest(self.primary_hasher_name)
        if primary_digest is None:
            self.total_files_without_primary_digest += 1
            self.skipped_files.append(
                (file_info, f"No '{self.primary_hasher_name}' primary digest found")
            )
            logging.warning(
                f"No '{self.primary_hasher_name}' primary digest found, skipping {file_info.path}"
            )
            return
        is_changed = False
        logging.info(f"Checking for changes to {file_info.path}...")
        if self.change_detection_type == CHANGE_DETECTION_TYPE_DATESIZE:
            is_changed = file_info.is_modified_date_or_size_changed()
        elif self.change_detection_type == CHANGE_DETECTION_TYPE_DIGEST:
            is_changed = file_info.is_primary_digest_changed(
                self.hasher_defs.create_hasher()
            )
        elif self.change_detection_type == CHANGE_DETECTION_TYPE_FORCE:
            is_changed = True
        else:
            raise InvalidStateError(
                f"Unexpected change_detection_type={self.change_detection_type}."
            )
        if is_changed:
            logging.info(f"Change detected: {file_info.path}:")
        elif get_verbosity_level() > 0:
            logging.info(f"Path: {file_info.path}:")
        if is_changed or get_verbosity_level() > 0:
            if file_info.has_cached_size_in_bytes:
                logging.info(f"    cur size={file_info.size_in_bytes_cached}")
                logging.info(f"    old size={file_info.size_in_bytes}")
            elif self.change_detection_type != CHANGE_DETECTION_TYPE_FORCE:
                logging.info(f"    (size not checked)")
            if file_info.has_cached_modified_date:
                logging.info(
                    f"    cur time={file_info.modified_date_stamp_local_cached}"
                )
                logging.info(f"    old time={file_info.modified_date_stamp_local}")
            elif self.change_detection_type != CHANGE_DETECTION_TYPE_FORCE:
                logging.info(f"    (time not checked)")
            if file_info.has_cached_digest():
                logging.info(f"    cur digest={file_info.get_digest_cached()}")
                logging.info(f"    old digest={file_info.get_digest()}")
            elif self.change_detection_type != CHANGE_DETECTION_TYPE_FORCE:
                logging.info(f"    (digest not checked)")
            if (
                file_info.has_cached_size_in_bytes
                and file_info.has_cached_modified_date
                and file_info.has_cached_digest()
            ):
                if (
                    file_info.size_in_bytes_cached == file_info.size_in_bytes
                    and file_info.modified_date_stamp_local_cached
                    == file_info.modified_date_stamp_local
                    and file_info.get_digest_cached() != file_info.get_digest()
                ):
                    logging.warning(
                        f"WARNING: Potential bitrot or other sneaky corruption: {file_info.path}"
                    )
                    self.sneaky_corruption_potentials.append(
                        SneakyCorruptionPotential(
                            file_info=file_info,
                            old_size_in_bytes=file_info.size_in_bytes,
                            cur_size_in_bytes=file_info.size_in_bytes_cached,
                            old_modified_time=file_info.modified_date_stamp_local,
                            cur_modified_time=file_info.modified_date_stamp_local_cached,
                            old_digest=file_info.get_digest(),
                            cur_digest=file_info.get_digest_cached(),
                        )
                    )
        if is_changed:
            if not self.update_stale:
                self.total_files_stale_info_skipped += 1
                self.skipped_files.append(
                    (file_info, f"The {ATBU_PERSISTENT_INFO_EXTENSION} info is stale")
                )
                logging.warning(
                    f"File has changed, file info stale, skipping {file_info.path}."
                )
                return
            logging.info(f"{self.whatif_str}Updating file info for {file_info.path}...")
            if not self.whatif:
                file_info.refresh_info_from_phys_file(self.hasher_defs.create_hasher())
                primary_digest = file_info.get_digest(self.primary_hasher_name)
                if self.per_file_persistence:
                    file_info.write_info_data_file()
            some_updating_occurred = True
            if file_info.is_modified_date_or_size_changed() and not self.whatif:
                self.skipped_files.append(
                    (
                        file_info,
                        f"The {ATBU_PERSISTENT_INFO_EXTENSION} file info "
                        f"remains stale after update attempt",
                    )
                )
                self.total_files_stale_info_skipped += 1
                logging.warning(
                    f"The {ATBU_PERSISTENT_INFO_EXTENSION} file info remains "
                    f"stale after update attempt, skipping {file_info.path}."
                )
                return
            self.total_file_info_updated += 1
        if not some_updating_occurred:
            self.total_files_no_update_required += 1
        if some_updating_occurred:
            added_changed_str = "updated" if info_data_file_existed else "added"
            if self.per_file_persistence:
                logging.info(
                    f"The {ATBU_PERSISTENT_INFO_EXTENSION} file info was {added_changed_str}: "
                    f"path={file_info.path} "
                    f"{file_info.primary_digest_algo_name}={file_info.primary_digest}"
                )
                logging.debug(
                    f"The {ATBU_PERSISTENT_INFO_EXTENSION} file info was "
                    f"{added_changed_str}: {file_info}"
                )
            else:
                logging.info(
                    f"The file info was {added_changed_str}: "
                    f"path={file_info.path} "
                    f"{file_info.primary_digest_algo_name}={file_info.primary_digest}"
                )
                logging.debug(f"The file info was {added_changed_str}: {file_info}")
        else:
            if self.per_file_persistence:
                logging.info(
                    f"The {ATBU_PERSISTENT_INFO_EXTENSION} file info was up to date: "
                    f"path={file_info.path} "
                    f"{file_info.primary_digest_algo_name}={file_info.primary_digest}"
                )
                logging.debug(
                    f"The {ATBU_PERSISTENT_INFO_EXTENSION} file info was up to date: {file_info}"
                )
            else:
                logging.info(
                    f"The file info was up to date: "
                    f"path={file_info.path} "
                    f"{file_info.primary_digest_algo_name}={file_info.primary_digest}"
                )
                logging.debug(f"The file info was up to date: {file_info}")

        # logging.info(f"Have file w/good info for {file_info.path}")
        return

    def update(self):
        if self.is_used:
            raise AlreadyUsedError(f"This instance already used to update.")
        self.is_used = True
        for file_info in self.file_info_list:
            self._process_file_info(file_info)


def get_loc_files_as_ncloc_to_object(
    locations: Union[str, list[str]],
    include_pattern: re.Pattern = None,
    exclude_atbu: bool = True,
    factory: Callable[[str, str], object] = lambda loc_root, file_path: str(file_path),
) -> dict[str, list[str]]:
    """Get each location's files paired with the root location leading to each discovered file.
    This returns a dictionary of location to files for each such location. For each file,
    the factory is called as follows...

        factory(location_root_path, path_to_file)

    ...where the factory should return an instance of the desired class.

    The default factory creates a string of the path to the file.
    """
    if isinstance(locations, str):
        locations = [str(locations)]
    results: dict = defaultdict(list)
    for location in locations:
        for root, dirs, files in os.walk(location):  # pylint: disable=unused-variable
            for file in files:
                # Skip .atbu extension files. We get to the info via non-atbu files.
                if exclude_atbu and has_atbu_extension(file):
                    continue
                if include_pattern and not include_pattern.match(file):
                    continue
                o = factory(location, os.path.join(root, file))
                if o:
                    results[os.path.normcase(location)].append(o)
    return results


def get_loc_fileobj_list(
    locations: Union[str, list[str]],
    include_pattern: re.Pattern = None,
    exclude_atbu: bool = True,
    factory: Callable[[str, str], object] = lambda loc_root, file_path: str(file_path),
) -> list[str]:
    """Get all files as an object, which is by default the file's path."""
    dict_ncloc_to_file_list = get_loc_files_as_ncloc_to_object(
        locations=locations,
        include_pattern=include_pattern,
        exclude_atbu=exclude_atbu,
        factory=factory,
    )
    file_list = [v for l in dict_ncloc_to_file_list.values() for v in l]
    return file_list


def get_loc_persistent_file_info(
    locations: Union[str, list[str]],
    include_pattern: re.Pattern = None,
) -> list[FileInformationPersistent]:
    file_info_persistent_list: list[FileInformationPersistent] = get_loc_fileobj_list(
        locations=locations,
        include_pattern=include_pattern,
        exclude_atbu=True,
        factory=lambda loc_root, file_path: FileInformationPersistent(path=file_path),
    )
    return file_info_persistent_list
