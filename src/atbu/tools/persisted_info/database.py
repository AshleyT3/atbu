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
r"""Persistent file information database-related functionality allows
gathering of persistent file information, placing it into a single
json "database" file.

There was a second revision of persistent info functionality incorporated
into ATBU so you may see redundancy or superfluous constructs within.
"""

from dataclasses import dataclass
import os
import json
import logging
from collections import defaultdict

from atbu.common.hasher import HasherDefinitions

from ..backup.global_hasher import GlobalHasherDefinitions
from ..backup.exception import *
from ..backup.constants import *
from .file_info import (
    FileInformationPersistent,
    get_loc_persistent_file_info,
    LocationFileInfoUpdater,
)

class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, FileInformationPersistent):
            return o.to_serialization_dict()
        return json.JSONEncoder.default(self, o)


class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):  # pylint: disable=method-hidden,no-self-use
        if "_type" not in obj:
            return obj
        object_type = obj["_type"]
        if object_type == "FileInformationPersistent":
            return FileInformationPersistent(
                path=obj["path"],
                info_current=obj["info_current"],
                info_history=obj["info_history"],
                is_loaded_from_db=True,
            )
        elif (
            object_type == "FileInformation"
        ):  # FileInformationPersistent used to be FileInformation (when used w/.atbu files)
            return FileInformationPersistent(
                path=obj["path"],
                info_current=obj["info_current"],
                info_history=obj["info_history"],
                is_loaded_from_db=True,
            )
        return obj


def get_location_info_from_database(
    database_json_path,
) -> defaultdict[str, list[FileInformationPersistent]]:
    with open(database_json_path, "r", encoding="utf-8") as database_file:
        return json.load(database_file, cls=CustomDecoder)


def file_info_list_to_digest_dict(
    file_info_list: list[FileInformationPersistent],
):
    digest_dict: defaultdict[str, list[FileInformationPersistent]] = defaultdict(
        list[FileInformationPersistent]
    )
    for file_info in file_info_list:
        digest_dict[file_info.primary_digest].append(file_info)
    return digest_dict


def file_info_list_to_ncpath_dict(
    file_info_list: list[FileInformationPersistent],
) -> dict[FileInformationPersistent]:
    ncpath_dict: defaultdict[str, FileInformationPersistent] = {}
    for file_info in file_info_list:
        fi = ncpath_dict.get(file_info.nc_path)
        if fi:
            raise InvalidStateError(
                f"Expecting only one file info per path: path={fi.path}"
            )
        ncpath_dict[file_info.nc_path] = file_info
    return ncpath_dict


def save_database_from_dict_file_info(
    dict_digest_to_file_info_list: defaultdict[str, list[FileInformationPersistent]],
    database_path,
):
    with open(database_path, "w", encoding="utf-8") as database_file:
        database_file.write(
            json.dumps(dict_digest_to_file_info_list, cls=CustomEncoder, indent=4)
        )


def save_database_from_file_info_list(
    file_info_list: list[FileInformationPersistent],
    database_path,
    hasher_defs: HasherDefinitions = None,
):
    if not hasher_defs:
        hasher_defs = GlobalHasherDefinitions()
    digest_dict = file_info_list_to_digest_dict(
        file_info_list=file_info_list,
    )
    save_database_from_dict_file_info(
        dict_digest_to_file_info_list=digest_dict, database_path=database_path
    )


class FileInformationDatabase:
    def __init__(self, source_path: str, persist_type: ATBU_PERSIST_TYPE_HINT) -> None:
        if not os.path.exists(source_path):
            raise InvalidFunctionArgument(
                f"Source path must a be directory but got '{source_path}'."
            )
        self.source_path = os.path.abspath(source_path)
        # If is_source_path_explicit_json_db_file==True means .json is user-created
        # and could pertain to one or more directories not currently online.
        self.is_source_path_explicit_json_db_file = os.path.isfile(self.source_path)
        self.persist_type = persist_type
        if self.is_source_path_explicit_json_db_file:
            self.db_filename = self.source_path
        else:
            self.db_filename = os.path.join(
                self.source_path, ATBU_DEFAULT_PERSISTENT_DB_FILENAME
            )
        self._file_info_list: list[FileInformationPersistent] = None
        self.updater: LocationFileInfoUpdater = None

    def get_file_info(self) -> list[FileInformationPersistent]:
        if self._file_info_list is None:
            raise InvalidStateError(
                f"_file_info_list is None. You must first either load or update the DB."
            )
        return self._file_info_list

    def get_dict_digest_to_fi(self):
        return file_info_list_to_digest_dict(file_info_list=self.get_file_info())

    def get_dict_ncpath_to_fi(self):
        return file_info_list_to_ncpath_dict(file_info_list=self.get_file_info())

    def _get_source_path_file_info_list(self):
        return get_loc_persistent_file_info(locations=self.source_path)

    def _load_per_file_info(self) -> None:
        if self.persist_type != ATBU_PERSIST_TYPE_PER_FILE:
            raise InvalidFunctionArgument(
                f"Expected persist_type={ATBU_PERSIST_TYPE_PER_FILE} but got {self.persist_type}"
            )
        self._file_info_list = self._get_source_path_file_info_list()

    def _load_per_dir_info(self) -> None:
        """Load the .json DB file. Two types of .json DB files based on
        how they were created/used. An user-created DB is created with
        save-db and is not tied to a specific directory, can contain
        files from one or more directories (up to user). The other
        type of DB is that created by update-digests for per-dir cases,
        where it maintains a DB of files within that directory structure.
        This method will load either type and the result is a flat list
        of file information in self._file_info_list.
        """
        if self.persist_type != ATBU_PERSIST_TYPE_PER_DIR:
            raise InvalidStateError(
                f"Expected persist_type={ATBU_PERSIST_TYPE_PER_DIR} but got {self.persist_type}"
            )

        if self.db_filename is None:
            raise InvalidStateError(
                f"db_filename is None, expected db_filename to be a .json db filename."
            )

        # Load file information from the DB file.
        # The info from DB contains path, digests,
        # modified date/time, size, etc.
        digest_to_fi_list = {}
        if os.path.exists(self.db_filename):
            digest_to_fi_list = get_location_info_from_database(
                database_json_path=self.db_filename
            )
        # Flatten to list of file info.
        self._file_info_list = [fi for l in digest_to_fi_list.values() for fi in l]

        # Disallow refresh of file information that comes from
        # an explicitly specified .json DB. This will cause
        # an exception if there's a code logic breaking the
        # assumption we do not expect files to be present
        # with an explicitly specified database.
        if self.is_source_path_explicit_json_db_file:
            for fi in self._file_info_list:
                fi.implicit_refresh_allowed = False

        # If user specifies explicit .json db as a location,
        # the user expects the db to be used as is with the need
        # for files to be present (user captured db earlier, perhaps,
        # before a drive was disconnected). Therefore, skip the
        # following which assumes files exist on the system.
        if not self.is_source_path_explicit_json_db_file:
            # Remove file info for files that no longer exist.
            # Or, in the case of a moved folder, remove info
            # pertaining to the old location.
            nc_source_path = os.path.normcase(self.source_path)
            self._file_info_list = list(
                filter(
                    lambda fi: os.path.isfile(fi.path)
                    and fi.nc_path.startswith(nc_source_path),
                    self._file_info_list,
                )
            )

            #
            # self._file_info_list is now a file info list of files
            # that both exist and are under self.source_path.
            #

            # Index self._file_info_list by path which will be used
            # to find out what file information is missing.
            db_path_to_file_info: dict = {fi.nc_path: fi for fi in self._file_info_list}

            # Get current file system file info. This only gets
            # a bare file info without digest/stat (because they
            # are not updated yet as DB is before being saved).
            fs_file_info_list = self._get_source_path_file_info_list()

            # Index new paths into the self._file_info_list DB info.
            for fi in fs_file_info_list:
                # If not in DB, add to DB.
                if not db_path_to_file_info.get(fi.nc_path):
                    db_path_to_file_info[fi.nc_path] = fi

            self._file_info_list = list(db_path_to_file_info.values())

    def load(self):
        """This loads existing data. TBD relationship with _get_source_path_file_info
        et al which scan files for both persist_types (in prep of updates etc.)
        """
        if self.persist_type == ATBU_PERSIST_TYPE_PER_FILE:
            self._load_per_file_info()
        elif self.persist_type == ATBU_PERSIST_TYPE_PER_DIR:
            self._load_per_dir_info()
        else:
            raise InvalidFunctionArgument(
                f"Unexpected persist_type={self.persist_type}"
            )

    def update(
        self,
        change_detection_type: str,
        update_stale: bool,
        whatif: bool,
    ) -> LocationFileInfoUpdater:
        self.load()
        # Show progress in sorted file path order.
        self._file_info_list.sort(key=lambda fi: fi.nc_path)
        self.updater = LocationFileInfoUpdater(
            file_info_list=self._file_info_list,
            update_stale=update_stale,
            change_detection_type=change_detection_type,
            per_file_persistence=not self.persist_type == ATBU_PERSIST_TYPE_PER_DIR,
            whatif=whatif,
        )
        # Do not update for explicitly specified .json
        # file DBs because files are not necessarily online.
        if not self.is_source_path_explicit_json_db_file:
            self.updater.update()
        return self.updater

    def update_from(self, other_db):
        self._file_info_list = list(other_db.get_file_info())
        # If this instance is a 'per-dir' DB, save the DB.
        # There is no saving to perform for 'per-file' since
        # per-file persistence updates as part of scanning/updating
        # the directories, likely before this update_from is called.
        if self.persist_type == ATBU_PERSIST_TYPE_PER_DIR:
            self.save_db()

    def save_db(self):
        save_database_from_file_info_list(
            database_path=self.db_filename,
            file_info_list=self._file_info_list,
        )


class FileInformationDatabaseCollection:
    def __init__(self, source_path: str, persist_types: list[str]) -> None:
        if not os.path.exists(source_path):
            raise InvalidFunctionArgument(
                f"Source path must a be directory but got '{source_path}'."
            )
        self.source_path = os.path.abspath(source_path)
        self.databases = {}
        for pt in persist_types:
            if pt not in ATBU_PERSIST_TYPES:
                raise InvalidFunctionArgument(
                    f"Expected a valid persist type '{ATBU_PERSIST_TYPES}' but got '{pt}'."
                )
            if self.databases.get(pt):
                raise InvalidFunctionArgument(
                    f"Only one of each persist type is allowed but got more than one of '{pt}'."
                )
            self.databases[pt] = FileInformationDatabase(
                persist_type=pt, source_path=self.source_path
            )

    @property
    def has_per_file_persistence(self):
        for pt in self.databases:
            if pt == ATBU_PERSIST_TYPE_PER_FILE:
                return True
        return False

    def get_combined_db_file_info(self):
        combined_info: dict[str, FileInformationPersistent] = {}
        db: FileInformationDatabase
        for k in [ATBU_PERSIST_TYPE_PER_FILE, ATBU_PERSIST_TYPE_PER_DIR]:
            db = self.databases.get(k)
            if not db:
                continue
            fi_list = db.get_file_info()
            for fi in fi_list:
                if not combined_info.get(fi.nc_path):
                    combined_info[fi.nc_path] = fi
        return combined_info.values()

    def get_dict_nc_path_to_fi(self):
        # pylint: disable=unused-variable
        (
            primary_update_db,
            other_db,
        ) = self._get_primary_other_db()  # pylint: disable=unused-variable
        return primary_update_db.get_dict_ncpath_to_fi()

    def get_dict_digest_to_fi(self):
        # pylint: disable=unused-variable
        (
            primary_update_db,
            other_db,
        ) = self._get_primary_other_db()  # pylint: disable=unused-variable
        return primary_update_db.get_dict_digest_to_fi()

    def _get_primary_other_db(self):
        primary_update_db: FileInformationDatabase = self.databases.get(
            ATBU_PERSIST_TYPE_PER_FILE
        )
        other_db: FileInformationDatabase = self.databases.get(
            ATBU_PERSIST_TYPE_PER_DIR
        )
        if not primary_update_db:
            primary_update_db = self.databases.get(ATBU_PERSIST_TYPE_PER_DIR)
            other_db = None
        if primary_update_db is None:
            raise InvalidFunctionArgument(
                f"Cannot determine the primary update db. DBs={self.databases.keys()}"
            )
        return primary_update_db, other_db

    def load(self):
        primary_update_db, other_db = self._get_primary_other_db()
        if primary_update_db is not None:
            primary_update_db.load()
        if other_db is not None:
            other_db.load()

    def update(
        self,
        change_detection_type: str,
        update_stale: bool,
        whatif: bool,
    ) -> LocationFileInfoUpdater:
        """Update the databases if needed. Returns the updater used for
        access to any stats.
        """
        primary_update_db, other_db = self._get_primary_other_db()
        updater = primary_update_db.update(
            change_detection_type=change_detection_type,
            update_stale=update_stale,
            whatif=whatif,
        )
        if other_db is None:
            # There is no other db, just primary. If primary is per-file it
            # is implicitly already persisted given the update above. If it
            # is a per-dir, it must be saved after the update.
            # Save the per-dir db.
            if (
                primary_update_db.persist_type == ATBU_PERSIST_TYPE_PER_DIR
                and not primary_update_db.is_source_path_explicit_json_db_file
            ):
                primary_update_db.save_db()
        else:
            # Tell other_db to update itself from
            # primary_update_db and save itself to db.
            other_db.update_from(other_db=primary_update_db)
        return updater


def extract_location_info(
    arguments: list[str], min_required: int, max_allowed: int
) -> list[tuple[str, str]]:
    """Helper function to process location arguments captured by argparse."""
    per_arg_to_persist_types = {
        "per-file:": [ATBU_PERSIST_TYPE_PER_FILE],
        "pf:": [ATBU_PERSIST_TYPE_PER_FILE],
        "per-dir:": [ATBU_PERSIST_TYPE_PER_DIR],
        "pd:": [ATBU_PERSIST_TYPE_PER_DIR],
        "per-both:": [ATBU_PERSIST_TYPE_PER_FILE, ATBU_PERSIST_TYPE_PER_DIR],
        "pb:": [ATBU_PERSIST_TYPE_PER_FILE, ATBU_PERSIST_TYPE_PER_DIR],
    }
    current_persist_types = [ATBU_PERSIST_TYPE_PER_DIR]
    locations = []
    for loc in arguments:
        orig_loc = loc
        if max_allowed is not None and len(locations) >= max_allowed:
            raise InvalidCommandLineArgument(
                f"You have already specified {len(locations)} locations. "
                f"The argument '{loc}' is invalid."
            )
        if loc in per_arg_to_persist_types:
            current_persist_types = per_arg_to_persist_types[loc]
            continue
        if len(loc) == 0:
            raise InvalidCommandLineArgument(
                f"Invalid argument '{orig_loc}'. Expected a directory but got '{loc}'"
            )
        loc = os.path.abspath(loc)
        if not os.path.exists(loc):
            raise InvalidCommandLineArgument(
                f"The specified location does not exist: {loc}"
            )
        locations.append(
            (
                loc,
                current_persist_types,
            )
        )
    if len(locations) < min_required:
        raise InvalidCommandLineArgument(
            f"You have only specified '{len(locations)}' "
            f"which is less than the {min_required} required."
        )
    if max_allowed is not None and len(locations) > max_allowed:
        # Given above checks, this should never occur.
        raise InvalidCommandLineArgument(
            f"You specified {len(locations)} locations which "
            f"is more than the {max_allowed} allowed."
        )
    return locations


@dataclass
class LocationSummaryItem:
    location: str
    total_all_files: int
    total_found_unique_files: int
    total_found_physical_files: int
    total_skipped_files: int


def log_location_summary_item(lsi: LocationSummaryItem):
    logging.info(f"Location .............................. {lsi.location}")
    logging.info(f"Location total all files .............. {lsi.total_all_files}")
    logging.info(
        f"Location total found unique files ..... {lsi.total_found_unique_files}"
    )
    logging.info(
        f"Location total found physical files ... {lsi.total_found_physical_files}"
    )
    if lsi.total_skipped_files > 0:
        logging.warning(
            f"Location total skipped files ....... {lsi.total_skipped_files}"
        )
    else:
        logging.info(
            f"Location total skipped files .......... {lsi.total_skipped_files}"
        )


def handle_savedb(args):
    logging.debug("handle_savedb func")
    if args.locations is None:
        raise InvalidCommandLineArgument("You must specify one or more locations.")
    logging.debug(f"locations={args.locations}")
    location_persist_types = extract_location_info(
        args.locations, min_required=1, max_allowed=None
    )

    if not hasattr(args, "database"):
        raise InvalidCommandLineArgument(
            "The --database location has not been specified."
        )
    database_path = args.database
    database_skipped_path = os.path.splitext(database_path)[0] + "-skipped.txt"
    logging.info(f"Database: {database_path}")
    if os.path.exists(database_path):
        if not args.overwrite:
            raise InvalidCommandLineArgument(
                f"The database file already exists: {database_path}"
            )
        os.remove(database_path)
        logging.info(f"Database file erased: {database_path}")
    if os.path.exists(database_skipped_path):
        if not args.overwrite:
            raise InvalidCommandLineArgument(
                f"The database skipped list file already exists: {database_skipped_path}"
            )
        os.remove(database_skipped_path)
        logging.info(f"Database skipped file erased: {database_skipped_path}")
    all_locations_info: defaultdict[str, list[FileInformationPersistent]] = defaultdict(
        list[FileInformationPersistent]
    )
    all_locations_info_skipped = []
    location_summary = []
    for lp in location_persist_types:
        location = lp[0]
        persist_types = lp[1]
        if not os.path.exists(location):
            raise FileNotFoundError(f"Directory does not exist: {location}")

        location_DBs = FileInformationDatabaseCollection(
            source_path=location, persist_types=persist_types
        )
        updater = location_DBs.update(
            change_detection_type=args.change_detection_type,
            update_stale=args.update_stale,
            whatif=False,
        )
        location_info_found = location_DBs.get_dict_digest_to_fi()
        location_info_skipped = updater.skipped_files

        lsi = LocationSummaryItem(
            location=location,
            total_all_files=len(location_info_found) + len(location_info_skipped),
            total_found_unique_files=len(location_info_found),
            total_found_physical_files=sum(
                len(l) for l in location_info_found.values()
            ),
            total_skipped_files=len(location_info_skipped),
        )
        location_summary.append(lsi)
        log_location_summary_item(lsi=lsi)
        for k, v in location_info_found.items():
            all_locations_info[k] += v
        all_locations_info_skipped += location_info_skipped
    save_database_from_dict_file_info(
        dict_digest_to_file_info_list=all_locations_info, database_path=database_path
    )
    with open(database_skipped_path, "w", encoding="utf-8") as database_skipped_file:
        database_skipped_file.write(json.dumps(all_locations_info_skipped))
    logging.info(
        f"========================================================================="
    )
    logging.info(f"The following is a recap of summary information output above:")
    for lsi in location_summary:
        log_location_summary_item(lsi=lsi)
        logging.info(
            f"-------------------------------------------------------------------------"
        )
    logging.info(f"All locations total unique files ...... {len(all_locations_info)}")
    logging.info(
        f"All locations total physical files .... "
        f"{sum(len(l) for l in all_locations_info.values())}"
    )
    if len(all_locations_info_skipped) > 0:
        logging.warning(
            f"All locations skipped files ........... {len(all_locations_info_skipped)}"
        )
    else:
        logging.info(
            f"All locations skipped files ........... {len(all_locations_info_skipped)}"
        )
