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

import argparse
import logging
from typing import Union

from .constants import *
from .exception import (
    AtbuException,
    GlobalContextAlreadySet,
    InvalidCommandLineArgument,
    InvalidStateError,
    QueueListenerNotStarted,
    SingletonAlreadyCreated,
    exc_to_string,
)
from .mp_global import (
    deinitialize_logging,
    global_init,
    initialize_logging_basic,
    initialize_logging,
    remove_created_logging_handlers,
    remove_root_stream_handlers,
)
from ..backup.backup_cmdline import handle_backup
from ..backup.restore import handle_restore, handle_decrypt
from ..backup.verify import handle_verify
from ..backup.recover import handle_recover
from ..backup.list_items import handle_list
from ..backup.creds_cmdline import handle_creds
from .file_info import (
    ATBU_PERSISTENT_INFO_EXTENSION,
    CHANGE_DETECTION_CHOICES,
    CHANGE_DETECTION_TYPE_DATESIZE,
    CHANGE_DETECTION_TYPE_DIGEST,
    CHANGE_DETECTION_TYPE_FORCE,
)
from ..persisted_info.update_digests import handle_update_digests
from ..persisted_info.database import handle_savedb
from ..persisted_info.diff import handle_diff, DIFF_COMMAND_CHOICES
from .hasher import DEFAULT_HASH_ALGORITHM, GlobalHasherDefinitions


class BlankLinesHelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text: str, width: int) -> list[str]:
        return super()._split_lines(text, width) + [""]

    @staticmethod
    def insert_blank_line(parser):
        parser.add_parser("", formatter_class=BlankLinesHelpFormatter, help="")


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

extra_help_subjects = {
    "specifiers": storage_def_specifier_help,
}

console_formatter = logging.Formatter("%(asctime)-15s %(threadName)s %(message)s")


def create_argparse():
    #
    # Root parser
    #
    parser = argparse.ArgumentParser(
        description=f"{ATBU_ACRONUM_U} v{ATBU_VERSION_STRING}",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # For certain operations, this causes the secret to be written in hex to the console.
    # This is for testing purposes. You should never use this option when establishing a
    # private key you are actually going to use.
    # parser.add_argument(
    #     "--show-secrets", action="store_true", default=False, help=argparse.SUPPRESS
    # )

    # Uncomment to allow --debug-server (for use with VS Code pydebug)
    # parser.add_argument(
    #     "--debug-server",
    #     help=argparse.SUPPRESS, #"Activate the debug server to listen on specified port, wait for a client connect."
    #     type=int,
    #     required=False,
    # )

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

    #############################################################################################
    #                                backup-related argparse setup                              #
    #############################################################################################

    #
    # Common credential key-type argument.
    #
    parser_key_type = argparse.ArgumentParser(add_help=False)
    parser_key_type.add_argument(
        "key_type",
        choices=[CRED_KEY_TYPE_STORAGE, CRED_KEY_TYPE_ENCRYPTION],
        help="What key/password to set (i.e., cloud storage, backup encryption, etc.).",
    )

    #
    # Common credential filename argument.
    #
    parser_credential_filename = argparse.ArgumentParser(add_help=False)
    parser_credential_filename.add_argument(
        "filename",
        help="The path to the credential file.",
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

    # Add a subparser to act as a heading with blank lines before/after.
    BlankLinesHelpFormatter.insert_blank_line(subparsers)
    subparsers.add_parser(
        "",
        parents=[parser_common],
        help=f"""Backup/Restore/Verify sub-commands
-----------------------------------
""",
    )
    BlankLinesHelpFormatter.insert_blank_line(subparsers)

    #
    # 'backup' subparser.
    #
    parser_backup = subparsers.add_parser(
        "backup",
        formatter_class=argparse.RawTextHelpFormatter,
        help="Backup files to a local file system folder or the cloud.",
        parents=[parser_common],
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
        help=f"""Enabled by default, reports potential bitrot (aka "sneaky corruption") as an error.
Requires use of --incremental-plus (--ip). Use --no-detect-bitrot (--no-dbr) to
squelch reporting as an error (still reported informationally). Bitrot or so-called
sneaky corruption is detected when a file's date/time and size have remained the
same since the last backup, but the digests are different.""",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser_backup.set_defaults(func=handle_backup)

    #
    # 'restore' subparser.
    #
    parser_restore = subparsers.add_parser(
        "restore",
        formatter_class=argparse.RawTextHelpFormatter,
        parents=[parser_common],
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
        parents=[parser_common],
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
        parents=[parser_common],
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
        "create-storage-def",
        parents=[parser_creds_storage_def_specifier, parser_common],
        formatter_class=argparse.RawTextHelpFormatter,
        help=f"Create a backup storage definition.",
        description=f"""where

    <interface>    <'filesystem','libcloud'|'google'>
    <provider>     <'filesystem'|'azure_blobs'|'google_storage'>
    <container>    The cloud storage container or bucket name.
    <key>          storage key
    <secret>       storage secret
    [,k=v[,k=v ...]] extra parameters as needed: name1=value1,name2=value2,...

Create a storage definition. No spaces allowed as shown. If <secret> evaluates to an
existing filename with a .json extension, the path to that file will be saved as the
crednetial (i.e., an OAuth2 service account file). For some configurations, it may be
easier or necessary to edit the config .json file directly, adding whatever driver
arguments you wish.

Examples:

    {ATBU_PROGRAM_NAME} creds create-storage-def my-cloud-backup libcloud azure_blobs key=<key>,secret=<secret>
    {ATBU_PROGRAM_NAME} creds create-storage-def my-cloud-backup google google_storage key=<client_email>,secret=<path_to_OAuth2.json>

""",
    )
    cred_create_storage_def_parser.add_argument(
        "interface",
        choices=[
            CONFIG_INTERFACE_TYPE_FILESYSTEM,
            CONFIG_INTERFACE_TYPE_LIBCLOUD,
            CONFIG_INTERFACE_TYPE_GOOGLE,
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
'azure_blobs' or 'google_storage'. For provider '{CONFIG_INTERFACE_TYPE_GOOGLE}' use interface 'google_storage'.

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
        metavar="key=<key>,secret=<secret>[,k=v[,k=v ...]]",
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
        "--delete-backup-info", "--dbi",
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
            parser_credential_filename,
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
            parser_credential_filename,
            parser_common,
        ],
    )
    cred_import_cred_parser.add_argument(
        "--create-config",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=f"""Create a {ATBU_DEFAULT_CONFIG_FILE_NAME} configuration if one does not exist.""",
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
    # creds set-username:
    #
    # TODO:
    # creds_set_username_parser = subparser_creds.add_parser(
    #    "set-username",
    #    help="Set the user name (aka 'key')associated the storage secret for specified storage definition.",
    #    parents=[parser_storage_def_specifier, parser_key_type],
    # )

    #
    # creds set-password:
    #
    creds_set_password_parser = subparser_creds.add_parser(
        "set-password",
        help="Set character password for specified storage definition.",
        parents=[parser_creds_storage_def_specifier, parser_key_type, parser_common],
    )
    creds_set_password_parser.add_argument(
        "password",
        help="The password to set.",
        nargs="?",
    )

    #
    # creds set-password-filename:
    #
    creds_set_password_filename_parser = subparser_creds.add_parser(
        "set-password-filename",
        help="Set the storage provider password to the specified file name (i.e., OAuth2 .json file).",
        parents=[parser_creds_storage_def_specifier, parser_common],
    )
    creds_set_password_filename_parser.add_argument(
        "filename",
        help="The file name to set.",
    )

    #
    # creds set-password-envvar:
    #
    creds_set_password_envvar_parser = subparser_creds.add_parser(
        "set-password-envvar",
        help="Set password to environment variable name which will point to a file (i.e., credential .json file).",
        parents=[parser_creds_storage_def_specifier, parser_common],
    )
    creds_set_password_envvar_parser.add_argument(
        "env_var",
        help="The environment variable name to set.",
    )
    parser_creds.set_defaults(func=handle_creds)

    #
    # 'restore' subparser.
    #
    parser_recover = subparsers.add_parser(
        "recover",
        parents=[parser_common],
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
        parents=[parser_common],
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

    # Add a subparser to act as a heading with blank lines before/after.
    BlankLinesHelpFormatter.insert_blank_line(subparsers)
    subparsers.add_parser(
        "",
        parents=[parser_common],
        help=f"""Persistent file information-related sub-commands (unrelated to backup/restore)
------------------------------------------------------------------------------
""",
    )
    BlankLinesHelpFormatter.insert_blank_line(subparsers)

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
'per-file: c:\SomeLocationThatShouldUsePerFile'.
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
'per-file: c:\SomeLocationThatIsUsingPerFile'.
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
        description=f"""Save a json database from all persistent information created by the
'{ATBU_PROGRAM_NAME} update-digests' command.

""",
        parents=[parser_common, common_update_stale, common_change_detection_type],
    )
    parser_savedb.add_argument(
        "locations",
        metavar="[--per-file|--pf|--per-dir|--pd|--per-both|--pb] <location1>",
        nargs="+",
        help=f"""The locations whose persistent file information should be placed
into a newly saved database file.
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

    # Add a subparser to act as a heading with blank lines before/after.
    BlankLinesHelpFormatter.insert_blank_line(subparsers)
    subparsers.add_parser(
        "",
        parents=[parser_common],
        help=f"""Other sub-commands
------------------
""",
    )
    BlankLinesHelpFormatter.insert_blank_line(subparsers)

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


def main(argv=None):
    try:
        global_init()
    except GlobalContextAlreadySet:
        pass
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

    if hasattr(args, "verbosity") and args.verbosity is not None:
        set_verbosity_level(args.verbosity)

    # Instantiate global singleton GlobalHasherDefinitions.
    try:
        GlobalHasherDefinitions([DEFAULT_HASH_ALGORITHM])
    except SingletonAlreadyCreated:
        logging.warning(
            f"GlobalHasherDefinitions already created."
        )  # TODO: determine proper pytest cleanup and/or set is_test variable etc.

    logfile = None
    loglevel = None
    if hasattr(args, "logfile"):
        logfile = args.logfile
    if hasattr(args, "loglevel"):
        loglevel = args.loglevel
    # If no log file specified and user is creating/updating database, automatically place log file side-by-side with db.
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
        if hasattr(args, "func"):
            remove_created_logging_handlers()
            remove_root_stream_handlers()
            initialize_logging(logfile, loglevel, log_console_detail)
            exit_code = args.func(args)
            if exit_code is None:
                exit_code = 0
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
            print(f"Failure during stop_global_queue_listener. {exc_to_string(ex)}")
    logging.debug(f"{ATBU_PROGRAM_NAME} exit_code={exit_code}")
    return exit_code


if __name__ == "__main__":
    main()
