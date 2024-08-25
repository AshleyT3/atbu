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
r"""Thin SQL DB API layer.
"""
# pylint: disable=missing-class-docstring,missing-function-docstring

from dataclasses import dataclass
import logging
import os
import sqlite3
from typing import Union
from pathlib import Path

from .backup_constants import *
from .backup_entities import *
from .global_hasher import GlobalHasherDefinitions


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


class DbSchema:
    VERSION = "0.02"

    schema_statements = """
CREATE TABLE IF NOT EXISTS backup_db (id INTEGER PRIMARY KEY, name TEXT, version TEXT);

CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY, backup_db_id INTEGER NOT NULL, name TEXT, FOREIGN KEY (backup_db_id) REFERENCES backup_db(id));

CREATE TABLE IF NOT EXISTS specific_backups (id INTEGER PRIMARY KEY, backups_id INTEGER NOT NULL, name TEXT, backup_start_time_utc TEXT, object_name_hash_salt TEXT, backup_type TEXT, FOREIGN KEY (backups_id) REFERENCES backups(id));

CREATE TABLE IF NOT EXISTS path_values (id INTEGER PRIMARY KEY, path TEXT UNIQUE);

CREATE TABLE IF NOT EXISTS backup_file_info (id INTEGER PRIMARY KEY, specific_backup_id INTEGER NOT NULL, path_value_id INTEGER NOT NULL, last_modified DOUBLE, last_accessed DOUBLE, lastmodified_stamp TEXT, size_in_bytes INTEGER, discovery_path_value_id INTEGER NOT NULL, is_successful INTEGER, exception TEXT, ciphertext_hash BLOB, encryption_IV BLOB, storage_object_name TEXT, is_unchanged_since_last INTEGER, is_backing_fi_digest INTEGER, deduplication_option TEXT, FOREIGN KEY (specific_backup_id) REFERENCES specific_backups(id), FOREIGN KEY (path_value_id) REFERENCES path_values(id), FOREIGN KEY (discovery_path_value_id) REFERENCES path_values(id));

CREATE TABLE IF NOT EXISTS digest_values (id INTEGER PRIMARY KEY, digest_type TEXT, digest BLOB, UNIQUE (digest_type, digest));

CREATE TABLE IF NOT EXISTS backup_file_digests (backup_file_info_id INTEGER NOT NULL, digest_value_id INTEGER NOT NULL, FOREIGN KEY (backup_file_info_id) REFERENCES backup_file_info(id) FOREIGN KEY (digest_value_id) REFERENCES digest_values(id) PRIMARY KEY (backup_file_info_id, digest_value_id));

CREATE INDEX IF NOT EXISTS bfi_sbi_path_dpath_idx ON backup_file_info(specific_backup_id, path_value_id, discovery_path_value_id);

CREATE TRIGGER IF NOT EXISTS create_backup_file_info_trigger BEFORE INSERT ON backup_file_info WHEN NOT EXISTS (SELECT 1 FROM path_values WHERE id = NEW.path_value_id) OR NOT EXISTS (SELECT 1 FROM path_values WHERE id = NEW.discovery_path_value_id) BEGIN SELECT RAISE(ABORT, 'backup_file_info blocked: requires valid path_value_id, discovery_path_value_id, and must have at least one backup_file_digests association.'); END;
"""

    def __init__(self):
        pass

    @staticmethod
    def create_db(db: DbInterface):
        logging.debug(f"Running: {DbSchema.schema_statements}")
        db.executescript(DbSchema.schema_statements)
        db.commit()


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

    def init_db(self, db_name, backup_base_name) -> int:
        DbSchema.create_db(db=self.db)
        c: sqlite3.Cursor = self.db.execute(
            "INSERT INTO backup_db (name, version) VALUES (?, ?)",
            (db_name, DbSchema.VERSION),
        )
        backup_db_id = c.lastrowid
        c = self.db.execute(
            "INSERT INTO backups (backup_db_id, name) VALUES (?, ?)",
            (backup_db_id, backup_base_name),
        )
        return c.lastrowid  # backups_id

    def get_backup_db_root(self) -> tuple[int, str, str]:
        c = self.db.execute("SELECT COUNT(*) FROM backup_db")
        row_count = c.fetchone()[0]
        if row_count != 1:
            # At this time, there's only one top-level backup db per database.
            raise ValueError("backup_db should only have a single row.")
        c = self.db.execute("SELECT * FROM backup_db")
        l = c.fetchall()
        if len(l) != 1:
            raise ValueError("backup_db should only have a single row.")
        r = l[0]
        db_root_id, db_name, db_ver = r
        if db_name != BACKUP_DATABASE_DEFAULT_NAME:
            raise ValueError(
                f"backup_db should be named {BACKUP_DATABASE_DEFAULT_NAME}"
            )
        if db_ver != BACKUP_INFO_MAJOR_VERSION_STRING:
            raise ValueError(
                f"backup_db should be version {BACKUP_INFO_MAJOR_VERSION_STRING}"
            )
        return db_root_id, db_name, db_ver

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

    def get_specific_backup_name(
        self,
        specific_backup_id: int,
    ) -> str:
        backups_root_id, backup_base_name = self.get_backups_root()
        c: sqlite3.Cursor = self.db.execute(
            "SELECT name FROM specific_backups sb WHERE sb.backups_id=? AND sb.id=?",
            (backups_root_id, specific_backup_id),
        )
        rows = c.fetchall()
        if len(rows) != 1:
            raise ValueError(
                f"there should only be one specific_backup_id={specific_backup_id}."
            )
        return rows[0][0]

    def get_specific_backups(
        self,
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
                backup_base_name=backup_base_name,
                specific_backup_name=specific_backup_name,
                backup_start_time_utc=datetime.fromisoformat(row[3]),
                object_name_hash_salt=row[4],
                backup_type=row[5],
                sbi_id=row[0],
            )
        return result

    def get_specific_backup_file_info(
        self,
        specific_backup_id: int,
        specific_backup_name: str = None,
        cls_entity: BackupFileInformationEntityT = BackupFileInformationEntity,
    ) -> list[BackupFileInformationEntityT]:
        if not specific_backup_name:
            specific_backup_name = self.get_specific_backup_name(
                specific_backup_id=specific_backup_id
            )
        hash_algorithm_name = GlobalHasherDefinitions().get_primary_hashing_algo_name()
        logging.debug(f"Querying for bfi={specific_backup_id} name={specific_backup_name}")
        c: sqlite3.Cursor = self.db.execute(
            "SELECT bfi.id, bfi.specific_backup_id, bfi.path_value_id, pv.path, "
            "bfi.discovery_path_value_id, pv2.path discovery_path, "
            "dv.digest sha256, bfi.is_backing_fi_digest, bfi.last_modified, bfi.last_accessed, "
            "bfi.lastmodified_stamp, bfi.size_in_bytes, bfi.is_successful, bfi.exception, "
            "bfi.ciphertext_hash, bfi.encryption_IV, bfi.storage_object_name, "
            "bfi.is_unchanged_since_last, bfi.deduplication_option "
            "FROM backup_file_info bfi "
            "INNER JOIN path_values pv ON bfi.path_value_id = pv.id "
            "INNER JOIN path_values pv2 ON bfi.discovery_path_value_id = pv2.id "
            "INNER JOIN backup_file_digests bfd ON bfi.id = bfd.backup_file_info_id "
            "INNER JOIN digest_values dv ON dv.id = bfd.digest_value_id "
            "WHERE bfi.specific_backup_id = ? AND dv.digest_type = ?",
            (specific_backup_id, hash_algorithm_name),
        )
        result = []
        logging.debug(f"Processing rows for bfi={specific_backup_id} name={specific_backup_name}")
        for row in c:
            # pylint: disable=line-too-long
            # id, specific_backup_id, path_value_id,                path,  discovery_path_value_id,   discovery path,  digest,     is_backing_fi_digest,       last_modified,      last_accessed,                 lastmodified_stamp, size_in_bytes, is_successful, exception, ciphertext_hash, encryption_IV, storage_object_name, is_unchanged_since_last, deduplication_option
            #  0                   1              2                    3                         4,                5        6                         7                    8                   9                                 10             11         12               13              14             15                   16                       17                    18
            # (3,                  1,             4, 'c:\\somefolder...',                        2,  'c:\\somefolder', b'...',                        0,  1721967555.8663788, 1724136489.4542758, '2024-07-26T04:19:14.866381+00:00',          1024,             1,      None,          b'...',        b'...',          '*.atbake',                       0,                    0,                 None)
            bfi = cls_entity(
                path=row[3],
                discovery_path=row[5],
            )
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
            result.append(bfi)
        logging.debug(f"Finished loading bfi={specific_backup_id} name={specific_backup_name}")
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
        database_name: str,
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
            db_api.init_db(
                db_name=database_name,
                backup_base_name=backup_base_name,
            )
            return db_api
        except:
            if db_api:
                db_api.close()
            raise

    @staticmethod
    def open_db(db_file_path) -> "DbAppApi":
        if not os.path.exists(db_file_path):
            raise FileNotFoundError(f"Database file not found: {db_file_path}")
        return DbAppApi.create_api(str(db_file_path))
