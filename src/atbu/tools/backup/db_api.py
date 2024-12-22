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
import logging
import os
import sqlite3
from typing import Union
from pathlib import Path

from atbu.tools.backup.exception import BackupDatabaseSchemaError
from atbu.common.util_helpers import (
    is_platform_path_case_sensitive,
)

from .backup_constants import *
from .backup_entities import *
from .global_hasher import GlobalHasherDefinitions

DB_API_SQLITE_CACHE_SIZE = -256000

def set_db_api_default_cache_size(cache_size):
    global DB_API_SQLITE_CACHE_SIZE
    DB_API_SQLITE_CACHE_SIZE = cache_size

def get_db_api_default_cache_size():
    return DB_API_SQLITE_CACHE_SIZE

def fn_pat_to_sql_like_pat(fn_pat: str):
    sql_like_pat = fn_pat.replace("*", "%")
    sql_like_pat = sql_like_pat.replace("?", "_")
    return sql_like_pat

def fn_pat_to_sql_where_expr(
    column_name: str,
    fn_pat_start_pos: int,
    fn_pat: str
) -> tuple[str, str]:
    """Returns tuple (where_expr, expr_pattern), where where_expr is either a GLOB or LIKE
    expression, including a question mark (?) for the expr_pattern to be used by the caller.
    If fn_pat_start_pos is greater than zero, the pattern is prefixed with that many wildcard
    characters (? or _ depending on whether GLOB or LIKE is used).
    """
    if fn_pat_start_pos == 0:
        return f"{column_name} = ?", fn_pat
    if is_platform_path_case_sensitive():
        return f"{column_name} GLOB ?", ("?"*fn_pat_start_pos) + fn_pat
    return f"{column_name} LIKE ?", ("_"*fn_pat_start_pos) + fn_pat_to_sql_like_pat(fn_pat)

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
        db.execute("UPDATE backup_db SET version = ? WHERE name = ?", (DbSchema.VERSION, db_name,))


@dataclass
class DbSchemaSetupStep:
    version: str
    schema_statements: str


class DbSchema:
    VERSION_DB_NOT_EXIST = "0.00"
    VERSION = BACKUP_INFO_MAJOR_VERSION_STRING

    schema_setup_steps = [
        DbSchemaSetupStep(
            version=VERSION_DB_NOT_EXIST,
            schema_statements=None,
        ),
        DbSchemaSetupStep(
            version="0.02",
            schema_statements="""
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
        DbSchemaSetupStep(
            version=VERSION,
            schema_statements="""
CREATE INDEX bfi_pvid_idx ON backup_file_info(path_value_id);
CREATE INDEX bfi_backingfidigest_path_dpath_sbi_idx ON backup_file_info(is_backing_fi_digest, path_value_id, discovery_path_value_id, specific_backup_id);
CREATE INDEX bfd_dv_bfi_idx ON backup_file_digests(digest_value_id, backup_file_info_id);
CREATE INDEX digest_values_idx ON digest_values(digest);
CREATE INDEX bfi_is_unchanged_last_idx ON backup_file_info(is_unchanged_since_last);
""",
        )
    ]

    def __init__(self):
        pass

    @staticmethod
    def upgrade_db(db: DbInterface, is_first_time_init: bool):
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
                return cur_db_ver

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

            logging.info(
                f"Running database upgrade from version {prev_db_ver_step} to "
                f"{schema_setup_step.version}"
            )
            logging.debug(f"Schema update steps: {schema_setup_step.schema_statements}")

            db.executescript(schema_setup_step.schema_statements)
            prev_db_ver_step = schema_setup_step.version

        if not is_started:
            raise BackupDatabaseSchemaError(
                f"Database schema updates were expected but did not occur."
            )

        DbCommonOperations.set_backup_db_version(
            db=db,
            db_name=BACKUP_DATABASE_DEFAULT_NAME,
            db_ver=DbSchema.VERSION
        )
        db.commit()

        logging.debug(f"Database version level check successful: version={DbSchema.VERSION}")
        return DbSchema.VERSION


class DbManagerSqlite3(DbInterface):
    def __init__(self, connection_string):
        if connection_string is None:
            raise ValueError(f"Invalid connection string: {connection_string}")
        self.connection_string = connection_string
        self.conn = sqlite3.connect(connection_string)

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

    def commit(self):
        self.db.commit()

    @staticmethod
    def create_api(connection_string: str) -> 'DbAppApi':
        return DbAppApi(DbManagerSqlite3(connection_string))

    def init_db(self, backup_base_name):
        DbSchema.upgrade_db(db=self.db, is_first_time_init=True)
        row_count, db_root_id, db_name, db_ver = DbCommonOperations.get_backup_db_root_info(self.db)
        c = self.db.execute(
            "INSERT INTO backups (backup_db_id, name) VALUES (?, ?)",
            (db_root_id, backup_base_name),
        )

    def set_db_cache_size(self, cache_size: int) -> int:
        DbCommonOperations.set_db_cache_size(db=self.db, cache_size=cache_size)
        return self.get_db_cache_size()

    def get_db_cache_size(self) -> int:
        return DbCommonOperations.get_db_cache_size(db=self.db)

    @lru_cache
    def get_backup_db_root(self) -> tuple[int, str, str]:
        (
            row_count,
            db_root_id,
            db_name,
            db_ver
        ) = DbCommonOperations.get_backup_db_root_info(db=self.db)

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
    ) -> tuple[str,str]:
        backups_root_id, backup_base_name = self.get_backups_root()
        c: sqlite3.Cursor = self.db.execute(
            "SELECT name, backup_start_time_utc "
            "FROM specific_backups sb "
            "WHERE sb.backups_id=? AND sb.id=?",
            (backups_root_id, specific_backup_id),
        )
        rows = c.fetchall()
        if len(rows) != 1:
            raise ValueError(
                f"there should only be one specific_backup_id={specific_backup_id}."
            )
        return rows[0] # name, backup_start_time_utc

    def get_specific_backups(
        self,
        is_persistent_db_conn: bool,
        backup_database_file_path: str,
        backup_base_name: str,
        cls_entity: SpecificBackupInformationEntityT = SpecificBackupInformationEntity,
    ) -> dict[str, SpecificBackupInformationEntityT]:
        backups_root_id, backup_base_name = self.get_backups_root()
        c: sqlite3.Cursor = self.db.execute(
            "SELECT sb.id, sb.backups_id, sb.name, sb.backup_start_time_utc, "
            "sb.object_name_hash_salt, sb.backup_type "
            "FROM specific_backups sb "
            "JOIN backups b ON b.id = ? "
            "ORDER BY sb.backup_start_time_utc;",
            (backups_root_id,),
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

    def _build_bfi_query(
        self,
        extra_select="",
        extra_clauses="",
    ):
        hash_algorithm_name = GlobalHasherDefinitions().get_primary_hashing_algo_name()
        query_str = (
            "SELECT bfi.id, bfi.specific_backup_id, bfi.path_value_id, pv.path, "
            "bfi.discovery_path_value_id, pv2.path discovery_path, "
            "dv.digest sha256, bfi.is_backing_fi_digest, bfi.last_modified, "
            "bfi.last_accessed, bfi.lastmodified_stamp, bfi.size_in_bytes, "
            "bfi.is_successful, bfi.exception, bfi.ciphertext_hash, "
            "bfi.encryption_IV, bfi.storage_object_name, "
            "bfi.is_unchanged_since_last, bfi.deduplication_option "
            f"{extra_select} "
            "FROM backup_file_info bfi "
            "INNER JOIN path_values pv ON bfi.path_value_id = pv.id "
            "INNER JOIN path_values pv2 ON bfi.discovery_path_value_id = pv2.id "
            "INNER JOIN backup_file_digests bfd ON bfi.id = bfd.backup_file_info_id "
            "INNER JOIN digest_values dv ON dv.id = bfd.digest_value_id "
            "INNER JOIN specific_backups sb ON sb.id = bfi.specific_backup_id "
            "INNER JOIN backups b ON b.id = sb.backups_id "
            "INNER JOIN backup_db b_db ON b_db.id = b.backup_db_id "
            "WHERE "
            "    b_db.id = (SELECT id FROM backup_db LIMIT 1) "
            "    AND b.id = (SELECT id FROM backups LIMIT 1) "
            f"    AND dv.digest_type = '{hash_algorithm_name}' "
            f"{extra_clauses}"
        )
        return query_str

    def get_duplicate_file(
        self,
        deduplication_option: str,
        bfi: BackupFileInformationEntityT,
    ) -> BackupFileInformationEntityT:
        dup_list = self.get_phys_backup_dup_list(primary_digest=bfi.primary_digest)
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
        if bfi.is_successful:
            return
        if not bfi.is_unchanged_since_last:
            return
        if bfi.backing_fi is not None:
            return
        if bfi.deduplication_option is not None:
            disc_backing_fi = self.get_duplicate_file(
                deduplication_option=bfi.deduplication_option,
                bfi=bfi,
            )
        else:
            disc_backing_fi = self.get_most_recent_backing_bfi_for_path(
                specific_backup_id=bfi.sb_id,
                path_substr=bfi.path,
                path_substr_pos=0,
                cls_entity=cls_entity,
            )
        bfi.backing_fi = disc_backing_fi
        validate_bfi_backing_information(bfi=bfi)

    def _db_row_to_bfi_resolve(
        self,
        row,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> BackupFileInformationEntityT:
        bfi = self._db_row_to_bfi(row, cls_entity)
        self.resolve_backing_fi(bfi=bfi, cls_entity=cls_entity)
        return bfi

    def get_specific_backup_file_info(
        self,
        specific_backup_id: int,
        resolve_backing_fi: bool = False,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> list[BackupFileInformationEntityT]:
        specific_backup_name, _ = self.get_specific_backup_info(
            specific_backup_id=specific_backup_id
        )
        logging.debug(f"Querying for bfi={specific_backup_id} name={specific_backup_name}")
        query_str = self._build_bfi_query(extra_clauses=" AND bfi.specific_backup_id = ? ")
        c: sqlite3.Cursor = self.db.execute(query_str, (specific_backup_id, ))
        result = []
        logging.debug(f"Processing rows for bfi={specific_backup_id} name={specific_backup_name}")
        for row in c:
            bfi = self._db_row_to_bfi(row, cls_entity)
            if resolve_backing_fi:
                self.resolve_backing_fi(bfi=bfi, cls_entity=cls_entity)
            result.append(bfi)
        logging.debug(f"Finished loading bfi={specific_backup_id} name={specific_backup_name}")
        return result

    def get_most_recent_backing_bfi_for_path(
        self,
        specific_backup_id: int,
        path_substr: str,
        path_substr_pos: int,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> BackupFileInformationEntityT:
        _, backup_start_time_utc = self.get_specific_backup_info(
            specific_backup_id=specific_backup_id
        )
        logging.debug(f"get_most_recent_backup_file_info_for_path: {path_substr}")
        where_expr, expr_pattern = fn_pat_to_sql_where_expr("pv.path", path_substr_pos, path_substr)
        query_str = self._build_bfi_query(
            extra_clauses=(
                "    AND bfi.is_unchanged_since_last = 0"
                "    AND sb.backup_start_time_utc <= ?"
                f"   AND {where_expr} "
                "ORDER BY sb.backup_start_time_utc DESC, pv.path "
                "LIMIT 1; "
            )
        )
        c: sqlite3.Cursor = self.db.execute(
            query_str,
            (backup_start_time_utc, expr_pattern, ),
        )
        row = c.fetchone()
        if not row:
            return None
        bfi = self._db_row_to_bfi(row, cls_entity)
        return bfi

    def get_most_recent_backup_of_path(
        self,
        path_substr: str,
        path_substr_pos: int,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> BackupFileInformationEntityT:
        logging.debug(f"get_most_recent_backup_file_info_for_path: {path_substr}")
        where_expr, expr_pattern = fn_pat_to_sql_where_expr("pv.path", path_substr_pos, path_substr)
        query_str = self._build_bfi_query(
            extra_clauses=(
                f"   AND {where_expr} "
                "ORDER BY sb.backup_start_time_utc DESC, pv.path "
                "LIMIT 1; "
            )
        )
        c: sqlite3.Cursor = self.db.execute(
            query_str,
            (expr_pattern, ),
        )
        row = c.fetchone()
        if not row:
            return None
        bfi = self._db_row_to_bfi_resolve(row, cls_entity)
        return bfi

    def get_phys_backup_dup_list(
        self,
        primary_digest: str,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> list[BackupFileInformationEntityT]:
        old_way = False
        query_str = """
WITH
    dv AS (
        SELECT id, digest
        FROM digest_values
        WHERE digest_values.digest = ? 
        AND digest_values.digest_type = ?
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
WHERE bfi.is_unchanged_since_last = 0 AND bfi.id IN (SELECT backup_file_info_id FROM bfd)
"""
        hash_algorithm_name = GlobalHasherDefinitions().get_primary_hashing_algo_name()
        c: sqlite3.Cursor = self.db.execute(
            query_str,
            (bytes.fromhex(primary_digest), hash_algorithm_name,),
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
        if fn_pat != '*':
            where_expr, expr_pattern = fn_pat_to_sql_where_expr(
                "pv.path",
                0,
                fn_pat,
            )
            where_expr = f"AND {where_expr} "
            sql_args = (specific_backup_id, expr_pattern,)

        query_str = self._build_bfi_query(
            extra_clauses=(
                "    AND bfi.specific_backup_id = ? "
                f"    {where_expr}"
                "ORDER BY pv.path; "
            )
        )
        c: sqlite3.Cursor = self.db.execute(
            query_str,
            sql_args,
        )

        result = []
        for row in c:
            bfi = self._db_row_to_bfi_resolve(row, cls_entity)
            result.append(bfi)
        return result

    def insert_specific_backup(
        self,
        parent_backups_id,
        backup_specific_name,
        backup_start_time_utc,
        object_name_hash_salt,
        backup_type,
    ) -> int:
        c = self.db.execute(
            "INSERT INTO specific_backups "
            "(backups_id, name, backup_start_time_utc, object_name_hash_salt, backup_type) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                parent_backups_id,
                backup_specific_name,
                backup_start_time_utc,
                object_name_hash_salt,
                backup_type,
            ),
        )
        return c.lastrowid

    def insert_path_value(self, path):
        c = self.db.execute("INSERT INTO path_values (path) VALUES (?)", (path,))
        return c.lastrowid

    def get_path_value_id(self, path):
        c = self.db.execute("SELECT id from path_values WHERE path=?", (path,))
        row = c.fetchone()
        return row[0] if row else None

    def get_path_value_id_insert(self, path):
        value_id = self.get_path_value_id(path)
        if value_id is None:
            value_id = self.insert_path_value(path)
        return value_id

    def insert_digest_value(self, digest_type, digest):
        if isinstance(digest, str):
            digest = bytes.fromhex(digest)
        if not isinstance(digest, bytes):
            raise ValueError(
                f"digest must be bytes or str convertable to bytes: {type(digest)}"
            )
        c = self.db.execute(
            "INSERT INTO digest_values (digest_type, digest) VALUES (?, ?)",
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
            "SELECT id from digest_values WHERE (digest_type, digest)=(?, ?)",
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
            "INSERT INTO backup_file_digests (backup_file_info_id, digest_value_id) VALUES (?, ?)",
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

        path_value_id = self.get_path_value_id_insert(path)
        discovery_path_value_id = self.get_path_value_id_insert(discovery_path)
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
            "INSERT INTO backup_file_info ("
            "specific_backup_id, "
            "path_value_id, "
            "last_modified, "
            "last_accessed, "
            "lastmodified_stamp, "
            "size_in_bytes, "
            "discovery_path_value_id, "
            "is_successful, "
            "exception, "
            "ciphertext_hash, "
            "encryption_IV, "
            "storage_object_name, "
            "is_unchanged_since_last, "
            "is_backing_fi_digest, "
            "deduplication_option"
            f') VALUES ({", ".join("?" * len(values))})',
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
            db_api.init_db(backup_base_name=backup_base_name)
            return db_api
        except:
            if db_api:
                db_api.close()
            raise

    @staticmethod
    def open_db(db_file_path: Union[str, Path]) -> "DbAppApi":
        if not os.path.exists(db_file_path):
            raise FileNotFoundError(f"Database file not found: {db_file_path}")
        try:
            db_api = DbAppApi.create_api(str(db_file_path))
            DbSchema.upgrade_db(db=db_api.db, is_first_time_init=False)
            return db_api
        except:
            if db_api:
                db_api.close()
            raise
