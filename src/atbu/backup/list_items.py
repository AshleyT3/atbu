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
r"""List various ATBU items: storage definitions, specific backups, files within.
"""
import logging
from tabulate import tabulate

from ..common.exception import InvalidStateError
from ..common.constants import CONFIG_SECTION_STORAGE_DEFINITION_SPECIFIER_PREFIX
from .backup_selections import (
    get_storage_defintions_from_sbs_list_list,
    user_specifiers_to_selections,
)
from .backup_core import StorageDefinition


def handle_list(args):
    logging.debug(f"handle_list")

    specifiers: list[str] = args.specifiers
    if not specifiers:
        specifiers = [f"{CONFIG_SECTION_STORAGE_DEFINITION_SPECIFIER_PREFIX}:*"]

    sbs_list_list = user_specifiers_to_selections(
        specifiers=specifiers, no_selections_ok=True
    )

    headers = [
        "Storage Definition",
        "Provider",
        "Container",
        "Interface",
        "Encrypted",
        "Persisted IV",
    ]
    records = []
    storage_def_list: list[
        StorageDefinition
    ] = get_storage_defintions_from_sbs_list_list(sbs_list_list=sbs_list_list)
    for storage_def in storage_def_list:
        storage_def_name = storage_def.storage_def_name
        records.append(
            [
                storage_def_name,
                storage_def.driver_factory.provider_name,
                storage_def.container_name,
                storage_def.driver_factory.interface_type,
                storage_def.is_encryption_used,
                storage_def.storage_persisted_encryption_IV,
            ]
        )
    logging.info(
        "\n" + tabulate(tabular_data=records, headers=headers, tablefmt="simple")
    )

    for sbs_list in sbs_list_list:  # pylint: disable=not-an-iterable
        storage_def_name = None
        for sbi in sbs_list:
            if sbi.specific_backup_info is None:
                continue
            if not storage_def_name:
                storage_def_name = sbi.storage_def_name
                logging.info(
                    f"Specific backups from storage definition '{storage_def_name}'"
                )
            elif storage_def_name != sbi.storage_def_name:
                raise InvalidStateError(
                    f"Expected entire list to belong to the same storage def '{storage_def_name}'"
                )
            logging.info(f"  {sbi.specific_backup_name}")
            list_fi_sorted = sorted(sbi.selected_fi.values(), key=lambda fi: fi.path)
            for sb_fi in list_fi_sorted:
                logging.info(f"    {sb_fi.path}")
