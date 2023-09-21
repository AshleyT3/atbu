|PROJNAME| Backup File Format Specification
=========================================================

One of the main goals of |PROJNAME| backup is to give power to the user over their stored data regardless of whether the tooling is around to directly manage it. Part of doing this, especially for technically demanding users, is to ensure the backup format is simple and well-documented. This technical specification outlines the format below.

Another goal is to allow a user to find and manage a physical backup of an original file using a platform's file management tools without needing the |PROJNAME| tooling. This could be utilized, for example, to manually prune away one or more particular files with relative ease.

|PROJNAME| accomplishes these goals by storing backed up files in a format that is both extraordinarily simple, yet which itself retains information that allows for restoration of the files to the proper stucture of the restore point (the tip of the restore directory or folder) specified at the time of restore. This actually goes whether |PROJNAME| backup is used for restoring files, or if some other non-|PROJNAME| tool.

|PROJNAME| therefore seeks to have not only an open format, but one which is easily understood, and contains enough information to allow reasonable restoration procedures to take place years into the future, even if |PROJNAME| tooling itself, or even Python were not around. Given the openness and simplicity of the format used, and its use of standards such as AES encryption and GZIP compression, creating other tooling to decrypt and restore a backup is feasiable so long as the secrets are maintained.

|PROJNAME| backup stores backed up files in the same format regardless of the dest storage medium, local or cloud storage. If you understand the local backup storage format, you understand the cloud storage format. There is no difference in the backed up file format.

Note, in the cloud, backup files are stored in a single directory structure (flat file object or blob storage), whereas on local drives a single-level directory structure is used to categorize blobs/objects, but the files themselves have the same internal format which is outlined below.

|PROJNAME| backup stores files with one-to-one correspondence between the original file and its archival storage object. Again, this applies to both local and cloud backups. Multiple files of a backup are not packed into archives, but are instead each stored in their own single storage object whether on local storage or in the cloud.

Depending on the destiation file systems or cloud storage provider implementations (and costs), there can be additional costs with this one-to-one approach used by |PROJNAME| backup, but the payoffs for having one discrete backup object for each backed up file is tremendous:

* It allows pruning backups over time without having to touch unrelated backup file data.
* It also allows a user to easily understand exactly where each file is physically stored, and to manage those files directly as needed, and without having to restore or decrypt them either.
* For any given physically backed up file, there will be one storage object.
* All of this is the same for either local or cloud storage.

Files backed up with |PROJNAME| backup have either a .atbak or .atbake extension ("at" and "bak" for backup, where 'e' means encrypted). Regardless of whether the file is .atbak (unencrypted), or .atbake (encrypted), the internal format is the same aside from any differences based on any options such as encryption, compression, and so forth.

All |PROJNAME| backup .atbak and .atbake files have the following general structure:

 `<backup_header> <preamble_size> <preamble> <file_data>`

The |PROJNAME| backup header has the following format:

+---------------------------+-------------------------+------------------------------------------+
| name                      | size                    | format/values                            |
+===========================+=========================+==========================================+
| initial header version    | 1 byte                  | 0x01 is the current/only version         |
+---------------------------+-------------------------+------------------------------------------+
| options flags             | 1 byte                  | | 0x01: BACKUP_HEADER_OPTION_IV_INCLUDED |
+---------------------------+-------------------------+------------------------------------------+
| AES encryption IV         | 16 byte                 | The AES encryption IV (only present if   | 
|                           |                         | BACKUP_HEADER_OPTION_IV_INCLUDED is set  |
+---------------------------+-------------------------+------------------------------------------+

If the encryption IV is included, it is alaways 16 bytes. The encryption IV is usually included as it is non-secret yet essential for decryption.

Following the initial 2-byte backup header, and the encryption IV if applicable, is the preamble header which is itself followed by the file's data.

The |PROJNAME| preamble header has the following format:

+------------------+-------------------------+-------------------------------+
| name             | size                    | format                        |
+==================+=========================+===============================+
| preamble_size    | 2 bytes                 | little endian unsigned short. |
+------------------+-------------------------+-------------------------------+
| preamble         | <preamble_size> bytes   | UTF-8 string                  |
+------------------+-------------------------+-------------------------------+
| file_data        | remainder of the file   | the original file, either     |
|                  |                         | uncompressed/compressed.      |
+------------------+-------------------------+-------------------------------+

The `<preamble>` itself uses key/value pairs which offer flexibility for growth over time.

The `<preamble>` fields can be parsed into a Python dictionary or similar structure of any given language.

The general format of the `<preamble>` is as follows:

 `v=1,z=<gzip|none>,sha256=<file_data_SHA256_hash>,size=<file_size>,modified=<modified_posix>,accessed=<accessed_posix_time>,path=<path_without_root>`

The following outlines the |PROJNAME| backup `<preamble>` fields:

+------------+----------------------------------------+---------------------------------------------------------+
| key name   | meaning                                | description                                             |
+============+========================================+=========================================================+
| 'v'        | preamble version                       | The initial and current version is 1.                   |
+------------+----------------------------------------+---------------------------------------------------------+
| 'z'        | compression type                       | | 'none' for uncompressed.                              |
|            |                                        | | 'gzip' for gzip compression.                          |
|            |                                        | | If 'v' is not present, it means uncompressed.         |
+------------+----------------------------------------+---------------------------------------------------------+
| 'sha256'   | the SHA256 hash of `<file_data>`       | Currently only SHA256 is used and is always present.    |
+------------+----------------------------------------+---------------------------------------------------------+
| 'size'     | file size                              | The uncompressed size of the backed up file.            |
+------------+----------------------------------------+---------------------------------------------------------+
| 'modified' | file modified time                     | The file's original modified time as a posix timestamp. |
+------------+----------------------------------------+---------------------------------------------------------+
| 'accessed' | file accessed time                     | The file's original accessed time as a posix timestamp. |
+------------+----------------------------------------+---------------------------------------------------------+
| 'path'     | file path                              | The file's original path location (without the drive    |
|            |                                        | letter, if applicable).                                 |
+------------+----------------------------------------+---------------------------------------------------------+
