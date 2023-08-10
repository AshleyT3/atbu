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
r"""Update persistent file information digests.
"""

import os
import logging

from ..backup.exception import *
from ..backup.constants import *
from .file_info import SneakyCorruptionPotential
from .database import FileInformationDatabaseCollection


def handle_update_digests(args):
    logging.debug("handle_update_digests func")
    if args.locations is None:
        raise ValueError("You must specify one or more locations.")
    logging.debug(f"locations={args.locations}")
    location_list = args.locations
    total_files = 0
    total_files_created = 0
    total_files_updated = 0
    total_files_no_update_required = 0
    total_files_skipped = 0
    sneaky_corruption_potentials: list[SneakyCorruptionPotential] = []
    try:
        location_info: tuple[list[str], str]
        for location_info in location_list:
            persist_types = location_info[0]
            location = location_info[1]
            if not os.path.exists(location):
                raise FileNotFoundError(f"Directory does not exist: {location}")
            logging.info(
                f"-------------------------------------------------------------------------"
            )
            logging.info(f"Updating files in {location}...")
            fi_dbc = FileInformationDatabaseCollection(
                source_path=location, persist_types=persist_types
            )
            updater = fi_dbc.update(
                change_detection_type=args.change_detection_type,
                update_stale=True,
                dryrun=False,
            )
            logging.info(f"{'Location ':.<45} {location}")
            logging.info(f"    {'Location total files ':.<45} {updater.total_files}")
            logging.info(
                f"    {'Location files info created ':.<45} {updater.total_file_info_created}"
            )
            logging.info(
                f"    {'Location files info updated ':.<45} {updater.total_file_info_updated}"
            )
            logging.info(
                f"    {'Location files no update required ':.<45} {updater.total_files_no_update_required}"
            )
            logging.info(
                f"    {'Location files info stale/error, skipped':.<45} {updater.total_files_stale_info_skipped + updater.total_files_without_primary_digest}"
            )
            if len(updater.sneaky_corruption_potentials) > 0:
                logging.info(
                    f"{'Total potential sneaky corruption':.<45} {len(updater.sneaky_corruption_potentials)} (see details above)"
                )
            total_files += updater.total_files
            total_files_created += updater.total_file_info_created
            total_files_updated += updater.total_file_info_updated
            total_files_no_update_required += updater.total_files_no_update_required
            total_files_skipped += (
                updater.total_files_stale_info_skipped
                + updater.total_files_without_primary_digest
            )
            sneaky_corruption_potentials.extend(updater.sneaky_corruption_potentials)
    except Exception as ex:
        logging.info("")
        logging.error(
            f"ERROR: The update-digest command failed: {os.linesep}{exc_to_string_with_newlines(ex)}"
        )
        logging.info("")
        logging.error(
            "Given the exception above, the following summary may be incomplete:"
        )
        logging.info("")
    finally:
        logging.info(f"=" * 65)
        if len(sneaky_corruption_potentials) > 0:
            logging.info(f"=" * 65)
            logging.info("Potential sneaky corruption all locations processed:")
            for scp in sneaky_corruption_potentials:
                logging.info(f"    path={scp.file_info.path}")
                logging.info(f"    old_size={scp.old_size_in_bytes}")
                logging.info(f"    cur_size={scp.cur_size_in_bytes}")
                logging.info(f"    old_time={scp.old_modified_time}")
                logging.info(f"    cur_time={scp.cur_modified_time}")
                logging.info(f"    old_digest={scp.old_digest}")
                logging.info(f"    cur_digest={scp.cur_digest}")
                logging.info(f"-" * 65)
            logging.info(
                f"    Total potential sneaky corruption Location A: {len(sneaky_corruption_potentials)}"
            )
            logging.info(f"=" * 65)

        logging.info(f"Total all locations processed:")
        logging.info(f"    {'Total files ':.<45} {total_files}")
        logging.info(f"    {'Total Files info created ':.<45} {total_files_created}")
        logging.info(f"    {'Total files info updated ':.<45} {total_files_updated}")
        logging.info(
            f"    {'Total files no update required ':.<45} {total_files_no_update_required}"
        )
        logging.info(
            f"    {'Total files info stale/error, skipped':.<45} {total_files_skipped}"
        )
        logging.info(
            f"    {'Total potential sneaky corruption':.<45} {len(sneaky_corruption_potentials)} (see details above)"
        )
