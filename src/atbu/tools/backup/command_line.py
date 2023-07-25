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
r"""Main entry point, argument parsing.
"""
# pylint: disable=line-too-long

import argparse
import logging
import multiprocessing
import os
import re
import sys
from typing import Union

from atbu.common.exception import (
    exc_to_string,
    AtbuException,
    InvalidCommandLineArgument,
    InvalidStateError,
    QueueListenerNotStarted,
    SingletonAlreadyCreated,
)
from atbu.common.profile import EasyProfile
from atbu.mp_pipeline.mp_global import (
    deinitialize_logging,
    get_verbosity_level,
    global_init,
    initialize_logging_basic,
    initialize_logging,
    remove_created_logging_handlers,
    remove_root_stream_handlers,
)
from atbu.common.hasher import (
    DEFAULT_HASH_ALGORITHM,
)
from atbu.tools.backup.config import (
    set_automated_testing_mode,
    get_automated_testing_mode,
    register_storage_def_config_override,
)


from .constants import *
from .exception import CredentialSecretFileNotFoundError, YubiKeyBackendNotAvailableError
from .global_hasher import GlobalHasherDefinitions
from .backup_core import (
    BACKUP_COMPRESSION_CHOICES,
    BACKUP_COMPRESSION_DEFAULT,
    BACKUP_INFO_EXTENSION,
)
from .backup_cmdline import handle_backup
from .restore import handle_restore, handle_decrypt
from .verify import handle_verify
from .recover import handle_recover
from .list_items import handle_list
from .yubikey_helpers import set_require_yubikey, setup_yubikey_infra
from .creds_cmdline import handle_creds
from ..persisted_info.file_info import (
    CHANGE_DETECTION_CHOICES,
    CHANGE_DETECTION_TYPE_DATESIZE,
    CHANGE_DETECTION_TYPE_DIGEST,
    CHANGE_DETECTION_TYPE_FORCE,
)
from ..persisted_info.update_digests import handle_update_digests
from ..persisted_info.database import handle_savedb
from ..persisted_info.diff import handle_diff, DIFF_COMMAND_CHOICES
from ..persisted_info.arrange import handle_arrange

class AtbuRawTextHelpFormatter(argparse.RawTextHelpFormatter):
    """This class modifies RawTextHelpFormatter help text to insert
    blank lines with a heading before each group of ATBU argparse subparsers.

    Instead of something like this...
        ...
        backup              Backup files to a local file system folder or the cloud.
        restore             Restore selected files from a backup.
        ...

    ...a heading is inserted with blank lines as follows...

        ...
                        Backup/Restore/Verify sub-commands
                        -----------------------------------

    backup              Backup files to a local file system folder or the cloud.
    restore             Restore selected files from a backup.
        ...
    """
    def format_help(self):

        help_text = super().format_help()

        m = re.search(
            pattern=r"( +backup +)Backup files to a local file system folder or the cloud.",
            string=help_text,
        )
        if m is not None:
            help_padding = m.end(1) - m.start(1)
            help_text = (
                help_text[:m.start()] +
                "\n" +
                " " * help_padding + "Backup/Restore/Verify sub-commands\n" +
                " " * help_padding + "-----------------------------------\n" +
                "\n" +
                help_text[m.start():]
            )

        m = re.search(
            pattern=r"( +update-digests +)Update persistent file information in the specified directories.",
            string=help_text,
        )
        if m is not None:
            help_padding = m.end(1) - m.start(1)
            help_text = (
                help_text[:m.start()] +
                "\n" +
                " " * help_padding + "Persistent file information-related sub-commands (unrelated to backup/restore)\n" +
                " " * help_padding + "------------------------------------------------------------------------------\n" +
                "\n" +
                help_text[m.start():]
            )

        m = re.search(
            pattern=r"( +help +)Show help on specific subjects:",
            string=help_text,
        )
        if m is not None:
            help_padding = m.end(1) - m.start(1)
            help_text = (
                help_text[:m.start()] +
                "\n" +
                " " * help_padding + "Other sub-commands\n" +
                " " * help_padding + "------------------\n" +
                "\n" +
                help_text[m.start():]
            )

        return help_text


class PerDirFileAction(argparse.Action):
    """Track the last specified 'per-*' option.
    The class variable PerDirFileAction.current_persist_type holds the last specified value.
    """
    current_persist_type = None
    per_arg_to_persist_types = {
        "per-file": [ATBU_PERSIST_TYPE_PER_FILE],
        "pf": [ATBU_PERSIST_TYPE_PER_FILE],
        "per-dir": [ATBU_PERSIST_TYPE_PER_DIR],
        "pd": [ATBU_PERSIST_TYPE_PER_DIR],
        "per-both": [ATBU_PERSIST_TYPE_PER_FILE, ATBU_PERSIST_TYPE_PER_DIR],
        "pb": [ATBU_PERSIST_TYPE_PER_FILE, ATBU_PERSIST_TYPE_PER_DIR],
    }
    # pylint: disable=redefined-outer-name
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None and nargs != 0:
            raise ValueError("nargs not allowed")
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        persist_type = PerDirFileAction.per_arg_to_persist_types.get(option_string.lstrip("-"))
        if persist_type is None:
            raise ValueError(
                f"Expecting option_string to be one of: {PerDirFileAction.per_arg_to_persist_types}"
            )
        PerDirFileAction.current_persist_type = persist_type
        setattr(namespace, self.dest, values)


class LocationAction(argparse.Action):
    """Handle persist tooling location options.
    Generally, this action requires at least one "--per-*" option (perist type) to be specified
    prior to any locations. If the PerDirFileAction.current_persist_type is None, this action
    will fail to accept a location.

    Locations are placed in a list, namespace.<dest>, which contains a tuple for each location
    in the format (<persist_type>,<location>).
    """
    # pylint: disable=redefined-outer-name
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        if PerDirFileAction.current_persist_type is None:
            raise argparse.ArgumentError(
                None,
                f"One of --pf, --per-file, --pd, or --per-dir "
                f"must be specified before {option_string}."
            )
        if not isinstance(values, list) or len(values) != 1:
            # argparse should catch this so this catches breaking or unexpected code changes.
            raise argparse.ArgumentError(
                None,
                f"Only one location can be specified using the {option_string} option."
            )
        if not hasattr(namespace, self.dest) or getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, [])
        locations: list[str] = getattr(namespace, self.dest)
        max_allowed = 1 if self.nargs is None else self.nargs
        try:
            max_allowed = int(max_allowed)
            if len(locations) >= max_allowed:
                raise argparse.ArgumentError(None, f"The {option_string} option can only be specified {max_allowed} time(s).")
        except ValueError:
            # No limit on number of locations (i.e., nargs="+").
            pass
        locations.append((PerDirFileAction.current_persist_type, values[0]))


#
# Common help strings used by argparse configuration further below.
#
storage_def_specifier_help = """
<storage-def-specifier>:
    <storage-def-specifier> is at least a storage specifier, possibly followed by backup and file selectors.
    For the case of a backup, it is simply a storage specifier. For the case of restore, verify and some list
    commands, it is usually a storage specifier, a backup selector, one or more file selectors, all of which
    determine what storage files to restore, verify, list, etc.
        <storage-def-specifier> is shorthand for the following...
        <storage-specifier> [backup:<backup_specifier> [files:<file_specifier> [files:<file_specifier>] ... ] ] ...
    Not all commands allow all portions of a <storage-def-specifier>. See command-specific help for clarification.
    Details:
        <storage_specifier>: storage-def:<storage-definition-name>
            where
                * <storage-definition-name> is either a folder of a local file system backup or
                  a the name you gave to a cloud storage configuration.
                * 'storage-def' can be abbreviated to 'storage' if desired.
            Examples:
                - storage-def:my_cloud_cfg
                - storage:my_cloud_cfg (same as storage-def:my_cloud_cfg)
                - d:\\MyLocalBackup
        backup:<backup_specifier>
            where
                * <backup_specifier> can be 'last' to indicate the most recent backup.
                * <backup_specifier> can be a glob-like selector such as '*20220509-142129*'.
            Examples:
                - backup:last is the most recent backup.
                - backup:MyBackup-20220509-142129 is a specific backup of MyBackup from May 9, 2022 at 14:21:29.
                - backup:MyBackup-2022* are all backups to MyBackup in the year 2022.
        files:<file_specifier>
            where
                * <file_specifier> is essentially a glob-like pattern indicating files to select.
            Examples:
                - files:* will select all files.
                - files:*.txt will select all files ending with ".txt"
"""

backup_information_switch_help = f"""
Backup Information (BI)
=======================
Backup information (BI) is the information that {ATBU_PROGRAM_NAME} stores during and at the end of a
backup. It is contained in *{BACKUP_INFO_EXTENSION} files which are stored in BI directories. This
section discusses BI, BI-related files and locations.

By default, {ATBU_PROGRAM_NAME} stores BI in the following locations:

    For cloud storage definitions:
        Primary: <HOME>/{ATBU_DEFAULT_CONFIG_DIR_NAME}/{ATBU_DEFAULT_BACKUP_INFO_SUBDIR}
        Secondary: None

    For file system storage definitions:
        Primary: <HOME>/{ATBU_DEFAULT_CONFIG_DIR_NAME}/{ATBU_DEFAULT_BACKUP_INFO_SUBDIR}
        Secondary: <backup-dest>/{ATBU_DEFAULT_CONFIG_DIR_NAME}/{ATBU_DEFAULT_BACKUP_INFO_SUBDIR}
        (Basically, file system storage backups store a copy on the destination storage media.)

You can override the defaults by specifying configuration settings in your backup's storage definition
configuration .json file. You can specify backup information directory configuration information in
the .json configuration's {CONFIG_SECTION_GENERAL} section. For example, consider the following "{CONFIG_VALUE_NAME_BACKUP_INFO_DIR}"
setting:

    ...
    "{CONFIG_SECTION_GENERAL}": {{
        "{CONFIG_VALUE_NAME_BACKUP_INFO_DIR}": [
            "F:\\MyBackupInfo"
        ]
    }}
    ...

If the above were added to a cloud storage definition configuration, {ATBU_PROGRAM_NAME} would end up using
the following backup information directories...

    For cloud storage definitions:
        Primary: <HOME>/{ATBU_DEFAULT_CONFIG_DIR_NAME}/{ATBU_DEFAULT_BACKUP_INFO_SUBDIR}
        Secondary: F:\\MyBackupInfo

Notice that the default primary is still the same but now there is a secondary when before there was
not. With a secondary backup information location in place, during backup {ATBU_PROGRAM_NAME} save the
primary copy to the primary location, and it will then copy that to the secondary location of
F:\\MyBackupInfo.

You can instruct {ATBU_PROGRAM_NAME} to not use any default backup information directories by specifying
the {CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS} setting. For example:

    ...
    "{CONFIG_SECTION_GENERAL}": {{
        "{CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS}": true,
        "{CONFIG_VALUE_NAME_BACKUP_INFO_DIR}": [
            "F:\\\\MyBackupInfo"
        ]
    }}
    ...

With the above {CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS}=true setting in place, {ATBU_PROGRAM_NAME} will use the following
backup information directory:

    Primary: F:\\MyBackupInfo

Notice the HOME directory location is no longer utilized. The only backup information directory is
F:\\MyBackupInfo which is now also the primary backup information directory.

Using Offline Config and BI
===========================
You can store a backup storage definition configuration and its secrets, along with all backup
information, offline on a removable drive, where the drive is only inserted into the client during
the time when backup operations are taking place. The following outlines how this can be accomplished.

You can use the {ATBU_PROGRAM_NAME} --config-file switch to reference a backup storage definition configuration
and its credentials as stored in a .json file. The .json file can be created by exporting your
backup storage definition using the "{ATBU_PROGRAM_NAME} creds export..." command.

After exporting to .json, you can then use "{ATBU_PROGRAM_NAME} <command_and_options> --config-file <json_file>"
to perform a backup/restore or other operations, where {ATBU_PROGRAM_NAME} will use the .json file's contents
to access the configuration, including its credentials/secrets. If the .json file was created from a
password-protected storage configuration, you will likewise be prompted to enter the password when
using --config-file to reference the .json backup storage definition configuration ("{ATBU_PROGRAM_NAME} creds export..."
exports password-protected credentials.).

By using an exported configuration, you can keep a configuration and its secrets off a client system,
and only make them available when performing backup operations. For example:

    1. atbu creds export storage-def:my-cloud-backup F:\\B\\my-cloud-backup-config.json, where F:
       is a USB Drive.

    2. Insert the USB Drive and perform a backup, referencing the F: .json config file.
       Example:
           atbu backup C:\\MyFiles storage-def:my-cloud-backup --full --config-file F:\\B\\my-cloud-backup-config.json

When you run the backup command in step 2, {ATBU_PROGRAM_NAME} will use the backup storage definition configuration
information, including secrets, stored in the "F:\\B\\my-cloud-backup-config.json" file.

Even though the above keeps the credentials stored offline, the backup information is still stored
in the default locations (i.e., the backup information is still stored on the local drive). To keep
the backup information offline (along with the storage definition configuration) you can perform the
following general steps:

    1. atbu creds export storage-def:my-cloud-backup F:\\B\\my-cloud-backup-config.json.

    2. Edit F:\\B\\my-cloud-backup-config.json, adding the following settings:
        ...
        \"{CONFIG_SECTION_GENERAL}\": {{
            \"{CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS}\": true,
            \"{CONFIG_VALUE_NAME_BACKUP_INFO_DIR}\": [
                "{{CONFIG_DIR}}/atbu-backup-info"
            ]
        }}
        ...

    3. Perform a backup.
       Example:
           atbu backup C:\\MyFiles storage-def:my-cloud-backup --full --config-file F:\\B\\my-cloud-backup-config.json

The above 3 steps are similar to the prior example except that a new step #2 has been inserted. This
new step #2 modifies the exported .json configuration to disable default backup information
directories, while also specifying the primary (and only) backup information directory should be
"{{CONFIG_DIR}}/atbu-backup-info".

The "{{CONFIG_DIR}}" string is replaced with the directory where the configuration file itself is
located, F:\\B\\my-cloud-backup-config.json. Given this, the location of the backup information
directory would be "F:\\B\\atbu-backup-info\\...".

IMPORTANT: For large backups, ensure the location of any backup information directory is well-performing.
If you use a very slow USB Drive, reading/writing large backup information files can be time consuming.

In addition to "{{CONFIG_DIR}}", you can also specify "{{DEFAULT_CONFIG_DIR}}" which is the default
HOME {ATBU_DEFAULT_CONFIG_DIR_NAME} configuration directory.

Here is a summary of the replacements:

    "{{DEFAULT_CONFIG_DIR}}": The <HOME>/{ATBU_DEFAULT_CONFIG_DIR_NAME} location. 
    "{{CONFIG_DIR}}": The <config>/{ATBU_DEFAULT_CONFIG_DIR_NAME} location.

If you want to add multiple backup information directories to your configuration, simply add an
element to the .json array. For example:

        ...
        \"{CONFIG_SECTION_GENERAL}\": {{
            \"{CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS}\": true,
            \"{CONFIG_VALUE_NAME_BACKUP_INFO_DIR}\": [
                "{{CONFIG_DIR}}/atbu-backup-info",
                "G:\\\\B\\\\atbu-backup-info"
            ]
        }}
        ...

Because \"{CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS}\" is set to true, there are no defaults implicitly inserted,
so the primary backup information directory is therefore the first one explicitly configured, which
in this case is "{{CONFIG_DIR}}/atbu-backup-info". Additionally, there is one secondary backup
information directory specified. All together, the BI directory configuration ends up being as
follows:

    Primary: "{{CONFIG_DIR}}/atbu-backup-info"
    Secondary #1: "G:\\B\\atbu-backup-info"

Consider the following configuration that does not disable default backup information directories:
        ...
        \"{CONFIG_SECTION_GENERAL}\": {{
            \"{CONFIG_VALUE_NAME_BACKUP_INFO_DIR_NO_DEFAULTS}\": false,
            \"{CONFIG_VALUE_NAME_BACKUP_INFO_DIR}\": [
                "{{CONFIG_DIR}}/atbu-backup-info",
                "G:\\\\B\\\\atbu-backup-info"
            ]
        }}
        ...

The result would be the following:

    Primary: "{{DEFAULT_CONFIG_DIR}}/atbu-backup-info"
    Secondary #1: "{{CONFIG_DIR}}/atbu-backup-info"
    Secondary #2: "G:\\B\\atbu-backup-info"

The above result is because, with defaults active, the primary is always implicitly the default HOME
{ATBU_DEFAULT_CONFIG_DIR_NAME} configuration directory. This means the two directories explicitly specified become secondary
backup information directories.

Additional Information
======================
The {ATBU_PROGRAM_NAME} command uses local copies of *{BACKUP_INFO_EXTENSION} to understand the history of what is been backed
up. There must always be a "primary" backup information directory which contains the latest backup
information. The other BI directories than the primary are secondary and merely backup copies in
case the primary copies are unavailable. Having backup copies can allow for easier recovery or
browsing in certain cases, where it is desired to mitigate the need to use "{ATBU_PROGRAM_NAME} recover..." for
a full recovery. Recovery is generally used when all local copies of the latest backup information
have been lost or destroyed.

VERY IMPORTANT: Do not arbitrarily change a storage definition's backup information directory
configuration. Care must be taken to ensure, if you ever change a configuration's primary backup
information directory, you ensure that directory is populated with the latest copies of backup
information *{BACKUP_INFO_EXTENSION} files. You would do this by copying to the new location, or perhaps using
the "{ATBU_PROGRAM_NAME} recover..." command. Generally, once you establish backup information directories,
you should stick with the current settings unless changes are truly reasonable.

Regardless of any BI directory configuration options discussed in this help, {ATBU_PROGRAM_NAME} always backs
up *{BACKUP_INFO_EXTENSION} files at the end of each backup. These backup copies of *{BACKUP_INFO_EXTENSION} files are not
stored directly as *{BACKUP_INFO_EXTENSION}, but are instead encrypted (if encryption is enabled) and
stored as backup files for use primarily by the "{ATBU_PROGRAM_NAME} recover..." command during disaster
recovery. These backup copies of the *{BACKUP_INFO_EXTENSION} files are unrelated to the copies stored locally
at the client which is the primary subject of the above documentation.
"""

extra_help_subjects = {
    "specifiers": storage_def_specifier_help,
    "backup-info": backup_information_switch_help,
}

console_formatter = logging.Formatter("%(asctime)-15s %(threadName)s %(message)s")


def create_argparse():
    #
    # Root parser
    #
    parser = argparse.ArgumentParser(
        description=f"{ATBU_ACRONUM_U} v{ATBU_VERSION_STRING}",
        formatter_class=AtbuRawTextHelpFormatter,
    )

    # Uncomment to allow --debug-server (for use with VS Code pydebug)
    # Activate the debug server to listen on specified port, wait for a client connect.
    # parser.add_argument(
    #     "--debug-server",
    #     help=argparse.SUPPRESS,
    #     type=int,
    #     required=False,
    # )

    # Specified by automated tests to be used by this utility as needed for E2E tests.
    parser.add_argument(
        "--automated-testing",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )

    #
    # Common to all parser
    #
    parser_common = argparse.ArgumentParser(add_help=False)
    parser_common.add_argument(
        "--logfile",
        help="The location of log file path. If not specified, do not log to file.",
    )
    parser_common.add_argument(
        "--loglevel", help="level for logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)."
    )
    parser_common.add_argument(
        "--log-console-detail",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="""When logging to console use detailed format.
""",
    )
    parser_common.add_argument(
        "-v",
        "--verbosity",
        action="count",
        help="""increase verbosity with each usage (i.e., -vv is more verbose than -v).
""",
    )
    parser_common.add_argument(
        "--yk",
        action="store_true",
        default=False,
        help="""Require YubiKey HMAC-SHA1 challenge/response to access the backup encryption key.
When this option is specified, a YubiKey with slot 2 configured for HMAC-SHA1
challenge/response will be used/required along with your password to unlock a
backup encryption key. This means, for a password-protected backup, you will be
required to have your password and a YubiKey. This option is also used when
setting up a backup for use with Yubikey. You must have a YubiKey and you must
ensure yubikey-manager is installed (i.e., pip install yubikey-manager). See
documentation for further details.
""",
    )
    parser_common.add_argument(
        "--profile",
        action="store_true",
        default=False,
        help="""Run the command with an instance of cProfile.Profile() active, capturing the
results to file when the command completes.
""",
    )
    parser_common.add_argument(
        "--profile-stats",
        action="store_true",
        default=False,
        help="""When --profile is specified, display profile stats when the command completes.
""",
    )
    parser_common.add_argument(
        "--profile-file",
        help="""When specified, write the profile stats to the specified file name. The filename
must not already exist.
""",
    )

    #############################################################################################
    #                                backup-related argparse setup                              #
    #############################################################################################

    #
    # Common credential filename argument (currently used for import/export of credentials).
    #
    parser_credential_filename_positional = argparse.ArgumentParser(add_help=False)
    parser_credential_filename_positional.add_argument(
        "filename",
        help="The path to the credential file.",
    )

    #
    # An optional explicit configuration file which is searched for credentials.
    #
    parser_credential_filename_optional = argparse.ArgumentParser(add_help=False)
    parser_credential_filename_optional.add_argument(
        "--config-file", "-c",
        help=f"""The path to the credential configuration file. When specified, this config file is
the first "credential store" that is searched. To use this, use "{ATBU_PROGRAM_NAME} creds export..."
to export a backup storage definition configuration to a .json file. You can then
specify that json file as the argument to --config-file when you run backup, restore,
etc. commands.

When running a backup command with --config-file specified, ATBU will consider
credentials in that file for the storage definition in question. You can delete
the credentials from your local system's keystore and thereby keep your storage
config and credentials offline when not backing up.

When performing "{ATBU_PROGRAM_NAME} creds export...", if your secrets are password-protected,
the password-protection status will persist in the exported .json file. When you
use --config-file with a .json containing a password-protected backup config, you
will still be prompted for your password. This means if you keep the config on
removeable media which is lost, the credentials require a password to unlock.
IMPORTANT: Do not use a credential .json on a USB Drive as your main exported
config/secrets backup. Keep other copies in safe places!
""",
    )

    #
    # Common destination file overwrite argument.
    #
    parser_file_ovewrite = argparse.ArgumentParser(add_help=False)
    parser_file_ovewrite.add_argument(
        "--overwrite",
        help="Overwrite the destination file if it already exists.",
        action=argparse.BooleanOptionalAction,
        default=False,
    )

    # Add a subparser to act as a heading with blank lines before/after.
    subparsers = parser.add_subparsers(
        help=f"""""",
    )

    #
    # 'backup' subparser.
    #
    parser_backup = subparsers.add_parser(
        "backup",
        formatter_class=argparse.RawTextHelpFormatter,
        help="Backup files to a local file system folder or the cloud.",
        parents=[parser_common, parser_credential_filename_optional],
    )
    group_backup_operation = parser_backup.add_mutually_exclusive_group(required=True)
    group_backup_operation.add_argument(
        f"-{ATBU_BACKUP_TYPE_FULL[0]}",
        f"--{ATBU_BACKUP_TYPE_FULL}",
        help="""Perform a full backup. All files will be backed up regardless of changes.
""",
        action="store_true",
    )
    group_backup_operation.add_argument(
        f"-{ATBU_BACKUP_TYPE_INCREMENTAL[0]}",
        f"--{ATBU_BACKUP_TYPE_INCREMENTAL}",
        help="""Perform an incremental backup. Files whose modified date, size in bytes have changed
since the prior backup.
""",
        action="store_true",
    )
    group_backup_operation.add_argument(
        f"--{ATBU_BACKUP_TYPE_INCREMENTAL_PLUS_SHORT_CMD_OPT}",
        f"--{ATBU_BACKUP_TYPE_INCREMENTAL_PLUS}",
        help="""Perform a comprehensive incremental backup. Files whose modified date, size in bytes,
or hash have changed since the prior backup. This reqiures generating the hash of all
source files which can be intensive and time consuming. Generally, it may be a good
idea, depending on the number of source files, to perform an incremental plus
backup once a while to ensure maximum integrity.
""",
        action="store_true",
    )
    parser_backup.add_argument(
        "source_dirs",
        metavar="source-dirs",
        type=str,
        nargs="+",
        help=f"""One more locations to backup.""",
    )
    parser_backup.add_argument(
        "dest_storage_specifier",
        metavar="dest-storage-specifier",
        type=str,
        help=f"""The destination to backup. The destiation is a <storage-def-specifier>.
To learn more about specifying storage definitions, backups, and files,
see '{ATBU_PROGRAM_NAME} help specifiers' for details.
""",
    )
    parser_backup.add_argument(
        "--dedup",
        choices=[
            ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST,
            ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST_EXT,
        ],
        nargs=1,
        help=f"""For --incremental-plus backups only, employ deduplication given the designated
deduplication method:

    '{ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST}':     This option causes the backup to consider a file unchanged if its
                  digest/date/size match that of an already backed up file, regardless
                  of the other file's path or filename.

    '{ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST_EXT}': This option is the same as '{ATBU_BACKUP_DEDUPLICATION_TYPE_DIGEST}' except a file must have an extension
                  which matches the already backed up file in order to be considered a
                  duplicate of that file.
                  
                  In all cases, if a deduplication match is detected, the file being
                  considered for backup not backed up but is instead marked a duplicate.
                  During restore, a duplicate resolution process will take place,
                  re-associating a duplicate with a physically backed up file matching
                  the same characteristics used to determine it was a duplicate. Generally
                  speaking, a {DEFAULT_HASH_ALGORITHM} hash match will very rarely have a collision. The
                  additional checks, such as date/size/extension are additional checks
                  which may help mitigate a rare hash collision.

""",
    )
    parser_backup.add_argument(
        "-e",
        "--exclude",
        default=[],
        nargs="+",
        help=f"""Specify one or more glob-like patterns that, if any are matched to a file's path,
the file will not be included in the backup.
""",
    )
    parser_backup.add_argument(
        "--detect-bitrot",
        "--dbr",
        "--detect-sneaky-corruption",
        "--dsc",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=f"""Enabled by default, reports potential bitrot (aka "sneaky corruption") as an error.
Requires use of --incremental-plus (--ip). Use --no-detect-bitrot (--no-dbr) to
squelch reporting as an error (still reported informationally). Bitrot or so-called
sneaky corruption is detected when a file's date/time and size have remained the
same since the last backup, but the digests are different.""",
    )
    parser_backup.add_argument(
        "-z",
        "--compression",
        choices=BACKUP_COMPRESSION_CHOICES,
        help=f"""Set the backup compression level. The default is '{BACKUP_COMPRESSION_DEFAULT}'.
""",
    )
    parser_backup.set_defaults(func=handle_backup)

    #
    # 'restore' subparser.
    #
    parser_restore = subparsers.add_parser(
        "restore",
        formatter_class=argparse.RawTextHelpFormatter,
        parents=[parser_common, parser_credential_filename_optional],
        help="Restore selected files from a backup.",
        description=f"""Restore selected files from a backup.

Examples:

    {ATBU_PROGRAM_NAME} restore d:\\MySourceBackup backup:last files:* c:\\MyRestoreDirectory
        From the last backup to d:\\MySourceBackup, restore all files to c:\\MyRestoreDirectory
        In this case, d:\\MySourceBackup is a local backup (located on d: drive) and not a cloud backup.

    {ATBU_PROGRAM_NAME} restore storage:my_cloud_backup backup:last files:* c:\\MyRestoreDirectory
        From the last backup to storage:my_cloud_backup, restore all files to c:\\MyRestoreDirectory
        In this case, storage:my_cloud_backup is a cloud backup.    
""",
    )
    parser_restore.add_argument(
        "source_storage_specifiers",
        metavar="source-storage-specifiers",
        type=str,
        nargs="+",
        help=f"""The source selections to restore from. To learn more about specifying storage definitions,
backups, and files, see '{ATBU_PROGRAM_NAME} help specifiers' for details.
""",
    )
    parser_restore.add_argument(
        "restore_dir",
        metavar="restore-dir",
        type=str,
        help=f"""The destination directory for the restored files.""",
    )
    parser_restore.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="""If specified, allows overwriting already existing destination files.""",
    )
    parser_restore.add_argument(
        "--auto-mapping",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="""Use --no-auto-mapping to disable automatic restore path mapping. By default,
paths mapped to allow restoring with minimal path components relative
to the restore directory. When that is not desirable, use --no-auto-mapping.
""",
    )
    parser_restore.set_defaults(func=handle_restore)

    #
    # 'verify' subparser.
    #
    parser_verify = subparsers.add_parser(
        "verify",
        help="Verify selected files from a backup.",
        description=f"""Verify selected files from a backup.

Examples:

    {ATBU_PROGRAM_NAME} verify d:\\MySourceBackup backup:last files:*
        From the last backup to d:\\MySourceBackup, verify all files.
        In this case, d:\\MySourceBackup is a local backup (located on
        d: drive) and not a cloud backup.

    {ATBU_PROGRAM_NAME} verify storage:my_cloud_backup backup:last files:*
        From the last backup to storage:my_cloud_backup, verify all files
        In this case, storage:my_cloud_backup is a cloud backup.

To learn more about specifying a storage definitions, backups,
and files, see '{ATBU_PROGRAM_NAME} help specifiers'
""",
        formatter_class=argparse.RawTextHelpFormatter,
        parents=[parser_common, parser_credential_filename_optional],
    )
    parser_verify.add_argument(
        "source_storage_specifiers",
        metavar="source-storage-specifiers",
        type=str,
        nargs="+",
        help=f"""The source selections to restore from. To learn more about specifying storage definitions,
backups, and files, see '{ATBU_PROGRAM_NAME} help specifiers' for details.
""",
    )
    parser_verify.add_argument(
        "--compare",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="""
If specified, performs comparison with local copy of the file. If not specified, only the digests
are calculated/compared (default).
""",
    )
    parser_verify.add_argument(
        "--compare-root",
        type=str,
        help="""
When --compare is specified, --compare-root, if specified, is folder under which are the
local files used for comparison. If --compare-root is not specified, the file's original
backup location is used.
""",
    )
    parser_verify.set_defaults(func=handle_verify)

    #
    # 'list' subparser.
    #
    parser_list = subparsers.add_parser(
        "list",
        help="List storage definitions, backups, and files relating to backups.",
        parents=[parser_common, parser_credential_filename_optional],
    )
    parser_list.add_argument(
        "specifiers",
        metavar="[<source> <specific-backup> <file-selections>]",
        type=str,
        nargs="*",
        help=f"""
The source backup specifiers for the list.
Examples:
    {ATBU_PROGRAM_NAME} list
        List all known storage definitions.
    {ATBU_PROGRAM_NAME} list d:\\MySourceBackup backup:last files:*
        From the last backup to d:\\MySourceBackup, list all files.
        In this case, d:\\MySourceBackup is a local backup (located on d: drive) and not a cloud backup.
    {ATBU_PROGRAM_NAME} list storage:my_cloud_backup backup:last files:*
        From the last backup to storage:my_cloud_backup, list all files
        In this case, storage:my_cloud_backup is a cloud backup.
To learn more about specifying a storage definitions, backups, and files, see '{ATBU_PROGRAM_NAME} help specifiers'
""",
    )
    parser_list.set_defaults(func=handle_list)

    #
    # Common storage-def-specifier argument for creds subparsers.
    #
    parser_creds_storage_def_specifier = argparse.ArgumentParser(add_help=False)
    parser_creds_storage_def_specifier.add_argument(
        "storage_def",
        metavar="<storage-def-specifier>",
        type=str,
        help=f"""Backup storage definition to affect. This can be a storage definition name or file
path to file system storage location. See '{ATBU_PROGRAM_NAME} help specifiers'.
""",
    )

    #
    # 'creds' subparser.
    #
    parser_creds = subparsers.add_parser(
        "creds",
        formatter_class=argparse.RawTextHelpFormatter,
        help=f"""Create/delete backup configurations, backup/restore/set credentials.""",
        parents=[parser_common],
    )
    subparser_creds = parser_creds.add_subparsers(
        dest="subcmd",
    )

    #
    # creds create-storage-def:
    #

    # pylint: disable=unused-variable
    cred_create_storage_def_parser = subparser_creds.add_parser(
        CREDS_SUBCMD_CREATE_STORAGE_DEF,
        parents=[parser_creds_storage_def_specifier, parser_credential_filename_optional, parser_common],
        formatter_class=argparse.RawTextHelpFormatter,
        help=f"Create a backup storage definition.",
        description=f"""where

    <interface>           <'filesystem','libcloud'|'google'>
    <provider>            <'filesystem'|'azure_blobs'|'google_storage'>
    <container>           The cloud storage container or bucket name.
    <key>                 access key
    <secret_access_key>   storage secret access key
    [,k=v[,k=v ...]]      extra parameters as needed: name1=value1,name2=value2,...

Create a storage definition. No spaces allowed as shown. If <secret_access_key> evaluates to an
existing filename with a .json extension, the path to that file will be saved as the crednetial
(i.e., an OAuth2 service account file). For some configurations, it may be easier or necessary
to edit the config .json file directly, adding whatever driver arguments you wish.

Examples:

    {ATBU_PROGRAM_NAME} creds {CREDS_SUBCMD_CREATE_STORAGE_DEF} my-cloud-backup libcloud azure_blobs key=<access_key>,secret=<secret_access_key>
    {ATBU_PROGRAM_NAME} creds {CREDS_SUBCMD_CREATE_STORAGE_DEF} my-cloud-backup google google_storage key=<client_email>,secret=<path_to_OAuth2.json>

""",
    )
    cred_create_storage_def_parser.add_argument(
        "interface",
        choices=[
            CONFIG_INTERFACE_TYPE_FILESYSTEM,
            CONFIG_INTERFACE_TYPE_LIBCLOUD,
            CONFIG_INTERFACE_TYPE_GOOGLE,
            CONFIG_INTERFACE_TYPE_AZURE,
        ],
        help="""The interface (API) the storage definition should use.

""",
    )
    cred_create_storage_def_parser.add_argument(
        "provider",
        metavar="<libcloud_provider_id>",
        help=f"""The storage provider name. This can be '{CONFIG_INTERFACE_TYPE_FILESYSTEM}' for a local
directory, or a provider supported by the chosen interface. For a cloud provider, if
interface is '{CONFIG_INTERFACE_TYPE_LIBCLOUD}' you will typically specify a libcloud provider string such as
'azure_blobs' or 'google_storage'. For interface '{CONFIG_INTERFACE_TYPE_GOOGLE}' use provider 'google_storage'.
Interface '{CONFIG_INTERFACE_TYPE_AZURE}' allows us of either traditional S3 secret or SAS token as secret. For
interface '{CONFIG_INTERFACE_TYPE_AZURE}' use provider 'azure_blobs'.

""",
    )
    cred_create_storage_def_parser.add_argument(
        "container",
        metavar="<container-name>",
        help=f"""The container name to use. If the name ends with '*', then this parameter acts as a prefix
in the search for an available name which, if found, is then created. A unique
UUID is appended to achieve the goal of finding a name. If a single name without '*'
is specified, it must either already exist or you can use --create-container to
attempt to create that one name.

""",
    )
    cred_create_storage_def_parser.add_argument(
        "driver_params",
        metavar="key=<access_key>,secret=<secret_access_key>[,k=v[,k=v ...]]",
        nargs="?",
        default=None,
        help=f"""The parameters for the API driver. For example, these are passed to libcloud to
create a driver to access the API. Generally, you must specify at least a key and secret, but
you can specify any libcloud driver arguments.

""",
    )
    cred_create_storage_def_parser.add_argument(
        "--create-container",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="""Attempt to create the container. If you do not specify this, you must
use your cloud provider's user interface to create the container.
""",
    )
    cred_create_storage_def_parser.add_argument(
        "--include-iv",
        "--iiv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=f"""The default is --include-iv which stores the encryption initialization vector (IV) in the
clear with the encrypted file in the backup storage location. It is recommended you do not
override the default without which you cannot recover encrypted files should you
fail to properly backup your locally stored backup information (which includes the IVs).
""",
    )
    cred_create_storage_def_parser.add_argument(
        "--secrets-visible",
        "--sv",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=f"""When <driver_params> is not specified on the command line, the user is prompted for input.
This switch causes user input of secrets (i.e., access/secret keys) to be visible while typing.
"""
    )

    #
    # creds delete-storage-def:
    #
    cred_delete_storage_def_parser = subparser_creds.add_parser(
        "delete-storage-def",
        help="Delete a storage definition.",
        parents=[parser_creds_storage_def_specifier, parser_common],
    )
    cred_delete_storage_def_parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Delete without a confirmation prompt.",
    )
    cred_delete_storage_def_parser.add_argument(
        "--delete-backup-info",
        "--dbi",
        action=argparse.BooleanOptionalAction,
        help="""If you specify --no-delete-backup-info (--no-dbi), backup information files
will not be deleted. By default, a storage definition's backup informatiion
files are deleted along with the storage definition itself. If this option
is used without --force, prompting for deleting backup information files
will be skipped (i.e., user only prompted once re storage defintiion).
""",
    )

    #
    # creds export:
    #
    cred_export_cred_parser = subparser_creds.add_parser(
        "export",
        help="Export a storage definition and its secrets to a text file (WARNING: clear text file!).",
        parents=[
            parser_creds_storage_def_specifier,
            parser_credential_filename_positional,
            parser_file_ovewrite,
            parser_common,
        ],
    )

    #
    # creds import:
    #
    cred_import_cred_parser = subparser_creds.add_parser(
        "import",
        help="Import a storage definition and its secrets from a text file.",
        parents=[
            parser_creds_storage_def_specifier,
            parser_credential_filename_positional,
            parser_common,
        ],
    )
    # TODO: Remove if ultimately unused:
    cred_import_cred_parser.add_argument(
        "--create-config",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=f"""Create a {ATBU_USER_DEFAULT_CONFIG_FILE_NAME} configuration if one does not exist.""",
    )
    cred_import_cred_parser.add_argument(
        "--prompt",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=f"""
If --no-prompt is specified, prompts will be skipped. If you specify
to import a backed up configuration, if the same configuration is
already present, it will be overwritten. Ovewriting will wipe out any
existing keys for that storage definition. If keys are different from
the imported configuration, you could lose overwritten keys. It is
recommended you backup configurations before overwriting them by using
'{ATBU_PROGRAM_NAME} creds export ...' first.
""",
    )

    #
    # creds set-password:
    #
    creds_set_password_parser = subparser_creds.add_parser(
        name=CRED_OPERATION_SET_PASSWORD,
        aliases=[CRED_OPERATION_SET_PASSWORD_ALIAS],
        formatter_class=argparse.RawTextHelpFormatter,
        help="Set password for the backup or storage.",
        parents=[parser_creds_storage_def_specifier, parser_common],
    )
    creds_set_password_parser.add_argument(
        "password_type",
        choices=CRED_OPERATION_SET_PASSWORD_TYPES,
        help=f"""What password type or secret to set (i.e., backup password, cloud storage secret, etc.).
    '{CRED_OPERATION_SET_PASSWORD_TYPE_BACKUP}' : Set the password for the backup as a whole. This password is used
        to encrypt both the backup encryption key and/or storage secret.
    '{CRED_OPERATION_SET_PASSWORD_TYPE_STORAGE}' : Set the storage secret for the cloud backup storage definition.
    '{CRED_OPERATION_SET_PASSWORD_TYPE_FILENAME}' : Set the storage secret to an OAuth2 .json file path name.*
    '{CRED_OPERATION_SET_PASSWORD_TYPE_ENVVAR}' : Set the storage secret to an environment variable name that itself
        points to an OAuth2 .json filename.*
    * OAuth2 .json files in format used with a GCS service account are supported.
""",
    )
    creds_set_password_parser.add_argument(
        "password",
        help=f"""The password value to set. If not specified, you will be prompted. The following
are the potential values based on your selection for the above password type argument:
    '{CRED_OPERATION_SET_PASSWORD_TYPE_BACKUP}' : Specify a textual string password used to encrypt the backup encryption key.
    '{CRED_OPERATION_SET_PASSWORD_TYPE_STORAGE}' : Specify a storage secret (i.e., what you copy/paste from cloud portal).
    '{CRED_OPERATION_SET_PASSWORD_TYPE_FILENAME}' : Specify a path to a GCS OAuth2 service account .json file.
    '{CRED_OPERATION_SET_PASSWORD_TYPE_ENVVAR}' : Specify an environment variable that itself points to a GCS OAuth2
        service account .json file.
""",
        nargs="?",
    )
    parser_creds.set_defaults(func=handle_creds)

    #
    # 'recover' subparser.
    #
    parser_recover = subparsers.add_parser(
        "recover",
        parents=[parser_common, parser_credential_filename_optional],
        formatter_class=argparse.RawTextHelpFormatter,
        help="""Recover your backup information files.""",
        description=f"""
This option allows you to recovery backup information from the backup storage, cloud or
local file system. You would do this if your local information has become lost, corrupted
or is otherwise unavailable. You still require your backup's private key, so you should
always make sure you backup (export) your backup's configuration and store it in a safe
place. Without that, you cannot use this recover option.

For more info on exporting your configuration, see '{ATBU_PROGRAM_NAME} creds export ...'
""",
    )
    parser_recover.add_argument(
        "storage_def_cred_cfg",
        metavar="<exported-config-filename> | <storage-def-specifier> [exported-config-filename]",
        nargs="+",
        type=str,
        help=f"""
You can specify the exported config file alone if the recovery
is for a cloud provider storage as the file itself has the
storage definition name, keys etc. needed for recovery.

If you just wish to recover backup information for an already
existing storage def configuration, specify the storage def
name alone, or a path to a filesystem storage definition path.

If you wish to both import credentials and recover backup
information for a filesystem storage, specify the definition's
path and the config filename to import.

The storage definition/credential backup config file is
created by exporting using '{ATBU_PROGRAM_NAME} creds export ...'. For good
measure, you should always backup <home>/{ATBU_DEFAULT_CONFIG_DIR_NAME}/{ATBU_DEFAULT_BACKUP_INFO_SUBDIR}
before performing backup info recovery in case you are uncertain
what you are doing, or otherwise later desire to use or look at
what you had before recovery.
""",
    )
    parser_recover.add_argument(
        "--prompt",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=f"""
If --no-prompt is specified, prompts will be skipped. If you specify
to import a backed up configuration, if the same configuration is
already present, it will be overwritten. Ovewriting will wipe out any
existing keys for that storage definition. If keys are different from
the imported configuration, you could lose overwritten keys. It is
recommended you backup configurations before overwriting them by using
'{ATBU_PROGRAM_NAME} creds export ...' first.
""",
    )
    parser_recover.set_defaults(func=handle_recover)

    #
    # 'decrypt' subparser.
    #
    parser_decrypt = subparsers.add_parser(
        "decrypt",
        formatter_class=argparse.RawTextHelpFormatter,
        parents=[parser_common, parser_credential_filename_optional],
        help="Decrypt storage files directly.",
        description=f"""Decrypt storage files directly. This is generally a command used by someone with technical expertise who may have
a need to decrypt backup storage files without needing to download them. For normal usage/users, this command can
be ignored.

This command might be used in a case where you have the direct raw storage files and you wish to decrypt them. For
example, if you were to download or otherwise get a copy of all your encrypted files stored in the cloud, where
downloading was not required, but you needed to decrypt those files locally in your environment.

Another example might be to sanity check that you can decrypt your storage files without requiring download, perhaps
for prep and confidence that the first example above can be achieved. This might be performed as part of disaster
recovery preparation.

To use this command, you still require your encryption private key so a storage definiton with that key needs to be
configured.

Examples:

    {ATBU_PROGRAM_NAME} decrypt storage:my_cloud_backup c:\\EncryptedFiles c:\\RestoreLocation
        This would use the private encryption key of my_cloud_backup to decrypt files located
        in c:\\EncryptedFiles to c:\\RestoreLocation.
""",
    )
    parser_decrypt.add_argument(
        "private_key_storage_specifier",
        metavar="private-key-storage-specifier",
        type=str,
        help=f"""The storage definition whose private key should be used for decryption.
""",
    )
    parser_decrypt.add_argument(
        "source_files_dir",
        metavar="source-files-dir",
        type=str,
        help=f"""The source directory with optional glob-like pattern specifying the files to decrypt.
If no glob pattern is present, ** is used to select all files. Regardless of the files
found, only those files ending with either {ATBU_FILE_BACKUP_EXTENSION_ENCRYPTED} or {ATBU_FILE_BACKUP_EXTENSION} are considered.""",
    )
    parser_decrypt.add_argument(
        "restore_dir",
        metavar="restore-dir",
        type=str,
        help=f"""The destination directory for the restored files.""",
    )
    parser_decrypt.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="""If specified, allows overwriting already existing destination files.""",
    )
    parser_decrypt.set_defaults(func=handle_decrypt)

    #### decrypt END

    #############################################################################################
    #                           Persistence-related argparse setup                              #
    #############################################################################################

    #
    # Common to subparsers saving/overwriting .atbu/diff databases.
    #

    #
    # Common to update and diff subparsers.
    #
    common_change_detection_type = argparse.ArgumentParser(add_help=False)
    common_change_detection_type.add_argument(
        "--change-detection-type",
        "--cdt",
        choices=CHANGE_DETECTION_CHOICES,
        default=CHANGE_DETECTION_TYPE_DATESIZE,
        help=f"""For operations where digests can be updated, this option specifies the
method to use when determining if a file has changed, where persistent
info needs updating. The options are:
    '{CHANGE_DETECTION_TYPE_DATESIZE}' for file system date or size changes (default).
    '{CHANGE_DETECTION_TYPE_DIGEST}' for digest check (requires time/cpu for re-gen of file digest).
    '{CHANGE_DETECTION_TYPE_FORCE}' will for an update to all files without the need for checks.
""",
    )
    common_update_stale = argparse.ArgumentParser(add_help=False)
    common_update_stale.add_argument(
        "--update-stale",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="""Specifying --no-update-stale disables the default of updating stale
persistent information. If you specify --no-update-stale, the operation
(such as diff) may be performed using stale persisted information which
may or may not be acceptable depending on your situation. Generally, the
default is what you want because it updates stale information when a
change is detected as determined by --change-detection-type.""",
    )

    #
    # Update digests subparser.
    #
    parser_update_digests = subparsers.add_parser(
        "update-digests",
        parents=[common_change_detection_type, parser_common],
        formatter_class=argparse.RawTextHelpFormatter,
        help="Update persistent file information in the specified directories.",
        description=f"""
Generate or update digests for all files in specified directories, placing the persistent
information in sidecar {ATBU_PERSISTENT_INFO_EXTENSION} files.

WARNING: when using the --persist-type option 'per-file' or 'both', this command creates a new
<filename>{ATBU_PERSISTENT_INFO_EXTENSION} file for all encountered files. By contrast, the 'per-dir' option (the default)
creates a single database at the root of the specified location.

""",
    )
    parser_update_digests.add_argument(
        "locations",
        metavar="[per-file:|pf:|per-dir:|pd:|per-both:|pb:]|<location>",
        nargs="+",
        type=str,
        help=f"""One or more local file system directories whose persistent information to update,
each optionally prefixed with the desired file info persistence to use (default is per-dir).
Note, there is a space after per-file:, per-dir:, and any location. For example,
'per-file: c:\\SomeLocationThatShouldUsePerFile'.
""",
    )
    parser_update_digests.set_defaults(func=handle_update_digests)

    #
    # 'diff' subparser.
    #
    parser_diff = subparsers.add_parser(
        "diff",
        formatter_class=argparse.RawTextHelpFormatter,
        help="Perform a diff of persistent file information of two different directories.",
        description="""Perform a compare of two locations, location A and B, each which has persistent information. Either
location A or B can be a directory or a persistent file information database. The diff produces a
result of A less B, meaning files A that are not in B. Optionally, you can choose to have an action
of removing or moving discovered duplicates.
""",
        parents=[parser_common, common_update_stale, common_change_detection_type],
    )
    parser_diff.add_argument(
        "locations",
        metavar="[per-file:|pf:|per-dir:|pd:|per-both:|pb:]|<location>",
        nargs="+",
        type=str,
        help=f"""You must specify this twice, once each for location A and B, optionally prefixing
either with the desired file info persistence to use (default is per-dir).
Note, there is a space after per-file:, per-dir:, and any location. For example,
'per-file: c:\\SomeLocationThatIsUsingPerFile'.
""",
    )
    parser_diff.add_argument(
        "--relpath-match",
        action="store_true",
        default=False,
        help=f"""If specified, files are only considered to match between location A and
location B if their relative paths match. Relative paths are derived by
removing the top-level location path under which a file was found. By
default, relative paths do not need ot match, only the digest between
the two locations must patch.
""",
    )
    parser_diff.add_argument(
        "--action",
        choices=DIFF_COMMAND_CHOICES,
        help=f"""Perform an action, either remove or move, on files in location A for
which there are duplicates in location B.""",
    )
    parser_diff.add_argument(
        "--move-destination",
        "--md",
        type=str,
        help="Directory for destination when moving duplicates as part of diff.",
    )
    parser_diff.add_argument(
        "--whatif",
        action="store_true",
        default=False,
        help="Show what files would be removed but do not actually remove them.",
    )
    parser_diff.set_defaults(func=handle_diff)

    #
    # 'savedb' subparser.
    #
    parser_savedb = subparsers.add_parser(
        "save-db",
        formatter_class=argparse.RawTextHelpFormatter,
        help="Save persistent file information from or more directories into a single json db.",
        description=f"""Save a json database from all persistent information created by the '{ATBU_PROGRAM_NAME} update-digests' command.

Console/logging output includes information about any files detected to have changed since the last
update. Use -v to include console/logging of each path checked. Use -vv to include details for each
path even if not changed since the last update. Details are always output when updates occur, where
using -v or -vv will slow down the command considerably for large directories.

""",
        parents=[parser_common, common_update_stale, common_change_detection_type],
    )
    parser_savedb.add_argument(
        "locations",
        metavar="[per-file:|pf:|per-dir:|pd:|per-both:|pb:]|<location>",
        nargs="+",
        help=f"""The locations whose persistent file information should be placed into a newly
saved database .json file. Optionally prefix any location with the desired
file info persistence to use (default is per-dir). Note, there is a space after
per-file:, per-dir:, and any location. For example,
    'per-file: c:\\SomeLocationThatShouldUsePerFile'.
""",
    )
    parser_savedb.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="When requesting to write a hash db file, overwrite any existing db file.",
    )
    parser_savedb.add_argument(
        "--database",
        "--db",
        type=str,
        required=True,
        help="Path of the persistent file information json database.",
    )
    parser_savedb.set_defaults(func=handle_savedb)

    #
    # 'arrange' subparser.
    #
    parser_arrange = subparsers.add_parser(
        "arrange",
        formatter_class=argparse.RawTextHelpFormatter,
        help="Arrange \"target\" files to match a \"template\" directory's structure.",
        description=rf"""
Manually mirroring drives using copy operations is not uncommon. While manually mirroring can
work with most any drives, and be very low-cost/convenient, there can be issues that arise over
time. One such issue relates to situations where the main current drive has its directories or
file names changed, bringing it out of sync name/structure-wise with the manual mirrors.

Consider an archive of large media items which largely remain static but where one wishes to
change organization strategies over time. In such cases, synchronizing all manual mirrors can
be challenging. The 'arrange' command helps to bring older manual mirrors up to date in structure
and file naming.

Example:

Given two directories that were once manually mirrored, c:\SourceDir and d:\OrigMirrorDir, it is
desired to rearrange (rename items) in d:\OrigMirrorDir so they match c:\SourceDir as closely as
possible for any items in both which match in content precisely (a digest match).

The c:\SourceDir is the called the arrange "template" directory since it acts as a template for
how the new mirror should most optimally look after the arrange operation is complete.

The d:\OrigMirrorDir is called the arramge "target source" directory since it will act as a source
of files used with move operations to create a new third directory on the same drive, d:\NewMirrorDir.

That third directory, d:\NewMirrorDir, is the arrange "target destination" directory since it acts
as a target for move operations from the arrange "target source" in order to try to match d:\NewMirrorDir
as closely as possible to the template c:\SourceDir.

The arrange command only performs intra-drive move operations (aka rename operations) to move
otherwise untouched files to new locations. The goal of 'arrange' is to maximize already existing
mirror copies by arranging them in an order matching c:\SourceDir as closely as possible. This
is performed for any files with a matching digest (precise match).

The command for this arrange operation might be:

    {ATBU_PROGRAM_NAME} arrange --pf -t c:\SourceDir -s d:\OrigMirrorDir -d d:\NewMirrorDir -u d:\undofile.json

Note, specifying an undofile or the --no-undo is required. An undo log file is not currently
used by this tool for undo, but eventually will be. At this time, though, it acts as a log of what
move operations took place as part of the arrange command.

The 'pf:' indicator will cause .atbu sidecar files to be created for all files in c:\SourceDir,
and all files in d:\OrigMirrorDir. (Use 'pd:" if you do not wish to use sidecar files, but keep
in mind sidecar files have benefits making them worth having around for large media items.)

After .atbu files are created, an analysis is performed based on digests of all files in order to begin
move operations from d:\OrigMirrorDir to d:\NewMirrorDir.

After the operation is complete, d:\NewMirrorDir will be a mirror of c:\SourceDir for any files
within d:\OrigMirrorDir which matched in digest (i.e., content). For any files not having a
digest match, the files will remain in d:\OrigMirrorDir for manual review as desired. A manual
mirror copy command can now be used to fully sync c:\SourceDir with d:\NewMirrorDir, but without
re-copying duplicate files that already existed in both directories (both manual mirror locations).

Think of the 'arrange' command as a way of rearranging one drive's directory based on the way some
other drive's directory is structured, based on the assumption both directories have duplicate files
making such rearranging worthwhile to automate. For manually mirrored drives, especially for large
media items, this is most often the case.

The arrange operation will never delete files, or modify the content of files. Arrange only moves
and rename files all on the same drive. AFter an 'arrange' operation completes, all files that were
in d:\OrigMirrorDir will be either in d:\NewMirrorDir (possibly renamed to match the name of an item
in c:\SourceDir), or unmoved in d:\OrigMirrorDir if no c:\SourceDir matches could be found.

Arrange merely seeks to move/rename what is already in d:\OrigMirrorDir to a relative location within
d:\NewMirrorDir matching a relative location for the same item within c:\SoureDir, but only if that
item in c:\SourceDir matches date, size, digest exactly with the d:\OrigMirrorDir item. Note, if the
date, size, digest match, but the name differs, the renamed item takes on the name of the item in
c:\SourceDir, so perhaps this renaming could be considered the most volatile aspsect of arranging.

Hint: Create digests separately from the arrange command by using atbu update-digests. For example,
for large media items, it may be advantageous to use '--per-file' .atbu files. It can take a while
to generate .atbu files and related digests for a large amount of data. To create these in advance,
separate from the arrange operation, use 'atbu update-digests'. If you do not create digests
in advance, the first thing the 'arrange' command will do is implicitly run update-digests.
""",
        parents=[parser_common, common_update_stale, common_change_detection_type],
    )
    parser_arrange.add_argument(
        "--per-dir", "--pd",
        nargs=0,
        action=PerDirFileAction,
        help=f"""
Specify this option before a location that should use per-directory persistence. For example,
specify the following to use per-dir for all directories:
    {ATBU_PROGRAM_NAME} arrange --pd -t C:\\MyTemplate -s D:\\MySource -d D:\\MyDest -u .\\undo-file.json
"""
    )
    parser_arrange.add_argument(
        "--per-file", "--pf",
        nargs=0,
        action=PerDirFileAction,
        help=f"""
Specify this option before a location that should use per-file persistence. For example,
specify the following to use per-file for all directories:
    {ATBU_PROGRAM_NAME} arrange --pf -t C:\\MyTemplate -s D:\\MySource -d D:\\MyDest -u .\\undo-file.json
"""
    )
    parser_arrange.add_argument(
        "-t", "--template-dir", "--td",
        action=LocationAction,
        nargs=1,
        required=True,
        help=f"""The template directory of an arrange operation.

The following is a template directory that uses "per-file" .atbu files which will be generated
when using update-digests or by arrange if they do not already exist:

    {ATBU_PROGRAM_NAME} arrange --pf -t C:\\MyTemplate -s D:\\MySource -d D:\\MyDest -u .\\undo-file.json
""",
    )
    parser_arrange.add_argument(
        "-s", "--source-dir", "--sd",
        action=LocationAction,
        nargs=1,
        required=True,
        help=f"""The target drive source directory (aka target source dir) of an arrange operation.

The following is a target source directory that uses "per-file" .atbu files which will be generated
when using update-digests or by arrange if they do not already exist:

    {ATBU_PROGRAM_NAME} arrange --pf -t C:\\MyTemplate -s D:\\MySource -d D:\\MyDest -u .\\undo-file.json
""",
    )
    parser_arrange.add_argument(
        "-d", "--destination-dir", "--dd",
        action=LocationAction,
        nargs=1,
        required=True,
        help=f"""The target drive destination directory (aka target destination dir) of an arrange operation.

The following is a target destination directory that uses "per-file" .atbu files which will
be generated when using update-digests or by arrange if they do not already exist:

    {ATBU_PROGRAM_NAME} arrange --pf -t C:\\MyTemplate -s D:\\MySource -d D:\\MyDest -u .\\undo-file.json
""",
    )
    parser_arrange.add_argument(
        "--no-undo",
        action="store_true",
        default=False,
        help="""Must be specified if --undofile is not specified. This is a sanity check to ensure",
no undo file is truely desired.
"""
    )
    parser_arrange.add_argument(
        "-u", "--undofile",
        type=str,
        default=None,
        help="""Path to write the arrange undo file which contains information about the operations
performed which can be used to undo the arranging. Note, at this time the undo file is not used
by this tool but eventually will be. For the time being, it can be used by scripting languages
to undo move operations if desired, or to otherwise have a log of the operations which took
place.
""",
    )
    parser_arrange.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="""If specified, existing target destination files can be ovewritten. By default,
move operations will fail if the destination file already exists.""",
    )
    parser_arrange.add_argument(
        "--whatif",
        action="store_true",
        default=False,
        help="Show how files would be arranged without actually arranging them.",
    )
    parser_arrange.set_defaults(func=handle_arrange)

    #############################################################################################
    #                specific help argparse setup (i.e., for atbu help <subject>                #
    #############################################################################################

    parser_help = subparsers.add_parser(
        "help",
        formatter_class=argparse.RawTextHelpFormatter,
        help=f"""Show help on specific subjects:
    '{ATBU_PROGRAM_NAME} help -h' to see available subjects.""",
    )
    parser_help.add_argument(
        "help_subject",
        choices=[k for k in extra_help_subjects],
        nargs=1,
        help=f"""The subject to get detailed help on:
    '{ATBU_PROGRAM_NAME} help specifiers' - get detailed help on storage definition specifiers used by backup/restore commands.
""",
    )

    return parser


def wait_for_debugger_attach(debug_server_port: Union[str, int, list]):
    if debug_server_port is None:
        raise InvalidCommandLineArgument(f"The debugger port must be specified.")
    if isinstance(debug_server_port, list):
        debug_server_port = debug_server_port[0]
    if isinstance(debug_server_port, str):
        try:
            debug_server_port = int(debug_server_port)
        except Exception as ex:
            raise InvalidCommandLineArgument(
                f"Parsing error: "
                f"The value '{debug_server_port}' is an invalid port number."
            ) from ex
    if debug_server_port < 0 or debug_server_port > 65535:
        raise InvalidCommandLineArgument(
            f" The value '{debug_server_port}' is an invalid port number."
        )
    try:
        import debugpy  # pylint: disable=import-outside-toplevel

        debugpy.listen(debug_server_port)
        print(f"Waiting for the debugger to attach via port {debug_server_port}...")
        debugpy.wait_for_client()
        debugpy.breakpoint()
        print(f"Debugger connected.")
    except ModuleNotFoundError as ex:
        raise InvalidStateError(
            f"Cannot 'import debugpy'. Either ensure vscode debugpy is available."
        ) from ex
    except Exception as ex:
        raise InvalidStateError(
            f"Unexpected error. Cannot wait for debugger attach. {exc_to_string(ex)}"
        ) from ex


def process_profile_arguments(args) -> EasyProfile:
    easy_profiler = None
    if args.profile:
        profile_file = None
        profile_stats = args.profile_stats
        if hasattr(args, "profile_file") and args.profile_file is not None:
            if os.path.exists(args.profile_file):
                raise InvalidCommandLineArgument(
                    f"The --profile-file file name must not already exist: "
                    f"file={args.profile_file}"
                )
            profile_file = args.profile_file
        if not profile_stats and profile_file is None:
            raise InvalidCommandLineArgument(
                f"Either one or both of --profile-file / --profile-stats must be specified "
                f"when --profile is specified."
            )
        easy_profiler = EasyProfile(log_stats=profile_stats, profile_file=profile_file)
        easy_profiler.start()
    return easy_profiler


def main(argv=None):
    multiprocessing.set_start_method("spawn")
    global_init()
    initialize_logging_basic()
    # pdb.set_trace()
    logging.info(f"{ATBU_ACRONYM} - v{ATBU_VERSION_STRING}")

    parser = create_argparse()
    args = parser.parse_args(argv)

    if hasattr(args, "debug_server") and args.debug_server is not None:
        wait_for_debugger_attach(args.debug_server)

    if hasattr(args, "help_subject"):
        for requested_help_subject in args.help_subject:
            if requested_help_subject in extra_help_subjects:
                print(extra_help_subjects[requested_help_subject])
                parser.exit(1)
        raise InvalidStateError(
            f"Expected help subject to match those available: {args.help_subject}"
        )

    if hasattr(args, "automated_testing"):
        set_automated_testing_mode(args.automated_testing)

    verbosity_level = 0
    if hasattr(args, "verbosity") and args.verbosity is not None:
        verbosity_level = args.verbosity

    # Instantiate global singleton GlobalHasherDefinitions.
    try:
        GlobalHasherDefinitions([DEFAULT_HASH_ALGORITHM])
    except SingletonAlreadyCreated:
        logging.warning(f"GlobalHasherDefinitions already created.")

    logfile = None
    loglevel = None
    if hasattr(args, "logfile"):
        logfile = args.logfile
    if hasattr(args, "loglevel"):
        loglevel = args.loglevel
    # If no log file specified and user is creating/updating database,
    # automatically place log file side-by-side with db.
    if (
        not logfile
        and hasattr(args, "func")
        and args.func == handle_savedb  # pylint: disable=comparison-with-callable.
        and hasattr(args, "database")  # pylint: disable=W0143
        and args.database is not None
    ):
        logfile = args.database + ".log"

    log_console_detail = False
    if hasattr(args, "log_console_detail") and args.log_console_detail:
        log_console_detail = args.log_console_detail

    exit_code = 1
    try:
        if hasattr(args, 'config_file') and args.config_file is not None:
            if not os.path.isfile(args.config_file):
                raise CredentialSecretFileNotFoundError(
                    f"The credential configuration file was not found: {args.config_file}",
                )
            #
            # Register the storage definition configuration if one is not already present.
            #
            register_storage_def_config_override(
                storage_def_config_path=args.config_file,
                only_if_not_already_present=True,
            )

        if hasattr(args, "func"):
            remove_created_logging_handlers()
            remove_root_stream_handlers()
            initialize_logging(
                logfile=logfile,
                loglevel=loglevel,
                verbosity_level=verbosity_level,
                log_console_detail=log_console_detail,
            )
            debug_argv = argv if argv is not None else sys.argv
            logging.debug(f"argv={'None' if debug_argv is None else ' '.join([*debug_argv])}")

            if get_automated_testing_mode():
                logging.info(f"*** Automated testing mode is enabled. ***")

            if hasattr(args, "yk"):
                if not isinstance(args.yk, bool):
                    raise InvalidStateError(f"--yk should yield a bool option.")
                if args.yk:
                    set_require_yubikey(is_required=args.yk)
                    try:
                        setup_yubikey_infra()
                    except YubiKeyBackendNotAvailableError as ex:
                        logging.error(
                            f"YubiKey Manager is not installed or "
                            f"could not be initialized."
                        )
                        raise

            profile = process_profile_arguments(args)

            exit_code = args.func(args)
            if exit_code is None:
                exit_code = 0

            if profile is not None:
                profile.stop()
                profile = None
        else:
            print(f"I have nothing to do. Try {ATBU_PROGRAM_NAME} -h for help.")
    except AtbuException as err:
        logging.error(f"Failed: {err.message}")
        if get_verbosity_level() > 0:
            logging.error(exc_to_string(err))
            raise
    finally:
        try:
            deinitialize_logging()
        except QueueListenerNotStarted:
            pass
        except Exception as ex:
            print(f"Failure during deinitialize_logging. {exc_to_string(ex)}")
    logging.debug(f"{ATBU_PROGRAM_NAME} exit_code={exit_code}")
    return exit_code


if __name__ == "__main__":
    main()
