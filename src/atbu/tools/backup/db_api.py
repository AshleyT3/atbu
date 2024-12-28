# Copyright 2022-2024 Ashley R. Thomas
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
r"""Thin SQL DB API layer.
"""
# pylint: disable=missing-class-docstring,missing-function-docstring

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import logging
import os
import re
import sqlite3
from time import perf_counter
from typing import Any, Callable, Union
from pathlib import Path

from atbu.tools.backup.exception import BackupDatabaseSchemaError
from atbu.common.util_helpers import (
    is_platform_path_case_sensitive,
)

from .backup_constants import *
from .backup_entities import *
from .global_hasher import GlobalHasherDefinitions


class DbQueryStrings:

    backups_insert_qry = "INSERT INTO backups (backup_db_id, name) VALUES (?, ?)"

    sbi_select_qry1 = """
SELECT name, backup_start_time_utc 
FROM specific_backups sb
WHERE sb.backups_id = ? AND sb.id = ?
"""

    sbi_select_qry2 = """
SELECT sb.id, sb.backups_id, sb.name, sb.backup_start_time_utc,
sb.object_name_hash_salt, sb.backup_type
FROM specific_backups sb
ORDER BY sb.backup_start_time_utc;
"""

    sbi_select_qry3 = """
SELECT id, name, backup_start_time_utc
FROM specific_backups
ORDER BY backup_start_time_utc DESC
"""

    sbi_insert_qry = """
INSERT INTO specific_backups
(backups_id, name, backup_start_time_utc, object_name_hash_salt, backup_type)
VALUES (?, ?, ?, ?, ?)
"""

    bfi_select_qry1 = """
SELECT
    bfi.id,
    bfi.specific_backup_id,
    bfi.path_value_id, pv.path,
    bfi.discovery_path_value_id, pv2.path discovery_path,
    dv.digest sha256, bfi.is_backing_fi_digest,
    bfi.last_modified, bfi.last_accessed, bfi.lastmodified_stamp,
    bfi.size_in_bytes,
    bfi.is_successful, bfi.exception,
    bfi.ciphertext_hash,
    bfi.encryption_IV,
    bfi.storage_object_name,
    bfi.is_unchanged_since_last,
    bfi.deduplication_option
FROM backup_file_info bfi
INNER JOIN path_values pv ON pv.id = bfi.path_value_id
INNER JOIN path_values pv2 ON bfi.discovery_path_value_id = pv2.id
INNER JOIN backup_file_digests bfd ON bfi.id = bfd.backup_file_info_id
INNER JOIN digest_values dv ON dv.id = bfd.digest_value_id
INNER JOIN specific_backups sb ON sb.id = bfi.specific_backup_id
%(where_expr)s
"""

    @classmethod
    def build_bfi_query(
        cls,
        where_expr="",
    ):
        if len(where_expr) > 0:
            where_expr = f"WHERE {where_expr}"
        return cls.bfi_select_qry1 % {"where_expr": where_expr}

    bfi_phys_backup_dup_list_qry = """
WITH
    dv AS (
        SELECT id, digest
        FROM digest_values
        WHERE digest_values.digest = ? 
    ),
    bfd AS (
        SELECT bfd.digest_value_id, bfd.backup_file_info_id
        FROM backup_file_digests bfd
        WHERE digest_value_id = (SELECT id FROM dv)
    )
SELECT
    bfi.id, bfi.specific_backup_id, bfi.path_value_id, pv.path, 
    bfi.discovery_path_value_id, pv2.path discovery_path, 
    (SELECT digest FROM dv) sha256, bfi.is_backing_fi_digest, 
    bfi.last_modified, bfi.last_accessed, bfi.lastmodified_stamp, 
    bfi.size_in_bytes, bfi.is_successful, bfi.exception, 
    bfi.ciphertext_hash, bfi.encryption_IV, bfi.storage_object_name, 
    bfi.is_unchanged_since_last, bfi.deduplication_option 
FROM backup_file_info bfi
INNER JOIN path_values pv ON bfi.path_value_id = pv.id 
INNER JOIN path_values pv2 ON bfi.discovery_path_value_id = pv2.id 
INNER JOIN specific_backups sb ON sb.id = bfi.specific_backup_id
WHERE bfi.is_unchanged_since_last = 0 AND bfi.id IN (SELECT backup_file_info_id FROM bfd)
ORDER BY sb.backup_start_time_utc DESC;
"""

    bfi_cidx_time_pathdig_qmarks_select = f"""
WITH
    criteria(cli_idx, backup_start_time_utc, path_lc_digest) AS (
        VALUES
            %(qmarks)s
    )
SELECT
    cli_idx,
    bfi.id,
    bfi.specific_backup_id,
    bfi.path_value_id,
    pv.path
FROM backup_file_info bfi 
INNER JOIN path_values pv ON pv.id = bfi.path_value_id
INNER JOIN specific_backups sb ON sb.id = bfi.specific_backup_id 
INNER JOIN criteria c ON c.path_lc_digest=pv.path_lc_digest
WHERE
    bfi.is_successful != 0
    AND bfi.is_unchanged_since_last = 0
    AND sb.backup_start_time_utc <= c.backup_start_time_utc
ORDER BY cli_idx, sb.backup_start_time_utc DESC;
"""

    bfi_digest_qmarks_select = """
WITH
dv AS (
    SELECT id, digest
    FROM digest_values
    WHERE digest_values.digest IN (%(qmarks)s)
),
bfd AS (
    SELECT bfd.digest_value_id, bfd.backup_file_info_id
    FROM backup_file_digests bfd
    WHERE digest_value_id IN (SELECT id FROM dv)
)
SELECT
    bfi.id,
    bfi.last_modified,
    bfi.size_in_bytes,
    path,
    digest,
    sb.backup_start_time_utc
FROM backup_file_info bfi
INNER JOIN bfd ON bfd.backup_file_info_id=bfi.id
INNER JOIN dv ON dv.id=bfd.digest_value_id
INNER JOIN specific_backups sb ON sb.id=bfi.specific_backup_id
INNER JOIN path_values pv ON pv.id=bfi.path_value_id
WHERE
    bfi.id IN (SELECT backup_file_info_id FROM bfd)
    AND bfi.is_unchanged_since_last = 0
    AND bfi.is_successful != 0
ORDER BY sb.backup_start_time_utc DESC;
"""

    bfi_insert_qry = """
INSERT INTO backup_file_info (
specific_backup_id,
path_value_id,
last_modified,
last_accessed,
lastmodified_stamp,
size_in_bytes,
discovery_path_value_id,
is_successful,
exception,
ciphertext_hash,
encryption_IV,
storage_object_name,
is_unchanged_since_last,
is_backing_fi_digest,
deduplication_option
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

    pv_select_qry = """
SELECT pv.id, pv.path, pv.path_lc_digest
FROM path_values pv
WHERE %(column_path_operand)s = ?
%(extra_where_clause)s;
"""

    @classmethod
    def build_pv_query(
        cls,
        column_path_operand: str,
        extra_where_clause: str = "",
    ):
        return cls.pv_select_qry % {
            "column_path_operand": column_path_operand,
            "extra_where_clause": extra_where_clause,
        }

    pv_insert_qry1 = "INSERT INTO path_values (path, path_lc_digest) VALUES (?, ?)"

    pv_select_qry2 = """
WITH
	mat_paths AS (
		SELECT id
		FROM path_values
		WHERE %(column_path_operand)s = ?
	)
SELECT
    bfi.id,
    bfi.specific_backup_id,
    bfi.path_value_id,
    pv.path
FROM backup_file_info bfi 
INNER JOIN path_values pv ON pv.id = bfi.path_value_id
INNER JOIN specific_backups sb ON sb.id = bfi.specific_backup_id 
WHERE pv.id IN (SELECT id FROM mat_paths)
%(extra_where_clause)s
ORDER BY sb.backup_start_time_utc DESC
%(end_clauses)s;
"""

    pv_select_qry3 = "SELECT id, path, path_lc_digest FROM path_values"

    @classmethod
    def _create_path_query(
        cls,
        column_path_operand: str,
        extra_where_clause: str = "",
        end_clauses: str = "",
    ) -> str:
        return cls.pv_select_qry2 % {
            "column_path_operand": column_path_operand,
            "extra_where_clause": extra_where_clause,
            "end_clauses": end_clauses,
        }


    pv_most_recent_qmarks_select_all_time = """
SELECT
    bfi.id,
    bfi.specific_backup_id,
    pv.path,
    bfi.is_successful,
    bfi.is_unchanged_since_last
FROM path_values pv
INNER JOIN backup_file_info bfi ON bfi.path_value_id = pv.id
INNER JOIN specific_backups sb ON sb.id = bfi.specific_backup_id 
WHERE
    pv.id IN (%(qmarks)s)
GROUP BY pv.path
ORDER BY MAX(sb.backup_start_time_utc) DESC;
"""


    pv_most_recent_qmarks_select_as_of_sbi = """
SELECT
    bfi.id,
    bfi.specific_backup_id,
    pv.path,
    bfi.is_successful,
    bfi.is_unchanged_since_last
FROM path_values pv
INNER JOIN backup_file_info bfi ON bfi.path_value_id = pv.id
INNER JOIN specific_backups sb ON sb.id = bfi.specific_backup_id 
WHERE
    pv.id IN (%(qmarks)s)
    AND sb.id = %(qmark_extra1)s
GROUP BY pv.path
ORDER BY MAX(sb.backup_start_time_utc) DESC;
"""


    where_clause_unch_less_equal_time = """
AND bfi.is_unchanged_since_last = 0
AND sb.backup_start_time_utc <= ?
"""

    digest_value_select_qry = (
        "SELECT id from digest_values WHERE (digest_type, digest)=(?, ?)"
    )

    digest_value_insert_qry = (
        "INSERT INTO digest_values (digest_type, digest) VALUES (?, ?)"
    )

    bfd_insert_qry = "INSERT INTO backup_file_digests (backup_file_info_id, digest_value_id) VALUES (?, ?)"


DB_API_SQLITE_CACHE_SIZE = -256000
_PREREAD_DB_FILES = True


def set_db_api_default_cache_size(cache_size):
    global DB_API_SQLITE_CACHE_SIZE
    DB_API_SQLITE_CACHE_SIZE = cache_size


def get_db_api_default_cache_size():
    return DB_API_SQLITE_CACHE_SIZE


def set_preread_db_files(preread_db_files: bool):
    global _PREREAD_DB_FILES
    _PREREAD_DB_FILES = preread_db_files


def is_preread_db_files() -> bool:
    return _PREREAD_DB_FILES


def read_file_to_nowhere(path):
    with open(path, mode="rb") as f:
        while f.read(0x40000):
            pass

RE_CONTAINS_GLOB_CHARS = re.compile(".*[*?[].*")


def has_glob_chars(s) -> bool:
    return RE_CONTAINS_GLOB_CHARS.match(s) is not None


def _fn_pat_to_sql_like_pat(fn_pat: str):
    sql_like_pat = fn_pat.replace("*", "%")
    sql_like_pat = sql_like_pat.replace("?", "_")
    return sql_like_pat


def _fn_pat_to_sql_where_expr(
    column_name: str, fn_pat_start_pos: int, fn_pat: str
) -> tuple[str, str]:
    """Returns tuple (where_expr, expr_pattern), where 'where_expr' is a SQLite expression
    using a operator '=', 'GLOB' or 'LIKE' depending on whether the input fn_pat has a
    pattern (or not), and whether the platform user's expectation is case sensitivity or not.
    The resulting 'where_expr' can be used in a 'WHERE' expression, where it will have one
    qmark which can be satisified using the resulting 'expr_pattern' as an argument.
    """
    if fn_pat_start_pos == 0 and not has_glob_chars(fn_pat) or fn_pat == "*":
        return f"{column_name} = ?", fn_pat
    if is_platform_path_case_sensitive():
        return f"{column_name} GLOB ?", ("?" * fn_pat_start_pos) + fn_pat
    return f"{column_name} LIKE ?", ("_" * fn_pat_start_pos) + _fn_pat_to_sql_like_pat(
        fn_pat
    )


def get_path_for_cmp(path: str) -> str:
    return os.path.normcase(path)


def get_string_digest(s) -> bytes:
    return hashlib.sha256(s.encode("utf-8")).digest()


def get_path_cmp_digest(path) -> bytes:
    return get_string_digest(get_path_for_cmp(path))


def _get_path_query_oper() -> str:
    if is_platform_path_case_sensitive():
        column_path_operand = "path"
    else:
        column_path_operand = "path_lc_digest"
    return column_path_operand


def get_path_query_arg(path) -> Any:
    if is_platform_path_case_sensitive():
        path_related_arg = path
    else:
        path_related_arg = get_path_cmp_digest(path)
    return path_related_arg


class DbInterface:
    def close(self):
        raise NotImplementedError()

    def __enter__(self):
        raise NotImplementedError()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def execute(self, sql: str, parameters=(), /) -> sqlite3.Cursor:
        raise NotImplementedError()

    def executescript(self, sql: str, /) -> sqlite3.Cursor:
        raise NotImplementedError()

    def cursor(self) -> sqlite3.Cursor:
        raise NotImplementedError()

    def commit(self) -> None:
        raise NotImplementedError()

    def rollback(self) -> None:
        raise NotImplementedError()

    def optimize(self) -> None:
        raise NotImplementedError()


class DbCommonOperations:

    @staticmethod
    def get_db_cache_size(db: DbInterface) -> int:
        c = db.execute("PRAGMA cache_size")
        return c.fetchone()[0]

    @staticmethod
    def set_db_cache_size(db: DbInterface, cache_size: int):
        cache_size = int(cache_size)
        c = db.execute(f"PRAGMA cache_size = {cache_size}")
        db.commit()

    @staticmethod
    def get_backup_db_root_info(db: DbInterface):
        c = db.execute("SELECT COUNT(*) FROM backup_db")

        row_count = c.fetchone()[0]
        if row_count == 0 or row_count != 1:
            return row_count, None, None, None

        c = db.execute("SELECT * FROM backup_db")
        rows = c.fetchall()
        if len(rows) != 1:
            return row_count, None, None, None

        db_root_id, db_name, db_ver = rows[0]
        return row_count, db_root_id, db_name, db_ver

    @staticmethod
    def set_backup_db_version(db: DbInterface, db_name: str, db_ver: str):
        (
            row_count,
            db_root_id,
            cur_db_name,
            cur_db_ver,
        ) = DbCommonOperations.get_backup_db_root_info(db)

        if row_count not in [0, 1]:
            raise BackupFileInformationError(
                f"The database root has neither 0 nor 1 rows: row_count={row_count}"
            )

        if row_count == 0:
            c = db.execute(
                "INSERT INTO backup_db (name, version) VALUES (?, ?)",
                (db_name, db_ver),
            )
            return

        if db_name != cur_db_name:
            raise BackupFileInformationError(
                f"The database root name is mismatched: expected={db_name} actual={cur_db_name}"
            )

        logging.debug(f"Setting database version={DbSchema.VERSION}")
        db.execute(
            "UPDATE backup_db SET version = ? WHERE name = ?",
            (
                DbSchema.VERSION,
                db_name,
            ),
        )


def schema_setup_v0_03(db: DbInterface):
    db.execute("ALTER TABLE path_values ADD COLUMN path_lc_digest BLOB;")
    c = db.execute("SELECT * FROM path_values;")
    all_rows = c.fetchall()
    for idx, row in enumerate(all_rows):
        id = row[0]
        if idx % 25000 == 0:
            logging.debug(f"Hashing path #{idx} with id={id}")
        path = row[1]
        path_lc_digest = get_path_cmp_digest(path)
        c.execute(
            f"UPDATE path_values SET path_lc_digest = ? WHERE id = ?",
            (
                path_lc_digest,
                id,
            ),
        )
    addl_sql_cmds = [
        "CREATE INDEX bfi_pvid_idx ON backup_file_info(path_value_id);",
        "CREATE INDEX bfi_backingfidigest_path_dpath_sbi_idx ON backup_file_info(is_backing_fi_digest, path_value_id, discovery_path_value_id, specific_backup_id);",
        "CREATE INDEX bfd_dv_bfi_idx ON backup_file_digests(digest_value_id, backup_file_info_id);",
        "CREATE INDEX digest_values_idx ON digest_values(digest);",
        "CREATE INDEX bfi_is_unchanged_last_idx ON backup_file_info(is_unchanged_since_last);",
        "CREATE INDEX path_lc_digest_idx ON path_values(path_lc_digest);",
    ]
    for sql_cmd in addl_sql_cmds:
        logging.debug(sql_cmd)
        db.execute(sql_cmd)


@dataclass
class DbSchemaSetupStep:
    version: str
    step_work: Union[str, Callable[[DbInterface], None]]


class DbSchema:
    VERSION_DB_NOT_EXIST = "0.00"
    VERSION = BACKUP_INFO_MAJOR_VERSION_STRING

    schema_setup_steps = [
        DbSchemaSetupStep(
            version=VERSION_DB_NOT_EXIST,
            step_work=None,
        ),
        DbSchemaSetupStep(
            version="0.02",
            step_work="""
CREATE TABLE IF NOT EXISTS backup_db (id INTEGER PRIMARY KEY, name TEXT, version TEXT);
CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY, backup_db_id INTEGER NOT NULL, name TEXT, FOREIGN KEY (backup_db_id) REFERENCES backup_db(id));
CREATE TABLE IF NOT EXISTS specific_backups (id INTEGER PRIMARY KEY, backups_id INTEGER NOT NULL, name TEXT, backup_start_time_utc TEXT, object_name_hash_salt TEXT, backup_type TEXT, FOREIGN KEY (backups_id) REFERENCES backups(id));
CREATE TABLE IF NOT EXISTS path_values (id INTEGER PRIMARY KEY, path TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS backup_file_info (id INTEGER PRIMARY KEY, specific_backup_id INTEGER NOT NULL, path_value_id INTEGER NOT NULL, last_modified DOUBLE, last_accessed DOUBLE, lastmodified_stamp TEXT, size_in_bytes INTEGER, discovery_path_value_id INTEGER NOT NULL, is_successful INTEGER, exception TEXT, ciphertext_hash BLOB, encryption_IV BLOB, storage_object_name TEXT, is_unchanged_since_last INTEGER, is_backing_fi_digest INTEGER, deduplication_option TEXT, FOREIGN KEY (specific_backup_id) REFERENCES specific_backups(id), FOREIGN KEY (path_value_id) REFERENCES path_values(id), FOREIGN KEY (discovery_path_value_id) REFERENCES path_values(id));
CREATE TABLE IF NOT EXISTS digest_values (id INTEGER PRIMARY KEY, digest_type TEXT, digest BLOB, UNIQUE (digest_type, digest));
CREATE TABLE IF NOT EXISTS backup_file_digests (backup_file_info_id INTEGER NOT NULL, digest_value_id INTEGER NOT NULL, FOREIGN KEY (backup_file_info_id) REFERENCES backup_file_info(id) FOREIGN KEY (digest_value_id) REFERENCES digest_values(id) PRIMARY KEY (backup_file_info_id, digest_value_id));
CREATE INDEX IF NOT EXISTS bfi_sbi_path_dpath_idx ON backup_file_info(specific_backup_id, path_value_id, discovery_path_value_id);
CREATE TRIGGER IF NOT EXISTS create_backup_file_info_trigger BEFORE INSERT ON backup_file_info WHEN NOT EXISTS (SELECT 1 FROM path_values WHERE id = NEW.path_value_id) OR NOT EXISTS (SELECT 1 FROM path_values WHERE id = NEW.discovery_path_value_id) BEGIN SELECT RAISE(ABORT, 'backup_file_info blocked: requires valid path_value_id, discovery_path_value_id, and must have at least one backup_file_digests association.'); END;
""",
        ),
        DbSchemaSetupStep(version=VERSION, step_work=schema_setup_v0_03),
    ]

    def __init__(self):
        pass

    @staticmethod
    def upgrade_db(db: DbInterface, is_first_time_init: bool) -> bool:
        if is_first_time_init:
            row_count = 0
            db_root_id = None
            cur_db_name = None
            cur_db_ver = None
        else:
            (
                row_count,
                db_root_id,
                cur_db_name,
                cur_db_ver,
            ) = DbCommonOperations.get_backup_db_root_info(db)

        if row_count not in [0, 1]:
            raise BackupFileInformationError(
                f"The database root has neither 0 nor 1 rows: row_count={row_count}"
            )

        if row_count == 1:
            if is_first_time_init:
                raise BackupFileInformationError(
                    f"A database exists when first-time initialization was expected: "
                    f"existing_db_name={cur_db_name} existing_db_ver={cur_db_ver}"
                )

            if BACKUP_DATABASE_DEFAULT_NAME != cur_db_name:
                raise BackupFileInformationError(
                    f"The database root name is mismatched: "
                    f"expected={BACKUP_DATABASE_DEFAULT_NAME} actual={cur_db_name}"
                )

            if cur_db_ver == DbSchema.VERSION:
                return False

            if cur_db_ver is None:
                raise BackupFileInformationError(f"The database version cannot be None")

        if row_count == 0:
            if not is_first_time_init:
                raise BackupFileInformationError(
                    f"An existing initialized database was expected but not found."
                )
            cur_db_ver = DbSchema.VERSION_DB_NOT_EXIST

        is_started = False
        prev_db_ver_step = DbSchema.VERSION_DB_NOT_EXIST

        for schema_setup_step in DbSchema.schema_setup_steps:
            if not is_started and schema_setup_step.version != cur_db_ver:
                prev_db_ver_step = schema_setup_step.version
                continue

            is_started = True

            if schema_setup_step.version == cur_db_ver:
                prev_db_ver_step = schema_setup_step.version
                continue

            logging.info(f"*** WARNING: Do not interrupt this upgrade! ***")
            logging.info(
                f"Running database upgrade from version {prev_db_ver_step} to "
                f"{schema_setup_step.version}"
            )

            try:
                if isinstance(schema_setup_step.step_work, str):
                    logging.debug(
                        f"Executing schema update steps: {schema_setup_step.step_work}"
                    )
                    db.executescript(schema_setup_step.step_work)
                else:
                    logging.debug(
                        f"Calling schema update function: {schema_setup_step.step_work}"
                    )
                    schema_setup_step.step_work(db)

                DbCommonOperations.set_backup_db_version(
                    db=db,
                    db_name=BACKUP_DATABASE_DEFAULT_NAME,
                    db_ver=schema_setup_step.version,
                )
                db.commit()
            except:
                db.rollback()
                raise

            prev_db_ver_step = schema_setup_step.version

        if not is_started:
            raise BackupDatabaseSchemaError(
                f"Database schema updates were expected but did not occur."
            )

        db.optimize()

        _, _, _, post_update_db_ver = DbCommonOperations.get_backup_db_root_info(db)
        if post_update_db_ver != DbSchema.VERSION:
            raise BackupDatabaseSchemaError(
                f"Database version is not current after schema update: "
                f"expected={DbSchema.VERSION} actual={post_update_db_ver}"
            )

        logging.debug(
            f"Database version level check successful: version={DbSchema.VERSION}"
        )
        return True


class DbManagerSqlite3(DbInterface):
    def __init__(self, connection_string):
        if connection_string is None:
            raise ValueError(f"Invalid connection string: {connection_string}")
        self.connection_string = connection_string
        self.conn = sqlite3.connect(connection_string, timeout=15.0, autocommit=False)

    def close(self):
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def execute(self, sql: str, parameters=(), /) -> sqlite3.Cursor:
        return self.conn.execute(sql, parameters)

    def executescript(self, sql: str, /) -> sqlite3.Cursor:
        return self.conn.executescript(sql)

    def cursor(self) -> sqlite3.Cursor:
        pass

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def optimize(self) -> None:
        # c = self.execute("PRAGMA mmap_size = 4000000000;")
        # logging.debug(f"PRAGMA mmap_size: {c.fetchall()[0]}")
        logging.debug(f"Running PRAGMA optimize...")
        self.execute("PRAGMA optimize=0x10002;")


class DbAppApi:
    def __init__(self, db: DbInterface):
        self.db = db
        cs = self.set_db_cache_size(get_db_api_default_cache_size())
        logging.debug(f"DbAppApi SQLite cache size set: cache_size={cs}")

    def close(self):
        if self.db:
            self.db.close()
            self.db = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def execute(self, sql: str, parameters=(), /) -> sqlite3.Cursor:
        return self.db.execute(sql, parameters)

    def executescript(self, sql: str, /) -> sqlite3.Cursor:
        return self.db.executescript(sql)

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def batch_retrieve(
        self,
        query_with_qmarks_spec: str,
        query_batch_parms: list[Any],
        batch_size: int = 1000,
        qmarks_paren_item_count: int = None,
        qmark_extra1_arg = None,
    ) -> list[tuple]:
        result_rows = []
        for i in range(0, len(query_batch_parms), batch_size):
            parms = query_batch_parms[i : i + batch_size]
            if qmarks_paren_item_count is None:
                qmarks = ",".join(["?"] * len(parms))
            else:
                if len(query_batch_parms) % qmarks_paren_item_count != 0:
                    raise ValueError(
                        "query_batch_parms not multiple of query qmark paren count"
                    )
                qmarks = ""
                for i in range(0, len(parms), qmarks_paren_item_count):
                    if i != 0:
                        qmarks += ","
                    qmarks += f"({",".join(["?"] * qmarks_paren_item_count)})"
            this_query = query_with_qmarks_spec % {
                "qmarks": qmarks,
                "qmark_extra1": "?",
            }
            if qmark_extra1_arg is not None:
                parms.append(qmark_extra1_arg)
            c = self.execute(this_query, parms)
            result_rows.extend(c.fetchall())
        return result_rows

    @staticmethod
    def create_api(connection_string: str) -> "DbAppApi":
        return DbAppApi(DbManagerSqlite3(connection_string))

    def set_db_cache_size(self, cache_size: int) -> int:
        DbCommonOperations.set_db_cache_size(db=self.db, cache_size=cache_size)
        return self.get_db_cache_size()

    def get_db_cache_size(self) -> int:
        return DbCommonOperations.get_db_cache_size(db=self.db)

    @lru_cache
    def get_backup_db_root(self) -> tuple[int, str, str]:
        (row_count, db_root_id, db_name, db_ver) = (
            DbCommonOperations.get_backup_db_root_info(db=self.db)
        )

        if row_count != 1:
            # At this time, there's only one top-level backup db per database.
            raise ValueError("backup_db should only have a single row.")

        if db_name != BACKUP_DATABASE_DEFAULT_NAME:
            raise ValueError(
                f"backup_db should be named {BACKUP_DATABASE_DEFAULT_NAME}"
            )

        if db_ver != BACKUP_INFO_MAJOR_VERSION_STRING:
            raise ValueError(
                f"backup_db should be version {BACKUP_INFO_MAJOR_VERSION_STRING}"
            )

        return db_root_id, db_name, db_ver

    @lru_cache
    def get_backups_root(self) -> tuple[int, str]:
        db_root_id, db_name, db_ver = self.get_backup_db_root()
        c = self.db.execute("SELECT * FROM backups WHERE backup_db_id=?", (db_root_id,))
        l = c.fetchall()
        if len(l) != 1:
            raise ValueError(
                f"backups should only have a single row for backup_db_id={db_root_id}."
            )
        r = l[0]
        backups_root_id, _, backups_root_name = r
        return backups_root_id, backups_root_name

    @lru_cache
    def get_specific_backup_info(
        self,
        specific_backup_id: int,
    ) -> tuple[str, str]:
        backups_root_id, backup_base_name = self.get_backups_root()
        c: sqlite3.Cursor = self.db.execute(
            DbQueryStrings.sbi_select_qry1,
            (backups_root_id, specific_backup_id),
        )
        rows = c.fetchall()
        if len(rows) != 1:
            raise ValueError(
                f"there should only be one specific_backup_id={specific_backup_id}."
            )
        return rows[0]  # name, backup_start_time_utc

    def get_specific_backups(
        self,
        is_persistent_db_conn: bool,
        backup_database_file_path: str,
        backup_base_name: str,
        cls_entity: SpecificBackupInformationEntityT = SpecificBackupInformationEntity,
    ) -> dict[str, SpecificBackupInformationEntityT]:
        c: sqlite3.Cursor = self.db.execute(
            DbQueryStrings.sbi_select_qry2,
        )
        result = dict[str, SpecificBackupInformationEntityT]()
        for row in c:
            # pylint: disable=line-too-long
            # (1, 1, 'abc-20240820-064641', '2024-08-20 06:46:41+00:00', b'...', 'full')
            specific_backup_name = row[2]
            result[specific_backup_name] = cls_entity(
                is_persistent_db_conn=is_persistent_db_conn,
                backup_database_file_path=backup_database_file_path,
                backup_base_name=backup_base_name,
                specific_backup_name=specific_backup_name,
                backup_start_time_utc=datetime.fromisoformat(row[3]),
                object_name_hash_salt=row[4],
                backup_type=row[5],
                sbi_id=row[0],
            )
        return result

    def _db_row_to_bfi(
        self,
        row,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> BackupFileInformationEntityT:
        # pylint: disable=line-too-long
        # id, specific_backup_id, path_value_id,                path,  discovery_path_value_id,   discovery path,  digest,     is_backing_fi_digest,       last_modified,      last_accessed,                 lastmodified_stamp, size_in_bytes, is_successful, exception, ciphertext_hash, encryption_IV, storage_object_name, is_unchanged_since_last, deduplication_option
        #  0                   1              2                    3                         4,                5        6                         7                    8                   9                                 10             11         12               13              14             15                   16                       17                    18
        # (3,                  1,             4, 'c:\\somefolder...',                        2,  'c:\\somefolder', b'...',                        0,  1721967555.8663788, 1724136489.4542758, '2024-07-26T04:19:14.866381+00:00',          1024,             1,      None,          b'...',        b'...',          '*.atbake',                       0,                    0,                 None)
        bfi = cls_entity(
            path=row[3],
            discovery_path=row[5],
            sb_id=row[1],
            bfi_id=row[0],
        )
        hash_algorithm_name = GlobalHasherDefinitions().get_primary_hashing_algo_name()
        bfi.digests = {hash_algorithm_name: row[6].hex()}
        bfi.is_backing_fi_digest = row[7] != 0
        bfi.modified_time_posix = row[8]
        bfi.accessed_time_posix = row[9]
        bfi.size_in_bytes = row[11]
        bfi.is_successful = row[12] != 0
        bfi.exception = row[13]
        bfi.ciphertext_hash_during_backup = (
            row[14].hex() if row[14] is not None else None
        )
        bfi.encryption_IV = row[15]
        bfi.is_backup_encrypted = (
            isinstance(bfi.encryption_IV, bytes) and len(bfi.encryption_IV) > 0
        )
        bfi.storage_object_name = row[16]
        bfi.is_unchanged_since_last = row[17] != 0
        bfi.deduplication_option = row[18]
        return bfi

    def get_duplicate_file(
        self,
        deduplication_option: str,
        bfi: BackupFileInformationEntityT,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> BackupFileInformationEntityT:
        dup_list = self.get_phys_backup_dup_list(
            primary_digest=bfi.primary_digest,
            cls_entity=cls_entity,
        )
        return find_duplicate_in_list(
            deduplication_option=deduplication_option,
            bfi=bfi,
            dup_list=dup_list,
        )

    def resolve_backing_fi(
        self,
        bfi: BackupFileInformationEntity,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ):
        if bfi.backing_fi is not None:
            raise InvalidStateError("bfi.backing_fi must not be set.")
        if bfi.is_failed:
            return
        if bfi.is_successful:
            return
        if not bfi.is_unchanged_since_last:
            return
        if bfi.deduplication_option is not None:
            s = perf_counter()
            disc_backing_fi = self.get_duplicate_file(
                deduplication_option=bfi.deduplication_option,
                bfi=bfi,
                cls_entity=cls_entity,
            )
            logging.debug(
                f"resolve_backing_fi: "
                f"get_duplicate_file: {perf_counter()-s:.3f} seconds."
            )
        else:
            s = perf_counter()
            disc_backing_fi = self.get_most_recent_backing_bfi_for_path(
                specific_backup_id=bfi.sb_id,
                path_to_find=bfi.path,
                cls_entity=cls_entity,
            )
            logging.debug(
                f"resolve_backing_fi: "
                f"get_most_recent_backing_bfi_for_path: {perf_counter()-s:.3f} seconds."
            )
        bfi.backing_fi = disc_backing_fi
        validate_bfi_backing_information(bfi=bfi)

    def get_specific_backup_file_info(
        self,
        specific_backup_id: int,
        resolve_backing_fi: bool = False,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> list[BackupFileInformationEntityT]:
        specific_backup_name, _ = self.get_specific_backup_info(
            specific_backup_id=specific_backup_id
        )
        logging.debug(
            f"Querying for bfi={specific_backup_id} name={specific_backup_name}"
        )
        query_str = DbQueryStrings.build_bfi_query(
            where_expr=" bfi.specific_backup_id = ? "
        )
        c: sqlite3.Cursor = self.db.execute(query_str, (specific_backup_id,))
        result = []
        logging.debug(
            f"Processing rows for bfi={specific_backup_id} name={specific_backup_name}"
        )
        for row in c:
            bfi = self._db_row_to_bfi(row, cls_entity)
            if resolve_backing_fi:
                self.resolve_backing_fi(bfi=bfi, cls_entity=cls_entity)
            result.append(bfi)
        logging.debug(
            f"Finished loading bfi={specific_backup_id} name={specific_backup_name}"
        )
        return result

    def _create_path_query_simple(
        self,
        path_to_find: str,
        extra_where_clause: str = "",
    ) -> tuple[Any, str]:
        column_path_operand = _get_path_query_oper()
        path_related_arg = get_path_query_arg(path=path_to_find)
        return path_related_arg, DbQueryStrings.build_pv_query(
            column_path_operand=column_path_operand,
            extra_where_clause=extra_where_clause,
        )

    def find_path_value_id(
        self,
        path_to_find: str,
    ) -> tuple[int, str, bytes]:
        """Returns path_values tuple (id, path, path_lc_digest) for matching path."""
        path_related_arg, query_str = self._create_path_query_simple(
            path_to_find=path_to_find
        )
        logging.debug(f"find_path_value_id: {path_to_find}")
        c: sqlite3.Cursor = self.db.execute(
            query_str,
            (path_related_arg,),
        )
        path_to_find = get_path_for_cmp(path_to_find)
        for row in c:
            if path_to_find == get_path_for_cmp(row[1]):
                return row[0], row[1], row[2]
        return None, None, None

    def insert_path_value(self, path) -> tuple[int, str, bytes]:
        path_lc_digest = get_path_cmp_digest(path)
        c = self.db.execute(
            DbQueryStrings.pv_insert_qry1,
            (path, path_lc_digest),
        )
        return c.lastrowid, path, path_lc_digest

    def find_path_value_id_insert(self, path_to_find) -> tuple[int, str, bytes]:
        path_value_id, path, path_lc_digest = self.find_path_value_id(
            path_to_find=path_to_find
        )
        if path_value_id is None:
            return self.insert_path_value(path_to_find)
        return path_value_id, path, path_lc_digest

    def _find_bfi_row_matching_path(self, bfi_rows, path_to_find) -> Any:
        path_to_find = get_path_for_cmp(path_to_find)
        for row in bfi_rows:
            path: str = row[3]
            if path_to_find == get_path_for_cmp(path):
                return row
        return None

    def _query_to_find_path_rows(
        self,
        path_to_find: str,
        extra_where_clause: str = "",
        extra_where_clause_args=None,
        end_clauses: str = "",
    ) -> Any:
        path_related_arg = get_path_query_arg(
            path=path_to_find,
        )
        query_str = DbQueryStrings._create_path_query(
            column_path_operand=_get_path_query_oper(),
            extra_where_clause=extra_where_clause,
            end_clauses=end_clauses,
        )

        if extra_where_clause_args is None:
            args = (path_related_arg,)
        else:
            args = (
                path_related_arg,
                extra_where_clause_args,
            )

        c: sqlite3.Cursor = self.db.execute(
            query_str,
            args,
        )

        return self._find_bfi_row_matching_path(c, path_to_find)

    def get_most_recent_backing_bfi_for_path(
        self,
        specific_backup_id: int,
        path_to_find: str,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> BackupFileInformationEntityT:
        logging.debug(f"get_most_recent_backup_file_info_for_path: {path_to_find}")
        _, backup_start_time_utc = self.get_specific_backup_info(
            specific_backup_id=specific_backup_id
        )

        bfi = self.get_most_recent_backup_of_path(
            path_to_find=path_to_find,
            extra_where_clause=DbQueryStrings.where_clause_unch_less_equal_time,
            extra_where_clause_args=backup_start_time_utc,
            resolve_backing=False,
            cls_entity=cls_entity,
        )

        return bfi

    def get_most_recent_backup_of_path(
        self,
        path_to_find: str,
        extra_where_clause: str = "",
        extra_where_clause_args=None,
        resolve_backing: bool = True,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> BackupFileInformationEntityT:
        logging.debug(f"get_most_recent_backup_file_info_for_path: {path_to_find}")

        if extra_where_clause_args is not None and extra_where_clause.find("?") == -1:
            raise ValueError(f"Expecting a qmark style placeholder question mark.")

        s = perf_counter()
        row_found = self._query_to_find_path_rows(
            path_to_find=path_to_find,
            extra_where_clause=extra_where_clause,
            extra_where_clause_args=extra_where_clause_args,
        )
        logging.debug(
            f"get_most_recent_backup_of_path: "
            f"_query_to_find_path_rows: {perf_counter()-s:.3f} seconds."
        )

        if not row_found:
            return None

        s = perf_counter()
        bfi_id = row_found[0]
        bfi_query = DbQueryStrings.build_bfi_query(where_expr=" bfi.id = ? ")
        c = self.db.execute(bfi_query, (bfi_id,))
        logging.debug(
            f"get_most_recent_backup_of_path: "
            f"build_bfi_query: {perf_counter()-s:.3f} seconds."
        )

        row_found = c.fetchone()
        logging.info(f"build_bfi_query2: {perf_counter()-s:.3f}")

        if row_found is None:
            raise BackupFileInformationError(
                f"backup_file_info with id={bfi_id} must exist but was not found."
            )

        bfi = self._db_row_to_bfi(row_found, cls_entity)
        if resolve_backing:
            s = perf_counter()
            self.resolve_backing_fi(bfi=bfi, cls_entity=cls_entity)
            logging.debug(
                f"get_most_recent_backup_of_path: "
                f"resolve_backing_fi: {perf_counter()-s:.3f} seconds."
            )
        return bfi

    def get_phys_backup_dup_list(
        self,
        primary_digest: str,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> list[BackupFileInformationEntityT]:

        c: sqlite3.Cursor = self.db.execute(
            DbQueryStrings.bfi_phys_backup_dup_list_qry,
            (bytes.fromhex(primary_digest),),
        )

        dup_list = []
        for row in c:
            bfi = self._db_row_to_bfi(row, cls_entity=cls_entity)
            dup_list.append(bfi)
        return dup_list

    def get_bfi_matching_fn_pat(
        self,
        specific_backup_id: int,
        fn_pat: str,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> list[BackupFileInformationEntityT]:
        sql_args = (specific_backup_id,)
        fn_pat = fn_pat.strip()
        where_expr = ""
        if fn_pat != "*":
            # This where_expr has one qmark.
            where_expr, expr_pattern = _fn_pat_to_sql_where_expr(
                "pv.path",
                0,
                fn_pat,
            )
            where_expr = f"AND {where_expr} "
            sql_args = (
                specific_backup_id,
                expr_pattern,
            )

        query_str = DbQueryStrings.build_bfi_query(
            where_expr=(
                " bfi.specific_backup_id = ? " f" {where_expr} " "ORDER BY pv.path; "
            )
        )
        c: sqlite3.Cursor = self.db.execute(
            query_str,
            sql_args,
        )

        bfi_list: list[BackupFileInformationEntityT] = []
        for row in c:
            bfi = self._db_row_to_bfi(row, cls_entity)
            bfi_list.append(bfi)

        bir = BackupInfoRetriever(db_api=self, cls_entity=cls_entity)
        bir.populate_backup_info(
            backup_file_list=bfi_list,
            sb_id=specific_backup_id,
        )

        bfi_list = [b.most_recent_backup_bfi for b in bir.retrieved_bir]
        bfi_list.sort(key=lambda b: b.nc_path)

        return bfi_list

    def insert_specific_backup(
        self,
        parent_backups_id,
        backup_specific_name,
        backup_start_time_utc,
        object_name_hash_salt,
        backup_type,
    ) -> int:
        c = self.db.execute(
            DbQueryStrings.sbi_insert_qry,
            (
                parent_backups_id,
                backup_specific_name,
                backup_start_time_utc,
                object_name_hash_salt,
                backup_type,
            ),
        )
        return c.lastrowid

    def insert_digest_value(self, digest_type, digest):
        if isinstance(digest, str):
            digest = bytes.fromhex(digest)
        if not isinstance(digest, bytes):
            raise ValueError(
                f"digest must be bytes or str convertable to bytes: {type(digest)}"
            )
        c = self.db.execute(
            DbQueryStrings.digest_value_insert_qry,
            (
                digest_type,
                digest,
            ),
        )
        return c.lastrowid

    def get_digest_value(self, digest_type, digest):
        if isinstance(digest, str):
            digest = bytes.fromhex(digest)
        if not isinstance(digest, bytes):
            raise ValueError(
                f"digest must be bytes or str convertable to bytes: {type(digest)}"
            )
        c = self.db.execute(
            DbQueryStrings.digest_value_select_qry,
            (digest_type, digest),
        )
        l = c.fetchall()
        if len(l) > 1:
            raise ValueError(
                f"digest_values should never return more than a single: "
                f"count={len(l)} digest_type={digest_type} digest={digest.hex()}"
            )
        row = l[0] if len(l) == 1 else None
        return row[0] if row else None

    def get_digest_value_insert(self, digest_type, digest):
        digest_value_id = self.get_digest_value(digest_type, digest)
        if digest_value_id is None:
            digest_value_id = self.insert_digest_value(digest_type, digest)
        return digest_value_id

    def insert_backup_file_digest(self, backup_file_info_id, digest_value_id):
        c = self.db.execute(
            DbQueryStrings.bfd_insert_qry,
            (
                backup_file_info_id,
                digest_value_id,
            ),
        )
        return c.lastrowid

    def insert_specific_backup_file_info(
        self,
        specific_backup_id: int,
        path: str,
        last_modified: str,
        last_accessed: str,
        lastmodified_stamp: str,
        size_in_bytes: int,
        digests: dict,
        discovery_path: str,
        is_successful: bool,
        exception: str,
        ciphertext_hash: str,
        encryption_iv: str,
        storage_object_name: str,
        is_unchanged_since_last: bool,
        is_backing_fi_digest: bool,
        deduplication_option: str,
    ) -> int:

        path_value_id, _, _ = self.find_path_value_id_insert(path)
        discovery_path_value_id, _, _ = self.find_path_value_id_insert(discovery_path)
        if isinstance(ciphertext_hash, str):
            ciphertext_hash = bytes.fromhex(ciphertext_hash)
        if isinstance(encryption_iv, str):
            encryption_iv = bytes.fromhex(encryption_iv)

        values = (
            specific_backup_id,
            path_value_id,
            last_modified,
            last_accessed,
            lastmodified_stamp,
            size_in_bytes,
            discovery_path_value_id,
            is_successful,
            exception,
            ciphertext_hash,
            encryption_iv,
            storage_object_name,
            is_unchanged_since_last,
            is_backing_fi_digest,
            deduplication_option,
        )
        c = self.db.execute(
            DbQueryStrings.bfi_insert_qry,
            values,
        )

        backup_file_info_id = c.lastrowid

        for digest_type, digest in digests.items():
            digest_values_id = self.get_digest_value_insert(
                digest_type=digest_type,
                digest=digest,
            )
            self.insert_backup_file_digest(backup_file_info_id, digest_values_id)

        return backup_file_info_id

    def _create_new_db(self, backup_base_name):
        DbSchema.upgrade_db(db=self.db, is_first_time_init=True)
        row_count, db_root_id, db_name, db_ver = (
            DbCommonOperations.get_backup_db_root_info(self.db)
        )
        c = self.db.execute(
            DbQueryStrings.backups_insert_qry,
            (db_root_id, backup_base_name),
        )
        self.db.commit()

    @staticmethod
    def create_new_db(
        new_db_file_path: Union[str, Path],
        backup_base_name: str,
        overwrite: bool = False,
    ) -> "DbAppApi":
        if os.path.exists(new_db_file_path):
            if not overwrite:
                raise FileExistsError(
                    f"Database filename must not exist: {new_db_file_path}"
                )
            os.unlink(new_db_file_path)
        try:
            db_api = None
            db_api = DbAppApi.create_api(str(new_db_file_path))
            db_api._create_new_db(backup_base_name=backup_base_name)
            return db_api
        except:
            if db_api:
                db_api.close()
            raise

    def preread_db_file(self):
        read_file_to_nowhere(self.db.connection_string)

    has_preread_occurred: bool = False

    @staticmethod
    def open_db(db_file_path: Union[str, Path]) -> "DbAppApi":
        if not os.path.exists(db_file_path):
            raise FileNotFoundError(f"Database file not found: {db_file_path}")
        try:
            db_api = DbAppApi.create_api(str(db_file_path))
            if not DbSchema.upgrade_db(db=db_api.db, is_first_time_init=False):
                db_api.db.optimize()

            if is_preread_db_files() and not DbAppApi.has_preread_occurred:
                DbAppApi.has_preread_occurred = True
                logging.info(f"Reading the database: {db_api.db.connection_string}...")
                start_read = perf_counter()
                db_api.preread_db_file()
                logging.info(
                    f"Reading the database completed in {perf_counter()-start_read:.3f} seconds."
                )
            return db_api
        except:
            if db_api:
                db_api.close()
            raise


@dataclass
class BackupInfoRetrieverResult:
    cur_bfi: BackupFileInformationEntityT
    most_recent_backup_bfi: BackupFileInformationEntityT
    is_for_backup: bool


@dataclass
class _path_value_info:
    id: int
    path: str
    path_lc_digest: bytes


@dataclass
class _specific_backup_info:
    id: int
    name: str
    backup_start_time_utc: str


@dataclass
class _backing_attrs:
    bfi_id: int
    last_modified: float = None
    size_in_bytes: int = None
    path: str = None
    primary_digest: bytes = None,
    backup_start_time_utc: str = None


@dataclass
class _bfi_last_backup_by_path:
    bfi_id: int
    bfi_sbid: int
    bfi_path: str
    bfi_is_successful: bool
    bfi_is_unchanged_since_last: bool
    bfi_most_recent_backup: BackupFileInformationEntityT = None
    backing_ims: _backing_attrs = None
    is_ims_backing: bool = False


@dataclass
class _backup_prep_info:
    cur_bfi: BackupFileInformationEntityT
    pvi: _path_value_info
    lbi_by_path: _bfi_last_backup_by_path = None


class BackupInfoRetriever:

    def __init__(
        self,
        db_api: DbAppApi,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity
    ):
        self.db_api = db_api
        self.sb_id = None
        self.sb_backup_start_time_utc = None
        self.retrieved_bir: list[BackupInfoRetrieverResult] = None
        self.retrieved_bfi: dict[BackupFileInformationEntityT, BackupInfoRetrieverResult] = None
        self._cls = cls_entity

    @property
    def is_populated(self):
        return self.retrieved_bir is not None and self.retrieved_bfi is not None

    def get_cached_most_recent_backup_of_path(
        self,
        path: str,
    ) -> BackupFileInformationEntityT:
        if self.retrieved_bfi is None:
            return None
        bir = self.retrieved_bfi.get(os.path.normcase(path))
        if bir is None:
            return None
        return bir.most_recent_backup_bfi

    def populate_backup_info(
        self,
        backup_file_list: list[BackupFileInformationEntityT],
        sb_id: int = None,
    ):
        self.sb_id = sb_id
        if self.sb_id is not None:
            for b in backup_file_list:
                if b.sb_id != self.sb_id:
                    raise InvalidStateError(
                        f"populate_backup_info: "
                        f"specific sb_id requires all bfi to have same sb_id. "
                        f"caller_sb_id={sb_id} "
                        f"invalid_sb_id={b.sb_id} "
                        f"bfi_id={b.bfi_id} "
                        f"path={b.path}"
                    )

            _, self.sb_backup_start_time_utc = self.db_api.get_specific_backup_info(
                specific_backup_id=self.sb_id
            )


        self.retrieved_bir = self._retrieve_backup_info(
            backup_file_list=backup_file_list,
        )
        self.retrieved_bfi = {}
        for bir in self.retrieved_bir:
            nc_path = os.path.normcase(bir.cur_bfi.path)
            if self.retrieved_bfi.get(nc_path) is not None:
                raise InvalidStateError(
                    "Two BackupInfoRetrieverResult instances for a single path is unexpected."
                )
            self.retrieved_bfi[nc_path] = bir

    def _retrieve_most_recent(
        self,
        bfi_list: list[BackupFileInformationEntityT],
    ) -> tuple[list[_backup_prep_info], list[BackupFileInformationEntityT]]:

        self.p_to_pvi, self.pld_to_pvi_list = self._create_path_lookup_dicts()
        self.sbid_to_sb_info = self._create_sbi_lookup_dict()

        bpi_list, not_found_for_backup_fi = self._assoc_existing_pv_info(
            cur_fi_list=bfi_list,
        )

        if len(bpi_list) <= 0:
            return bpi_list, not_found_for_backup_fi

        self._assoc_bpi_most_recent_path(bpi_list=bpi_list)
        for idx in range(len(bpi_list) - 1, -1, -1):
            bpi = bpi_list[idx]
            if (
                not bpi.lbi_by_path.bfi_is_successful
                and not bpi.lbi_by_path.bfi_is_unchanged_since_last
            ):
                not_found_for_backup_fi.append(bpi_list.pop())
                continue

        logging.debug(
            f"_retrieve_most_recent: "
            f"backup_file_list={len(bfi_list)} "
            f"hist_found={len(bpi_list)} "
            f"hist_not_found={len(not_found_for_backup_fi)}"
        )

        bpi_list.sort(key=lambda b: b.lbi_by_path.bfi_id)
        last_backup_bfi_ids = [b.lbi_by_path.bfi_id for b in bpi_list]
        last_backup_bfi_list = self._retrieve_bfi_complete(
            bfi_ids=last_backup_bfi_ids,
        )

        last_backup_bfi_list.sort(key=lambda b: b.bfi_id)
        for idx in range(len(last_backup_bfi_list)):
            if bpi_list[idx].lbi_by_path.bfi_id != last_backup_bfi_list[idx].bfi_id:
                raise InvalidStateError(
                    "_retrieve_most_recent: bfi_id mismatch unexpected"
                )
            bpi_list[idx].lbi_by_path.bfi_most_recent_backup = last_backup_bfi_list[idx]

        logging.debug(
            f"_retrieve_most_recent: "
            f"bfi_ids={len(last_backup_bfi_ids)} "
            f"results={len(last_backup_bfi_list)} "
            f"found_fi_pv_row_lastbk={len(bpi_list)}"
        )
        self._resolve_most_recent_bfi_backing_fi(bpi_list=bpi_list)

        for idx, bpi in enumerate(bpi_list):

            if idx % 500 == 0:
                logging.debug(
                    f"_retrieve_most_recent: "
                    f"final check in progress: idx={idx} path={bpi.cur_bfi.path}"
                )
            if bpi.cur_bfi.backing_fi is not None:
                raise InvalidStateError(
                    "_retrieve_most_recent: backing_fi must be None."
                )
            if bpi.lbi_by_path.bfi_most_recent_backup is None:
                raise InvalidStateError(
                    "_retrieve_most_recent: bfi_most_recent_backup must be valid."
                )
            if (bpi.lbi_by_path.bfi_most_recent_backup.backing_fi is None
                and not bpi.lbi_by_path.bfi_most_recent_backup.is_successful
            ):
                raise InvalidStateError(
                    "_retrieve_most_recent: most recent must have backing_fi or be successful."
                )
            if (
                bpi.lbi_by_path.bfi_most_recent_backup.deduplication_option is None
                and get_path_for_cmp(bpi.cur_bfi.path) != get_path_for_cmp(
                    bpi.lbi_by_path.bfi_most_recent_backup.path)
            ):
                raise InvalidStateError(
                    "_retrieve_most_recent: non-deduplication paths must match."
                )

        return bpi_list, not_found_for_backup_fi


    def _retrieve_backup_info(
        self,
        backup_file_list: list[BackupFileInformationEntityT],
    ) -> list[BackupInfoRetrieverResult]:
        start_all = perf_counter()

        bpi_list, not_found_for_backup_fi = self._retrieve_most_recent(
            bfi_list=backup_file_list,
        )

        results: list[BackupInfoRetrieverResult] = []
        for bfi in not_found_for_backup_fi:
            results.append(
                BackupInfoRetrieverResult(
                    cur_bfi=bfi,
                    most_recent_backup_bfi=None,
                    is_for_backup=True,
                )
            )

        for bpi in bpi_list:
            results.append(
                BackupInfoRetrieverResult(
                    cur_bfi=bpi.cur_bfi,
                    most_recent_backup_bfi=bpi.lbi_by_path.bfi_most_recent_backup,
                    is_for_backup=is_bfi_modiifed(
                        cur_bfi=bpi.cur_bfi,
                        most_recent_backup_bfi=bpi.lbi_by_path.bfi_most_recent_backup,
                        check_digests=False,
                    )
                )
            )

        results.sort(key=lambda r: r.cur_bfi.nc_path)

        logging.debug(f"retrieve_backup_info: total time: {perf_counter()-start_all:.3f}")

        return results

    def _create_path_lookup_dicts(
        self,
    ) -> tuple[dict[str, _path_value_info], dict[str, list[_path_value_info]]]:
        pc_start = perf_counter()
        c_pv = self.db_api.execute(DbQueryStrings.pv_select_qry3)
        l_pv = c_pv.fetchall()
        p_to_pv = {}
        pld_to_pv = defaultdict(list[_path_value_info])
        for r_pv in l_pv:
            pvi = _path_value_info(*r_pv)
            p_to_pv[r_pv[1]] = pvi
            pld_to_pv[r_pv[2]].append(pvi)
        logging.debug(f"_create_path_lookup_dicts: path query time: {perf_counter()-pc_start:.3f}")
        return p_to_pv, pld_to_pv

    def _create_sbi_lookup_dict(
        self,
    ) -> list[_specific_backup_info]:
        sbid_to_sb_info = defaultdict(list[_specific_backup_info])
        c_sb = self.db_api.execute(DbQueryStrings.sbi_select_qry3)
        for r_sb in c_sb.fetchall():
            sbid_to_sb_info[r_sb[0]] = _specific_backup_info(*r_sb)
        return sbid_to_sb_info

    def _assoc_existing_pv_info(
        self,
        cur_fi_list: list[BackupFileInformationEntityT],
    ) -> tuple[list[_backup_prep_info], list[BackupFileInformationEntityT]]:
        found = []
        not_found = []
        for i, cur_fi in enumerate(cur_fi_list):
            fi_path_for_cmp = get_path_for_cmp(cur_fi.path)
            path_related_arg = get_path_query_arg(path=cur_fi.path)
            assert isinstance(path_related_arg, bytes)  # TBD impl

            pv_list_found = self.pld_to_pvi_list.get(path_related_arg)
            pv_found = None
            if pv_list_found is not None:
                for pv in pv_list_found:
                    if get_path_for_cmp(pv.path) == fi_path_for_cmp:
                        pv_found = pv
                        break

            if pv_found is None:
                not_found.append(cur_fi)
                continue

            found.append(
                _backup_prep_info(
                    cur_bfi=cur_fi,
                    pvi=pv_found,
                )
            )

        return found, not_found

    def _assoc_bpi_most_recent_path(
        self, bpi_list: list[_backup_prep_info]
    ):
        if not bpi_list:
            return

        if self.sb_id is None:
            query_str = DbQueryStrings.pv_most_recent_qmarks_select_all_time
            qmark_extra1_arg = None
        else:
            query_str = DbQueryStrings.pv_most_recent_qmarks_select_as_of_sbi
            qmark_extra1_arg = self.sb_id

        bfi_ids = [bpi.pvi.id for bpi in bpi_list]
        bfi_ids.sort()
        bfi_rows = self.db_api.batch_retrieve(
            query_with_qmarks_spec=query_str,
            query_batch_parms=bfi_ids,
            qmark_extra1_arg=qmark_extra1_arg,
        )

        lastbk_dict = defaultdict(list[_bfi_last_backup_by_path])
        for bfi_row in bfi_rows:
            bfi_lastbk_by_path = _bfi_last_backup_by_path(*bfi_row)
            lastbk_dict[get_path_for_cmp(bfi_lastbk_by_path.bfi_path)].append(
                bfi_lastbk_by_path,
            )

        for bpi in bpi_list:

            cur_fi = bpi.cur_bfi
            k = get_path_for_cmp(cur_fi.path)

            lastbk_list = lastbk_dict.get(k)
            if lastbk_list is None or len(lastbk_list) == 0:
                raise InvalidStateError(
                    "_assoc_bpi_most_recent_path: at least one match for each bpi must exist."
                )

            bfi_last_backup = lastbk_list[0]
            if not bfi_last_backup:
                raise InvalidStateError(
                    "_assoc_bpi_most_recent_path: "
                    "caller supplied bpi must resolve to existing paths."
                )
            if k != get_path_for_cmp(bfi_last_backup.bfi_path):
                raise InvalidStateError("_assoc_bpi_most_recent_path: path check must match.")

            bpi.lbi_by_path = bfi_last_backup

    def _retrieve_bfi_complete(
        self,
        bfi_ids: list[int],
        batch_size: int = 1000,
    ) -> list[BackupFileInformationEntityT]:
        query_with_qmarks_spec = DbQueryStrings.build_bfi_query(
            where_expr=f"bfi.id IN (%(qmarks)s)"
        )
        results_bfi_rows = self.db_api.batch_retrieve(
            query_with_qmarks_spec=query_with_qmarks_spec,
            query_batch_parms=bfi_ids,
            batch_size=batch_size
        )

        bfi_list = []
        for i, bfi_row in enumerate(results_bfi_rows):
            if i % 1000 == 0:
                logging.debug(f"_retrieve_bfi_complete: {i}: row to bfi instance {bfi_row[0]}")
            bfi_result = self.db_api._db_row_to_bfi(
                row=bfi_row,
                cls_entity=self._cls,
            )
            bfi_list.append(bfi_result)
        return bfi_list

    def _get_id_mod_siz_list_prim_dig(
        self,
        bfi_primary_digests: list,
    ) -> list[_backing_attrs]:
        result_id_mod_siz_rows = self.db_api.batch_retrieve(
            query_with_qmarks_spec=DbQueryStrings.bfi_digest_qmarks_select,
            query_batch_parms=bfi_primary_digests,
        )
        result = [_backing_attrs(*r) for r in result_id_mod_siz_rows]
        return result

    def _resolve_backing_fi_dedup(
        self,
        bpi_list: list[_backup_prep_info],
    ):
        bfi_digests = []
        for idx, bpi in enumerate(bpi_list):
            bfi_most_recent_backup = bpi.lbi_by_path.bfi_most_recent_backup
            bfi_digests.append(bytes.fromhex(bfi_most_recent_backup.primary_digest))

        ims_list = self._get_id_mod_siz_list_prim_dig(  # list[bfi_id_modtime_size]
            bfi_primary_digests=bfi_digests,
        )

        ims_dict = defaultdict(list[_backing_attrs])
        for ims in ims_list:
            ims_dict[ims.primary_digest.hex()].append(ims)

        for idx, bpi in enumerate(bpi_list):
            bfi_most_recent_backup = bpi.lbi_by_path.bfi_most_recent_backup

            ims_list = ims_dict.get(bfi_most_recent_backup.primary_digest)
            if ims_list is None:
                raise InvalidStateError(
                    "_resolve_backing_fi_dedup: state error, ims list not found."
                )

            for ims in ims_list:
                is_backing = is_bfi_duplicate_info(
                    deduplication_option=bfi_most_recent_backup.deduplication_option,
                    bfi=bfi_most_recent_backup,
                    digest=ims.primary_digest.hex(),
                    modified_time_posix=ims.last_modified,
                    size_in_bytes=ims.size_in_bytes,
                    ext=os.path.splitext(ims.path)[0],
                )
                if is_backing:
                    bpi.lbi_by_path.backing_ims = ims
                    bpi.lbi_by_path.is_ims_backing = True

            if not bpi.lbi_by_path.is_ims_backing:
                raise InvalidStateError(
                    "_resolve_backing_fi_dedup: state error, ims not found."
                )

        backing_bfi_id_list = [b.lbi_by_path.backing_ims.bfi_id for b in bpi_list]
        backing_fi_list = self._retrieve_bfi_complete(
            bfi_ids=backing_bfi_id_list,
        )
        backing_bfi_id_dict = {b.bfi_id: b for b in backing_fi_list}
        for idx, bpi in enumerate(bpi_list):
            bfi_most_recent_backup = bpi.lbi_by_path.bfi_most_recent_backup
            if bfi_most_recent_backup.backing_fi is not None:
                raise InvalidStateError(
                    "_resolve_backing_fi_dedup: backing_fi must be None"
                )
            backing_fi_id = bpi.lbi_by_path.backing_ims.bfi_id
            bfi_most_recent_backup.backing_fi = backing_bfi_id_dict[backing_fi_id]

    def _resolve_backing_fi_path(self, bpi_list: list[_backup_prep_info]):

        if not bpi_list:
            return

        query_arg_list = []
        for bpi_idx, bpi in enumerate(bpi_list):
            bfi_most_recent_backup = bpi.lbi_by_path.bfi_most_recent_backup
            sb_info = self.sbid_to_sb_info[bfi_most_recent_backup.sb_id]
            query_arg_list.append(bpi_idx)
            query_arg_list.append(sb_info.backup_start_time_utc)
            query_arg_list.append(
                get_path_cmp_digest(path=bfi_most_recent_backup.path)
            )

        batch_result = self.db_api.batch_retrieve(
            query_with_qmarks_spec=DbQueryStrings.bfi_cidx_time_pathdig_qmarks_select,
            query_batch_parms=query_arg_list,
            qmarks_paren_item_count=3,
            batch_size=3 * 300,
        )

        bpi_idx = 0
        bpi = bpi_list[bpi_idx]
        for br_idx, br in enumerate(batch_result):
            if br[0] < bpi_idx:
                continue
            if br[0] > bpi_idx:
                raise InvalidStateError(
                    "_resolve_backing_fi_path: "
                    "all bpi items must correlate to most recent path backing results."
                )
            bfi_most_recent_backup = bpi.lbi_by_path.bfi_most_recent_backup
            if get_path_for_cmp(br[4]) != get_path_for_cmp(
                bfi_most_recent_backup.path
            ):
                continue
            if bpi.lbi_by_path.backing_ims is not None:
                raise InvalidStateError(
                    "_resolve_backing_fi_path: state error, backing ims must not be set."
                )
            bpi.lbi_by_path.backing_ims = _backing_attrs(
                bfi_id=br[1],
            )
            bpi_idx += 1
            if bpi_idx >= len(bpi_list):
                break
            bpi = bpi_list[bpi_idx]

        if bpi_idx < len(bpi_list):
            raise InvalidStateError(
                "_resolve_backing_fi_path: path backing info for all bpi not found."
            )

        backing_bfi_id_list = [b.lbi_by_path.backing_ims.bfi_id for b in bpi_list]
        backing_bfi_id_list.sort()
        backing_fi_list = self._retrieve_bfi_complete(
            bfi_ids=backing_bfi_id_list,
        )
        backing_bfi_id_dict = {b.bfi_id: b for b in backing_fi_list}
        for idx, bpi in enumerate(bpi_list):
            bfi_most_recent_backup = bpi.lbi_by_path.bfi_most_recent_backup
            if bfi_most_recent_backup.backing_fi is not None:
                raise InvalidStateError(
                    "_resolve_backing_fi_path: "
                    "backing_fi must be None"
                )
            backing_fi_id = bpi.lbi_by_path.backing_ims.bfi_id
            bfi_most_recent_backup.backing_fi = backing_bfi_id_dict[backing_fi_id]
        pass

    def _resolve_most_recent_bfi_backing_fi(
        self,
        bpi_list: list[_backup_prep_info],
    ):

        bpi_for_dedup: list[_backup_prep_info] = []
        bpi_for_path: list[_backup_prep_info] = []

        for idx, bpi in enumerate(bpi_list):
            bfi_most_recent = bpi.lbi_by_path.bfi_most_recent_backup
            if bfi_most_recent.is_successful:
                continue
            if not bfi_most_recent.is_unchanged_since_last:
                continue
            if bfi_most_recent.backing_fi is not None:
                raise InvalidStateError(
                    "_resolve_most_recent_bfi_backing_fi: "
                    "backing_fi must be None."
                )
            if bfi_most_recent.deduplication_option is not None:
                bpi_for_dedup.append(bpi)
            else:
                bpi_for_path.append(bpi)
        self._resolve_backing_fi_dedup(bpi_for_dedup)
        self._resolve_backing_fi_path(bpi_for_path)
