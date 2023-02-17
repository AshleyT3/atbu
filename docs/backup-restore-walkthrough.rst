.. _cloud-and-local-backup:

|PROJNAME| Cloud and Local Backup/Restore Getting Started
=========================================================

Setup
-----

|PROJNAME| has been tested on Python 3.9.12 and higher... so first install Python, possibly creating a virtual environment if you wish.

After your environment is setup with Python...

To use |PROJNAME|, first install it using pip |PKGNAME|:

.. code-block::

   pip install |PKGNAME|

The remaining sections below flow from top to bottom as a form of general walkthrough, showing how to perform various key tasks.

.. contents:: Table of Contents
    :depth: 3

Local Backup/Restore
--------------------

Performing a local backup
^^^^^^^^^^^^^^^^^^^^^^^^^
Local backups are those where files from local directories are backed up to other local directories, usually to other local directories on other drives.

The following performs a full backup from directory C:\\MyData to an external hard drive directory D:\\MyBackupDirectory:

``atbu backup --full C:\MyData D:\MyBackupDirectory``

Since this is the first time D:\\MyBackupDirectory has been used for a backup destination, the user is prompted to setup the new backup storage directory.

A backup storage directory or location is a place where backed up files reside along with any backup information files. 

Below shows the user pressed <ENTER> to accept the defaults to the initial backup location configuration questions after which the backup ran, backing up all files in C:\\MyData. The user chose to enable encryption without requiring a user password each time the backup runs.

Later, we will see how you can add a password, take away a password, and export/import your backup's private encryption key.

**Example output:** (edited for brevity)

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu backup --full C:\MyData D:\MyBackupDirectory
    atbu - v0.01
    Writing new configuration: D:\MyBackupDirectory\.atbu\atbu-config.json
    Storage location: D:\MyBackupDirectory
    Storage definition: D:\MyBackupDirectory\.atbu\atbu-config.json
    Backup destinations require a storage definition which retains information about the
    storage location, including how to access it and whether it's cloud or filesystem-based.
    Enter a user-friendly name for this backup destination's storage definition.
    If you press ENTER without entering anything, 'MyBackupDirectory' will be used.
    Enter a name (letters, numbers, spaces):
    Using 'MyBackupDirectory'.
    Using the name 'MyBackupDirectory'...
    Creating backup storage definition...
    Created storage definition MyBackupDirectory for D:\MyBackupDirectory
    The destination can be encrypted.
    Would you like encryption enabled? [Y/n] <ENTER>

    You can require the backup to ask for a password before starting a backup/restore,
    or you can allow a backup to proceed automatically without requiring your password.

    When you choose the automatic approach which does not require a password, you are
    allowing your backup 'private key' to be used automatically by this program. When
    doing this, your backup private key is stored in a manner where, not only this
    program, but other programs and people who have access to your computer or its
    contents may be able to access and use your private key.

    You can switch between requiring your password or using the automatic approach as
    needed/desired. Regardless of your choice, you should be certain to back up your
    security information (i.e., private key, related info) which you can do at any time.


    Choose whether to require password or not.
    Require a (p)assword or allow (a)utomatic use of your backup's private key?  [p/A] <ENTER>
    Creating key...created.
    Storing...
    Keyring information:
    Key=encryption-key
    Service=MyBackupDirectory
    Username=ATBU-backup-enc-key
    Your key is stored.
    Saving D:\MyBackupDirectory\.atbu\atbu-config.json
    D:\MyBackupDirectory\.atbu\atbu-config.json has been saved.
    Backup location(s)...
    Source location #0 .............. C:\MyData
    Searching for files...
    Backup destination: D:\MyBackupDirectory
    No backup history for 'MyBackupDirectory'. Creating new history database.
    Starting backup 'MyBackupDirectory-20220527-061212'...
    Scheduling hashing jobs...
    Waiting for completion of remaining hashing jobs...
    Wait backup file operations to complete...
    0% completed of C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    0% completed of C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
    0% completed of C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    0% completed of C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    0% completed of C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
    100% completed of C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
    100% completed of C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    100% completed of C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    100% completed of C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
    100% completed of C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    BackupFile: Completed C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
    Total bytes .............. 869673
    SHA256 original file ..... 6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    SHA256 encrypted file .... 9635c5f7b78e4e42850012d4b4be146a8869ff1d4ae921672abe3b203acc497a
    ---
    BackupFile: Completed C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
    Total bytes .............. 3059866
    SHA256 original file ..... 16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    SHA256 encrypted file .... eabca80e88058e3dad94fc902d22910b74fbaaa9cc04694043950eda8886a9ba
    ---
    BackupFile: Completed C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    Total bytes .............. 798387
    SHA256 original file ..... 6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    SHA256 encrypted file .... e37edab1bac45a9205c50ad669ccae56c752f2bfe7ff2aa5c86d2e72b5315845
    ---

    ... (edited for brevity) ...
    
    Waiting for backup information to be saved...
    SpecificBackupInformation thread stop initiated. Finishing up...
    Saving in-progress backup information: C:\Users\User\.atbu\atbu-backup-info\MyBackupDirectory-20220527-061212.atbuinf.tmp
    Saving backup info file: C:\Users\User\.atbu\atbu-backup-info\MyBackupDirectory-20220527-061212.atbuinf
    Backup info file saved: C:\Users\User\.atbu\atbu-backup-info\MyBackupDirectory-20220527-061212.atbuinf
    Copying primary C:\Users\User\.atbu\atbu-backup-info\MyBackupDirectory-20220527-061212.atbuinf to D:\MyBackupDirectory\.atbu\atbu-backup-info...
    SpecificBackupInformation background thread ending.
    0% completed of C:\Users\User\.atbu\atbu-backup-info\MyBackupDirectory.atbuinf
    100% completed of C:\Users\User\.atbu\atbu-backup-info\MyBackupDirectory.atbuinf
    BackupFile: Completed C:\Users\User\.atbu\atbu-backup-info\MyBackupDirectory.atbuinf
    Total bytes .............. 22033
    SHA256 original file ..... 9743781e28dd0b78f580e1779552a231729a2c529006552776619fcfb43371fc
    SHA256 encrypted file .... 75b8f639caf700109f99fa5c50652d4f3dfd79bdd8842a21b3b88151c9035d16
    ---
    The backup information has been successfully backed up: C:\Users\User\.atbu\atbu-backup-info\MyBackupDirectory.atbuinf
    All backup file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during backup.
    Total files ................................. 17
    Total unchanged files ....................... 0
    Total file results .......................... 17
    Total errors ................................ 0
    Total successful backups .................... 0
    Success, no errors detected.
    (venv2-3.9.12) PS C:\>

The result of the above initial backup command is that a new backup storage definition D:\\MyBackupDirectory has been created.

Listing information about a backup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following command will display information about D:\\MyBackupDirectory using the 'list' command:

``atbu list D:\MyBackupDirectory``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu list D:\MyBackupDirectory
    atbu - v0.01

    Storage Definition    Provider    Container             Interface    Encrypted    Persisted IV
    --------------------  ----------  --------------------  -----------  -----------  --------------
    MyBackupDirectory     filesystem  D:\MyBackupDirectory  filesystem   True         True
    (venv2-3.9.12) PS C:\>

The following displays information about the backup history for D:\\MyBackupDirectory:

``atbu list D:\MyBackupDirectory backup:*``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu list D:\MyBackupDirectory backup:*
    atbu - v0.01

    Storage Definition    Provider    Container             Interface    Encrypted    Persisted IV
    --------------------  ----------  --------------------  -----------  -----------  --------------
    MyBackupDirectory     filesystem  D:\MyBackupDirectory  filesystem   True         True
    Specific backups from storage definition 'MyBackupDirectory'
    MyBackupDirectory-20220527-061212
    (venv2-3.9.12) PS C:\>

The above indicates a backup occurred on May, 27, 2022 at around 6:12AM UTC.

The following command shows what was backed up in that backup...

``atbu list D:\MyBackupDirectory backup:MyBackupDirectory-20220527-061212 files:*``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu list D:\MyBackupDirectory backup:MyBackupDirectory-20220527-061212 files:*
    atbu - v0.01

    Storage Definition    Provider    Container             Interface    Encrypted    Persisted IV
    --------------------  ----------  --------------------  -----------  -----------  --------------
    MyBackupDirectory     filesystem  D:\MyBackupDirectory  filesystem   True         True
    Specific backups from storage definition 'MyBackupDirectory'
    MyBackupDirectory-20220527-061212
        C:\MyData\Documents\2021-Budget.xlsx
        C:\MyData\Documents\MyImportantNotes.txt
        C:\MyData\Documents\Textually speaking, a novel in pure text.txt
        C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
        C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
        C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
        C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
        C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
        C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg
        C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
        C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg
        C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202446.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202504.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    (venv2-3.9.12) PS C:\>

You could obviously filter on only Wildlife files with the following command...

``atbu list D:\MyBackupDirectory backup:MyBackupDirectory-20220527-061212 files:*\Wildlife\*``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu list D:\MyBackupDirectory backup:MyBackupDirectory-20220527-061212 files:*\Wildlife\*
    atbu - v0.01

    Storage Definition    Provider    Container             Interface    Encrypted    Persisted IV
    --------------------  ----------  --------------------  -----------  -----------  --------------
    MyBackupDirectory     filesystem  D:\MyBackupDirectory  filesystem   True         True
    Specific backups from storage definition 'MyBackupDirectory'
    MyBackupDirectory-20220527-061212
        C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
        C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg
        C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
        C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg
        C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    (venv2-3.9.12) PS C:\>

Restore files from a local backup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The following command will restore *all* files from the *last* "D:\\MyBackupDirectory" backup to a destination directory named C:\\MyRestore:

``atbu restore D:\MyBackupDirectory\ backup:last files:* C:\MyRestore``

**Example output:** (edited for brevity)

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu restore D:\MyBackupDirectory\ backup:last files:* C:\MyRestore
    atbu - v0.01
    Will restore 17 files from 'MyBackupDirectory'
    Starting restore from 'MyBackupDirectory'...
    Scheduling restore jobs...
    Wait for restore file operations to complete...
    0% completed of C:\MyRestore\Documents\2021-Budget.xlsx
    0% completed of C:\MyRestore\Documents\Textually speaking, a novel in pure text.txt
    0% completed of C:\MyRestore\Documents\MyImportantNotes.txt
    0% completed of C:\MyRestore\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    0% completed of C:\MyRestore\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
    RestoreFile: Completed for C:\MyRestore\Documents\2021-Budget.xlsx
    Total bytes ............................... 6184
    SHA256 download ........................... 9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    SHA256 original ........................... 9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    SHA256 encrypted download ................. bf45f129e5e9415a33b54419432a69b0c79af93cbc74d551d3fa5931d6dcf715
    Restore succeeded: C:\MyData\Documents\2021-Budget.xlsx
    SHA256 encrypted original ................. bf45f129e5e9415a33b54419432a69b0c79af93cbc74d551d3fa5931d6dcf715
    0% completed of C:\MyRestore\Pictures\SocialMedia\20211017_162445.jpg
    RestoreFile: Completed for C:\MyRestore\Documents\Textually speaking, a novel in pure text.txt
    Total bytes ............................... 63
    SHA256 download ........................... c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    SHA256 original ........................... c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    SHA256 encrypted download ................. b295958f46ab412932c935b108576c8338362a77c6fc9e9e0251f1edd2118b39
    SHA256 encrypted original ................. b295958f46ab412932c935b108576c8338362a77c6fc9e9e0251f1edd2118b39
    Restore succeeded: C:\MyData\Documents\Textually speaking, a novel in pure text.txt
    RestoreFile: Completed for C:\MyRestore\Documents\MyImportantNotes.txt
    Total bytes ............................... 34
    SHA256 download ........................... 2df5d20b39e6f3814da49b7752f569f388009a1a531139f60e8d9820702e3894
    SHA256 original ........................... 2df5d20b39e6f3814da49b7752f569f388009a1a531139f60e8d9820702e3894
    SHA256 encrypted download ................. d482a4788a99937f43104fe7fdce2a3ca13095fc8267df36577eaad0ee565641
    SHA256 encrypted original ................. d482a4788a99937f43104fe7fdce2a3ca13095fc8267df36577eaad0ee565641
    Restore succeeded: C:\MyData\Documents\MyImportantNotes.txt
    ... (edited for brevity) ...
    All restore file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during restore.
    Total files ................................. 17
    Total errors ................................ 0
    Total success ............................... 17
    Finished... no errors detected.
    (venv2-3.9.12) PS C:\>

After restoring, you can see both C:\MyRestore and the original C:\MyData contain the same files...

.. code-block:: console

    C:\MyRestore
    ├───Documents
    │       2021-Budget.xlsx
    │       MyImportantNotes.txt
    │       Textually speaking, a novel in pure text.txt
    │
    └───Pictures
        ├───Events
        │   └───2021-HolidayParty
        │           20210704_223018.jpg
        │           20210826_191432.jpg
        │
        ├───SocialMedia
        │       20211017_162445.jpg
        │       20211119_230028.jpg
        │
        ├───Wildlife
        │   ├───Deer
        │   │       20210704_222527.jpg
        │   │       20210704_222623.jpg
        │   │       20210704_222626.jpg
        │   │
        │   └───Geese
        │           20210703_193235.jpg
        │           20210703_193244.jpg
        │
        └───Yellowstone
                20210702_202203.jpg
                20210702_202437.jpg
                20210702_202446.jpg
                20210702_202504.jpg
                20210702_202530.jpg

    C:\MyData
    ├───Documents
    │       2021-Budget.xlsx
    │       MyImportantNotes.txt
    │       Textually speaking, a novel in pure text.txt
    │
    └───Pictures
        ├───Events
        │   └───2021-HolidayParty
        │           20210704_223018.jpg
        │           20210826_191432.jpg
        │
        ├───SocialMedia
        │       20211017_162445.jpg
        │       20211119_230028.jpg
        │
        ├───Wildlife
        │   ├───Deer
        │   │       20210704_222527.jpg
        │   │       20210704_222623.jpg
        │   │       20210704_222626.jpg
        │   │
        │   └───Geese
        │           20210703_193235.jpg
        │           20210703_193244.jpg
        │
        └───Yellowstone
                20210702_202203.jpg
                20210702_202437.jpg
                20210702_202446.jpg
                20210702_202504.jpg
                20210702_202530.jpg

Verifying a backup without restore
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The command to verify a backup without restoring its files is very similar to performing a restore. The following performs a verify of the same backup restored in the previous example...

``atbu verify D:\MyBackupDirectory\ backup:last files:*``

**Example output:** (edited for brevity)

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu verify D:\MyBackupDirectory\ backup:last files:*
    atbu - v0.01
    Will verify 17 files in 'MyBackupDirectory'
    Starting verify from 'MyBackupDirectory'...
    Scheduling verification jobs...
    Wait for verify file operations to complete...
    0% completed of MyData\Documents\2021-Budget.xlsx
    0% completed of MyData\Documents\MyImportantNotes.txt
    0% completed of MyData\Documents\Textually speaking, a novel in pure text.txt
    0% completed of MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    0% completed of MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
    VerifyFile: Completed for Documents\MyImportantNotes.txt
    Total bytes ............................... 34
    SHA256 download ........................... 2df5d20b39e6f3814da49b7752f569f388009a1a531139f60e8d9820702e3894
    SHA256 original ........................... 2df5d20b39e6f3814da49b7752f569f388009a1a531139f60e8d9820702e3894
    SHA256 encrypted download ................. d482a4788a99937f43104fe7fdce2a3ca13095fc8267df36577eaad0ee565641
    SHA256 encrypted original ................. d482a4788a99937f43104fe7fdce2a3ca13095fc8267df36577eaad0ee565641
    VerifyFile: Completed for Documents\2021-Budget.xlsx
    Total bytes ............................... 6184
    Verify succeeded: Documents\MyImportantNotes.txt
    SHA256 download ........................... 9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    SHA256 original ........................... 9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    SHA256 encrypted download ................. bf45f129e5e9415a33b54419432a69b0c79af93cbc74d551d3fa5931d6dcf715
    SHA256 encrypted original ................. bf45f129e5e9415a33b54419432a69b0c79af93cbc74d551d3fa5931d6dcf715
    Verify succeeded: Documents\2021-Budget.xlsx
    VerifyFile: Completed for Documents\Textually speaking, a novel in pure text.txt
    Total bytes ............................... 63
    SHA256 download ........................... c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    SHA256 original ........................... c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    SHA256 encrypted download ................. b295958f46ab412932c935b108576c8338362a77c6fc9e9e0251f1edd2118b39
    SHA256 encrypted original ................. b295958f46ab412932c935b108576c8338362a77c6fc9e9e0251f1edd2118b39
    Verify succeeded: Documents\Textually speaking, a novel in pure text.txt
    ... (edited for brevity) ...
    All file verify operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during verify.
    Total files ................................. 17
    Total errors ................................ 0
    Total success ............................... 17
    Finished... no errors detected.
    (venv2-3.9.12) PS C:\>

The above verify checks for matches of SHA256 digest, file modified date/time, file size. If you wish to also fully compare each backup file's contents byte-by-byte with a local copy of the file, you can add the ``--compare`` switch as follows...

``atbu verify D:\MyBackupDirectory\ backup:last files:* --compare``

Performing an incremental backup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Let's perform a typical *incremental* backup, which is a backup where only changed files are backed up.

Typically, changed files are detected either through an OS flag or modified date/time and size checks. |PROJNAME| uses the latter approach, modified date/time and size checks for incremental backups, but also provides *increment plus* digest-based change detection discussed in a later section.

Let's add and modify files in the C:\\MyData folder as follows...

.. code-block:: console

    C:\MyData
    ├───Documents
    │       MyImportantNotes.txt <---------- modified
    │
    └───Pictures
        │
        └───Wildlife
            │
            └───Heron
                    20220530_140532.jpg <--- added
                    20220530_140645.jpg <--- added

If we were to perform a full backup, all files, even those that have not changed, would be backed up again, creating lots of unnecessary duplication. If we want to only backup the added/modified files, we perform an incremental backup as follows...

``atbu backup --incremental C:\MyData\ D:\MyBackupDirectory\``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu backup --incremental C:\MyData\ D:\MyBackupDirectory\
    atbu - v0.01
    Storage location: D:\MyBackupDirectory
    Storage definition: D:\MyBackupDirectory\.atbu\atbu-config.json
    Backup location(s)...
    Source location #0 .............. C:\MyData\
    Searching for files...
    Backup destination: D:\MyBackupDirectory\
    Starting backup 'mybackupdirectory-20220530-225519'...
    Scheduling hashing jobs...
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    Scheduling backup of changed file: C:\MyData\Documents\MyImportantNotes.txt cur_date=2022-05-30T15:49:00.054641 old_date=2022-05-27T04:56:21.956714 cur_size=62 old_size=46
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
    Scheduling backup of file never backed up before: C:\MyData\Pictures\Wildlife\Heron\20220530_140645.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202504.jpg
    Skipping unchanged file: C:\MyData\Documents\2021-Budget.xlsx
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202446.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    Skipping unchanged file: C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    Skipping unchanged file: C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
    Skipping unchanged file: C:\MyData\Documents\Textually speaking, a novel in pure text.txt
    Skipping unchanged file: C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
    Skipping unchanged file: C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
    Scheduling backup of file never backed up before: C:\MyData\Pictures\Wildlife\Heron\20220530_140532.jpg
    Waiting for completion of remaining hashing jobs...
    Wait backup file operations to complete...
    0% completed of C:\MyData\Documents\MyImportantNotes.txt
    100% completed of C:\MyData\Documents\MyImportantNotes.txt
    BackupFile: Completed C:\MyData\Documents\MyImportantNotes.txt
    Total bytes .............. 211
    SHA256 original file ..... 3efb41e3ada35977bd17d9360318197193d8e20f557c89f5f13f8aa89743e5ea
    SHA256 encrypted file .... b13cee909453301b39b1a94af2e593b251817e3f0614dd6cfc0657cf7b1adea1
    ---
    Backup succeeded: Documents\MyImportantNotes.txt
    0% completed of C:\MyData\Pictures\Wildlife\Heron\20220530_140645.jpg
    0% completed of C:\MyData\Pictures\Wildlife\Heron\20220530_140532.jpg
    100% completed of C:\MyData\Pictures\Wildlife\Heron\20220530_140645.jpg
    100% completed of C:\MyData\Pictures\Wildlife\Heron\20220530_140532.jpg
    BackupFile: Completed C:\MyData\Pictures\Wildlife\Heron\20220530_140645.jpg
    Total bytes .............. 227
    SHA256 original file ..... b658c01348ac5aaac8dc634ab9086b55eb698f4eb15d0eb71d670ebe4e721f0d
    SHA256 encrypted file .... 11ccde5b1e0a6be51b0b2167fb882beb16d77bd52f5ea46491ad58bb91c51afe
    ---
    Backup succeeded: Pictures\Wildlife\Heron\20220530_140645.jpg
    BackupFile: Completed C:\MyData\Pictures\Wildlife\Heron\20220530_140532.jpg
    Total bytes .............. 227
    SHA256 original file ..... a6996a2b2f0c208d17782bc12a898ef682fb9d8905c5ed8f4309f744fdca69d6
    SHA256 encrypted file .... 57d36764e5fd567de5b79cf01afa67bb176bd5f91eb8ec940e12ef018232f65f
    ---
    Backup succeeded: Pictures\Wildlife\Heron\20220530_140532.jpg
    Waiting for backup information to be saved...
    SpecificBackupInformation thread stop initiated. Finishing up...
    Saving in-progress backup information: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-225519.atbuinf.tmp
    Saving backup info file: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-225519.atbuinf
    Backup info file saved: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-225519.atbuinf
    Copying primary C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-225519.atbuinf to D:\MyBackupDirectory\.atbu\atbu-backup-info...
    SpecificBackupInformation background thread ending.
    0% completed of C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    100% completed of C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    BackupFile: Completed C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    Total bytes .............. 243
    SHA256 original file ..... 2397dd7b7f757b1fe63e7af73e57a3b43311d98bfed6a6ec65031783d65aa555
    SHA256 encrypted file .... a1d8a93a12aa446cefb5e8228748dd9f04d76016472bbd89a9441f3abe316ee5
    ---
    The backup information has been successfully backed up: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    All backup file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during backup.
    Total files ................................. 19
    Total unchanged files ....................... 16
    Total backup operations ..................... 3
    Total errors ................................ 0
    Total successful backups .................... 3
    Success, no errors detected.
    (venv2-3.9.12) PS C:\>

You can see above only 3 files total were backed up. Those 3 files were detected because either they were not already in the backup history, or they had changed since the last time they were backed up. With |PROJNAME| incremental backups, a changed file is a file whose modified date/time or size has changed.

Detecting bitrot and other "sneaky" changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
There are cases, typically rare, where a file's contents may change while neither its modified date/time or size change. Two examples of how this can happen are as follows...

* A hard drive, disk, USB/Flash or other media has become defective with age, where so-called "bitrot" occurs.
* A program, malicious or otherwise, modifies a file's contents after which it resets the modified date/time to the value before modification.

In both of those example cases, typical incremental change detection will not detect the changed file. The reason for this is that incremental change detection uses modified date/time and size as factors in change detection, but not the file's content. |PROJNAME| generally refers to hidden changes like this as "sneaky" changes/corruption. 

Let's modify a file and reset its modified date/time to simulate bitrot.

We will modify this file...

* D:\\MyData\\Pictures\\Wildlife\\Deer\\20210704_222527.jpg

.. code-block:: console

    (venv2-3.9.12) PS C:\> $f = Get-Item C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    (venv2-3.9.12) PS C:\> $lw = $f.LastWriteTime
    (venv2-3.9.12) PS C:\> $lw
    Sunday, July 4, 2021 10:25:32 PM
    (venv2-3.9.12) PS C:\> # At this point, I use a binary editor to modify one byte in the 20210704_222527.jpg file.
    (venv2-3.9.12) PS C:\> # Let's check the LastWriteTime after that modification...
    (venv2-3.9.12) PS C:\> $f = Get-Item C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    (venv2-3.9.12) PS C:\> $f.LastWriteTime
    Monday, May 30, 2022 4:32:01 PM
    (venv2-3.9.12) PS C:\> # You can see the modified date/time changed. Let's reset it back to the 2021 date...
    (venv2-3.9.12) PS C:\> $f.LastWriteTime = $lw
    (venv2-3.9.12) PS C:\> $f = Get-Item C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    (venv2-3.9.12) PS C:\> $f.LastWriteTime
    Sunday, July 4, 2021 10:25:32 PM
    (venv2-3.9.12) PS C:\> # Instant bitrot simulation!

After performing the above steps, the 20210704_222527.jpg file's contents has been modified but neither it's date/time modified nor size has changed. Incremental backup alone will not detect this change.

Let's perform an incremental (not incremental plus) backup to see the above changed *not* get backed up...

``atbu backup --incremental C:\MyData\ D:\MyBackupDirectory\``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu backup --incremental C:\MyData\ D:\MyBackupDirectory\
    atbu - v0.01
    Storage location: D:\MyBackupDirectory
    Storage definition: D:\MyBackupDirectory\.atbu\atbu-config.json
    Backup location(s)...
    Source location #0 .............. C:\MyData\
    Searching for files...
    Backup destination: D:\MyBackupDirectory\
    Starting backup 'mybackupdirectory-20220530-234435'...
    Scheduling hashing jobs...
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202446.jpg
    Skipping unchanged file: C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    Skipping unchanged file: C:\MyData\Documents\MyImportantNotes.txt
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    Skipping unchanged file: C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    Skipping unchanged file: C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Heron\20220530_140645.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Heron\20220530_140532.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202504.jpg
    Skipping unchanged file: C:\MyData\Documents\Textually speaking, a novel in pure text.txt
    Skipping unchanged file: C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg
    Skipping unchanged file: C:\MyData\Documents\2021-Budget.xlsx
    Waiting for completion of remaining hashing jobs...
    Wait backup file operations to complete...
    Waiting for backup information to be saved...
    SpecificBackupInformation thread stop initiated. Finishing up...
    Saving in-progress backup information: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-234435.atbuinf.tmp
    Saving backup info file: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-234435.atbuinf
    Backup info file saved: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-234435.atbuinf
    Copying primary C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-234435.atbuinf to D:\MyBackupDirectory\.atbu\atbu-backup-info...
    SpecificBackupInformation background thread ending.
    0% completed of C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    100% completed of C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    BackupFile: Completed C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    Total bytes .............. 243
    SHA256 original file ..... 165ecb5443fd40764494cad1105003d9aa182b07746af6481fad0a7fa8aeefe2
    SHA256 encrypted file .... 8b06b5eced84e0d3fab78115c890ee40480a45ad40f3fc672fbe07ad1a37a237
    ---
    The backup information has been successfully backed up: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    All backup file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during backup.
    Total files ................................. 19
    Total unchanged files ....................... 19
    Total backup operations ..................... 0
    Total errors ................................ 0
    Total successful backups .................... 0
    Success, no errors detected.
    (venv2-3.9.12) PS C:\>

As you can see, despite 20210704_222527.jpg having been modified, the modification was not detected. This is because we modified 20210704_222527.jpg but reset its modified date/time back to the date/time before we modified it. 

Now let's try *incremental plus*... 

``atbu backup --incremental-plus C:\MyData\ D:\MyBackupDirectory\``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu backup --incremental-plus C:\MyData\ D:\MyBackupDirectory\
    atbu - v0.01
    Storage location: D:\MyBackupDirectory
    Storage definition: D:\MyBackupDirectory\.atbu\atbu-config.json
    Backup location(s)...
    Source location #0 .............. C:\MyData\
    Searching for files...
    Backup destination: D:\MyBackupDirectory\
    Starting backup 'mybackupdirectory-20220530-234752'...
    Scheduling hashing jobs...
    Waiting for completion of remaining hashing jobs...
    WARNING: Potential bitrot or sneaky corruption: File at path has same date/time and size as last backup but digest differs: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg modified_utc=2021-07-05T05:25:32.000000+00:00 size=722770 digest_now=0c4ab3650a9c78a000fd5f02573ba67812104e9f50db4a03848c12aeea3ef856 digest_last=29de887060a6e62aaee6b339548f564d86630a521e99552aec18b9145a005291
    Wait backup file operations to complete...
    0% completed of C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    100% completed of C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    BackupFile: Completed C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    Total bytes .............. 227
    SHA256 original file ..... 0c4ab3650a9c78a000fd5f02573ba67812104e9f50db4a03848c12aeea3ef856
    SHA256 encrypted file .... ef98a98b6110f5cbb2cbeec30bbf2d65ec4366d1991a2d873854a0e1fef77860
    ---
    Backup succeeded: Pictures\Wildlife\Deer\20210704_222527.jpg
    Waiting for backup information to be saved...
    SpecificBackupInformation thread stop initiated. Finishing up...
    Saving in-progress backup information: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-234752.atbuinf.tmp
    Saving backup info file: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-234752.atbuinf
    Backup info file saved: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-234752.atbuinf
    Copying primary C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory-20220530-234752.atbuinf to D:\MyBackupDirectory\.atbu\atbu-backup-info...
    SpecificBackupInformation background thread ending.
    0% completed of C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    100% completed of C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    BackupFile: Completed C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    Total bytes .............. 227
    SHA256 original file ..... a4232f0e619681e3a1aaebe1ad84a45de284583c561bcdce7b942556a04dba85
    SHA256 encrypted file .... bddd476d0509acc0f1ac8e8946c527332a83cb8fce11243cc6b47e4fba7d0cb9
    ---
    The backup information has been successfully backed up: C:\Users\User\.atbu\atbu-backup-info\mybackupdirectory.atbuinf
    All backup file operations have completed.
    *******************************************
    *** The following errors were detected: ***
    *******************************************
    Type             Exception Path                                     Message
    ---------------- --------- ---------------------------------------- ------------------------------------------------------------
    unexpected state           C:\MyData\Pictures\Wildlife\Deer\2021070 WARNING: Potential bitrot or sneaky corruption: File at path
                               4_222527.jpg                             has same date/time and size as last backup but digest
                                                                        differs:
                                                                        path=C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
                                                                        modified_utc=2021-07-05T05:25:32.000000+00:00 size=722770 di
                                                                        gest_now=0c4ab3650a9c78a000fd5f02573ba67812104e9f50db4a03848
                                                                        c12aeea3ef856 digest_last=29de887060a6e62aaee6b339548f564d86
                                                                        630a521e99552aec18b9145a005291
    Total files ................................. 19
    Total unchanged files ....................... 18
    Total backup operations ..................... 1
    Total errors ................................ 1
    Total successful backups .................... 1
    Some errors were detected. See prior messages and/or logs for details.
    (venv2-3.9.12) PS C:\>

You can see from the above that incremental plus detected the changed file's content. How did it do this?

|PROJNAME| was able to detect the bitrot because incremental plus re-calculates each file's special large number, its digest (or "hash"). While recalculating all digests is relatively CPU-intensive, and requires more hard drive activity, it is also more comprehensive, able to detect bitrot and other sneaky changes. This because using digest-based change detection is almost like comparing the file's content with the content of files already backed up.

Note in the above that |PROJNAME| also has Incremental Plus Bitrot Detection on by default, which causes it to flag an error if it detects suspicious, potentially sneaky file modifications. |PROJNAME| still backs up the file, but at the same time it also produces an error to alert you to the potential. If you do not wish for |PROJNAME| to emit an error, you can use --no-detect-bitrot which will have |PROJNAME| output only an informational message about the potential.

As mentioned, even when |PROJNAME| detects the the potential issue, it continues to back up the file, assuming the change is intentional. Since all backup history is retained, you still have the original backed up if you end up considering this more recent backup to be bitrot or some other undesried sneaky change.

.. _exporting-backup-config:

Exporting your backup config/private key
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Generally, for important encrypted backups, a copy of the backup's private encryption key should be stored separately from the backup or client computer. The exported private key should be stored in a secure/safe location for disaster or other recovery situations, or to otherwise be able to install |PROJNAME| and re-create your backup configuration toward allowing decryption/restoration of the backup's files.

You can export your local backup's configuration and credentials (private key) with the following command:

``atbu creds export <backup_storage_location> <export_file_path.json>``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu creds export D:\MyBackupDirectory\ E:\MyUsbDir\my-backup-private-key-backup.json
    atbu - v0.01
    Getting storage definition MyBackupDirectory...
    Saving backup to E:\MyUsbDir\my-backup-private-key-backup.json ...
    Backup complete.
    (venv2-3.9.12) PS C:\>

Importing your backup config/private key
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If you need to recreate your |PROJNAME| installation, follow the steps to install |PROJNAME| and then use the import command to restore the backup's configuration and private key...

``atbu creds import D:\MyBackupDirectory\ E:\MyUsbDir\my-backup-private-key-backup.json``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu creds import D:\MyBackupDirectory\ E:\MyUsbDir\my-backup-private-key-backup.json
    atbu - v0.01
    Loading backup file E:\MyUsbDir\my-backup-private-key-backup.json...
    Restoring secrets from backup file to keyring.

    *** WARNING *** WARNING *** WARNING *** WARNING *** WARNING *** WARNING
    The storage definition 'MyBackupDirectory' exists. You are about to
    replace it with 'MyBackupDirectory'. If this is an encrypted backup
    where the private key is not backed up, you will lose access to all data
    in this backup if you delete this configuration.

    You are about to overwrite a backup storage definition.
    Are you certain you want to overwrite 'MyBackupDirectory'  [y/N] y<ENTER>
    Restoring MyBackupDirectory as MyBackupDirectory from E:\MyUsbDir\my-backup-private-key-backup.json
    Saving configuration D:\MyBackupDirectory\.atbu\atbu-config.json...
    Configuration updated... restore complete
    (venv2-3.9.12) PS C:\>

In the above example, it prompts you before overwriting the existing configuration. After this completes, it will restore the configuration, and write the encryption key to the store backing Pythin keyring for your platform.

Cloud Storage Backup/Restore
----------------------------

Overview
^^^^^^^^
With |PROJNAME|, you can pretty much perform same backup/restore commands with cloud backups as with local backups. The most challenging aspect of using |PROJNAME| with the cloud is likely the setup of the cloud account, credentials, etc. This section will walk through some of the basics of |PROJNAME| cloud backups, including setup. See your cloud provider's storage setup information for details specific to your provider.

For some, the information in this section may seem a bit overwhelming but perhaps do not worry. The following discusses a couple of different providers so is really covering more information than should be required by one person using one cloud storage provider.

Cloud Setup and Credentials
^^^^^^^^^^^^^^^^^^^^^^^^^^^
|PROJNAME| has so far been minimally tested with both Google Cloud Storage (GCS) and Azure Blob Storage (ABS) so this documentation will be focused on what may be required for those providers. Overtime, additionally information for other providers can be added as needed.

Generally speaking, for both GCS/ABS, you need to have a cloud account, the ability to use cloud storage with that account, all of which will not be discussed in this documentation. It is the result of your setup with your cloud provider that is the focus within this section.

The result of you setup will yield so-called credentials in a general sense. Very often for tranditional S3-style storage access, there is an "access key" or "key" (not to be confused with encryption key), and a "secret."

You can think of the storage "key" as the user name in a sense, and the secret as the password.

What this means is you will often need two pieces of important information to setup your cloud backup, the credential key and secret.

Some cloud storage providers allow for setting up a so-called "service account" which can be used to access cloud storage. In this case, you can download a service account .json credential file (i.e., an OAuth2 .json file associated with a service account). In this case, the .json file itself contains all the information needed to access the cloud storage. You might loosely consider the .json to act as a replacement for the "key" and "secret."

Finally, some cloud providers have a notion of a "project ID" associated with the account. GCS is one example of this. If you have a non-default project ID with GCS, you will want to include that in your configuration of |PROJNAME|.

**Recap:**

* Configuring |PROJNAME| for use with your cloud provider requires you to setup a cloud account with your chosen provider.
* You will need to download or copy/paste credentials from your cloud provider which you will use to configure |PROJNAME| so it can access your cloud storage.
* For S3 and other storage access, very often the credentials are the following:
    * An "access key" or "key."
    * An "secret."
* Some providers such as GCS, instead of copy/pasting a key/secret, you instead download of an OAuth2 .json credential file associated with a service account. In fact, with GCS, you can use a so-called compatibility mode which allows use of a key/secret, but they recommend using the newer OAuth2 .json credential file.
* For some providers, such as GCS, you might need to know your project ID. You can always try to configure |PROJNAME| without a project ID, but if you experience issues, you may want to add it to see if it resolve the issues.

Credential Examples
"""""""""""""""""""
The following are examples of credentials...

Azure Blob Storage key/secret might look like this:

.. code-block:: console

    Key=examplestorageaccount876123
    Secret=9nXnXge6zkdkDFkDW9dKfj2FJkDKjfkJDFKD3432/dfd6dfjkaKDJjfDkjfD&dffjk/2dGkdjfkdkfDKfkdjkE==

Google Storage compatbility credentials (aka "HMAC" credentials) might look like the follow:

.. code-block:: console

    Key=GOOG1EDFJKDKFJKDJFKJKDF939893849FD8D08F09DGD9890898EER8E9FD9F
    Secret=ArdkfBDXfYd9dfDFKJdf5d9C2jKdFdfkae3dVjki

Google Storage service account OAuth2 .json file downloaded to the local computer into the C:\\MyCredentials directory:

.. code-block:: console

    C:\\MyCrednetials\\example-service-account-c98754699abb.json

If you are using a service account with OAuth2 .json credentials, if you open it up, you will see it contains a bit of information, one being a field named client_email. When you configure |PROJNAME|, you can use the value of client_email anywhere a key or user name is required (example given later below).

An example of a service account client email field value might be:

``atbuserviceaccount8838384784782@project-name-2135551212.iam.gserviceaccount.com``

Given the above, if using a GCS account with OAuth2 .json credentials, your resulting "username" (aka key) and "password" (aka secret) that you would give to |PROJNAME| are as follows:

.. code-block:: console

    Username (aka key): atbuserviceaccount8838384784782@project-name-2135551212.iam.gserviceaccount.com
    Password (aka secret): C:\\MyCrednetials\\example-service-account-c98754699abb.json

When |PROJNAME| needs to access your GCS acocunt, it would use the .json file with the Google APIs.

Cloud Storage Setup
^^^^^^^^^^^^^^^^^^^
You can use your cloud provider's UI to configure a storage container/bucket to act as your backup's storage container/bucket. Optionally, if the cloud credentials you give to |PROJNAME| have permission for creating a container/bucket, you can have ATBU try to create the container for you (more on this below).

|PROJNAME| Cloud Setup
^^^^^^^^^^^^^^^^^^^^^^
This section will provide an overview on taking your cloud provider's credentials and using that information to configure a |PROJNAME| cloud Storage Definition. Storage Definition is the same |PROJNAME| gives to the configuration for any storage that can store a backup, whether local or cloud.

**Note**: The cloud backup/restore walkthroughs below create the cloud backup configurations using test credentials entirely from the command line. You can use the same commands shown below but omit both the cloud storage access key ("key") and access secret ("secret") and |PROJNAME| will prompt you for both, where you can copy/paste each directly into |PROJNAME|. It is highly recommended that you use this latter approach, and not specify key/secret on the command line, to avoid leaving a copy of key/secret within your command line history buffer, if enabled. 

By now you should have your cloud storage provider's credentials, which will consist of some kind of key or username, and some kind of password or secret (which may be a .json file in some cases).

The general command line to setup a cloud storage definition is as follows...

For Azure Blob Storage:

.. code-block:: console

    atbu creds create-storage-def my-backup-name libcloud azure_blobs my-storage-container-name key=<access_key>,secret=<secret_access_key>

For Google Storage:

.. code-block:: console

    atbu creds create-storage-def my-backup-name google google_storage my-storage-bucket-name key=<access_key>,secret=<secret_access_key>

In this case, <access_key>/<secret_access_key> are either your HMAC compat mode key/secret, or your .json client_email value (open .json to get it) and a path to the .json file.

If you are using a non-default project, you can specify the project ID as follows: 

.. code-block:: console

    atbu creds create-storage-def my-backup-name google google_storage my-storage-bucket-name key=<access_key>,secret=<secret_access_key>,project=<project_id>

You can see the commands for both Azure Blob Storage and Google Storage Services are pretty much the same.

The general format for create-storage-def is as follows:

atbu creds create-storage-def <interface> <provider> <container> key=<access_key>,secret=<secret_access_key>,[project=<project_id>] [--create-container]

where

* <interface>           <'filesystem','libcloud'|'google'>
* <provider>            <'filesystem'|'azure_blobs'|'google_storage'>
* <container>           The cloud storage container or bucket name.
* <key>                 storage key
* <secret_access_key>   storage secret
* <project_id>          project if required.

If you specify --create-container, |PROJNAME| will attempt to create the container for you. Some important points on container creation...

If you use --create-container, and you specify an explicit single container name such as "my-container" then that container must not already be in use or the creation will fail.

Alternatively, when using --create-container, you can specify a container name ending with an asterisk '*' which activates the |PROJNAME| auto-find capability which causes |PROJNAME| to use the specified container name as a base name to which it appends a code until finding an available name.

It is recommended that you use auto-find if you wish |PROJNAME| to create the container name, and you do not wish to control the specific name used (beyond the base name).

Addendum to the above, avoiding secrets on the Command line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
As mentioned earlier, you can avoid specifying secrets on the command line by omitting them from the command line. In that case, you will be prompted by |PROJNAME| to input them. You can manually enter or copy/paste them. 

For Azure Blob Storage, omit "key=<access_key>,secret=<secret_access_key>" as follows:

.. code-block:: console

    atbu creds create-storage-def my-backup-name libcloud azure_blobs my-storage-container-name

For Google Storage, omit "key=<access_key>,secret=<secret_access_key>" as follows:

.. code-block:: console

    atbu creds create-storage-def my-backup-name google google_storage my-storage-bucket-name

For Google Storage, if you wish to specify a project name, you can still do so on the command line as follows:

.. code-block:: console

    atbu creds create-storage-def my-backup-name google google_storage my-storage-bucket-name project=<project_id>

Basically, you can use either the command line or the console input to specify secrets. If you leave a required secret out of the command line, you will be prompted to enter it via the console.

Azure Example
^^^^^^^^^^^^^

.. code-block:: console

    atbu creds create-storage-def my-backup-name libcloud azure_blobs my-storage-container-name key=examplestorageaccount876123,secret=9nXnXge6zkdkDFkDW9dKfj2FJkDKjfkJDFKD3432/dfd6dfjkaKDJjfDkjfD&dffjk/2dGkdjfkdkfDKfkdjkE==

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu creds create-storage-def my-backup-name libcloud azure_blobs my-storage-container-name* key=examplestorageaccount876123,secret=9nXnXge6zkdkDFkDW9dKfj2FJkDKjfkJDFKD3432/dfd6dfjkaKDJjfDkjfD&dffjk/2dGkdjfkdkfDKfkdjkE== --create-container
    atbu - v0.01
    Keyring information:
    Key=storage-secret
    Service=my-backup-name
    Username=ATBU-storage-password
    Storage definition my-backup-name saved.
    The destination can be encrypted.
    Would you like encryption enabled? [Y/n]

    You can require the backup to ask for a password before starting a backup/restore,
    or you can allow a backup to proceed automatically without requiring your password.

    When you choose the automatic approach which does not require a password, you are
    allowing your backup 'private key' to be used automatically by this program. When
    doing this, your backup private key is stored in a manner where, not only this
    program, but other programs and people who have access to your computer or its
    contents may be able to access and use your private key.

    You can switch between requiring your password or using the automatic approach as
    needed/desired. Regardless of your choice, you should be certain to back up your
    security information (i.e., private key, related info) which you can do at any time.


    Choose whether to require password or not.
    Require a (p)assword or allow (a)utomatic use of your backup's private key?  [p/A]
    Creating key...created.
    Storing...
    Keyring information:
    Key=encryption-key
    Service=my-backup-name
    Username=ATBU-backup-enc-key
    Your key is stored.
    Saving C:\Users\User\.atbu\atbu-config.json
    C:\Users\User\.atbu\atbu-config.json has been saved.
    The storage definition 'my-backup-name' will be encrypted.
    Container name had the * auto-find/create indicator. Searching for unique container name using base name my-storage-container-name*...
    Found/created container name 'my-storage-container-name-0a43083b-5986-4ace-a378-2587a48648b0'.
    Updating configuration with that new name.
    Storage definition my-backup-name successfully created.
    (venv2-3.9.12) PS C:\>

In the above example, encryption was enabled without requiring the user to enter a password to begin the backup. Additionally, the container name ended with an asterisk '*' which caused container name auto-find to be used, where you can see the container name my-storage-container-name-0a43083b-5986-4ace-a378-2587a48648b0 was created/selected.


Google Storage S3-compat Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: console

    atbu creds create-storage-def my-backup-name google google_storage my-storage-container-name key=GOOG1EDFJKDKFJKDJFKJKDF939893849FD8D08F09DGD9890898EER8E9FD9F,secret=ArdkfBDXfYd9dfDFKJdf5d9C2jKdFdfkae3dVjki

The output for this command is similar to the other examples (see above and below).

Google Storage Service Account OAuth2 .json Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: console

    atbu creds create-storage-def my-backup-name google google_storage my-storage-container-name key=atbuserviceaccount8838384784782@project-name-2135551212.iam.gserviceaccount.com,secret=C:\\MyCrednetials\\example-service-account-c98754699abb.json,project=project-name-2135551212

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu creds create-storage-def my-backup-name google google_storage my-storage-container-name* key=atbuserviceaccount8838384784782@project-name-2135551212.iam.gserviceaccount.com,secret=C:\\MyCrednetials\\example-service-account-c98754699abb.json,project==project-name-2135551212 --create-container
    atbu - v0.01
    Secret seems to reference a file either directly or indirectly: C:\\MyCrednetials\\example-service-account-c98754699abb.json
    Secret will be considered a reference to a file: C:\\MyCrednetials\\example-service-account-c98754699abb.json
    Keyring information:
    Key=storage-secret
    Service=my-backup-name
    Username=ATBU-storage-password
    Storage definition my-backup-name saved.
    The destination can be encrypted.
    Would you like encryption enabled? [Y/n] y

    You can require the backup to ask for a password before starting a backup/restore,
    or you can allow a backup to proceed automatically without requiring your password.

    When you choose the automatic approach which does not require a password, you are
    allowing your backup 'private key' to be used automatically by this program. When
    doing this, your backup private key is stored in a manner where, not only this
    program, but other programs and people who have access to your computer or its
    contents may be able to access and use your private key.

    You can switch between requiring your password or using the automatic approach as
    needed/desired. Regardless of your choice, you should be certain to back up your
    security information (i.e., private key, related info) which you can do at any time.


    Choose whether to require password or not.
    Require a (p)assword or allow (a)utomatic use of your backup's private key?  [p/A] a
    Creating key...created.
    Storing...
    Keyring information:
    Key=encryption-key
    Service=my-backup-name
    Username=ATBU-backup-enc-key
    Your key is stored.
    Saving C:\Users\User\.atbu\atbu-config.json
    C:\Users\User\.atbu\atbu-config.json has been saved.
    The storage definition 'my-backup-name' will be encrypted.
    Container name had the * auto-find/create indicator. Searching for unique container name using base name my-storage-container-name*...
    Found/created container name 'my-storage-container-name-0a8bafdd-55d2-4390-b4a6-d262414da558'.
    Updating configuration with that new name.
    Storage definition my-backup-name successfully created.
    (venv2-3.9.12) PS C:\>


In the above example, encryption was enabled without requiring the user to enter a password to begin the backup. Additionally, the container name ended with an asterisk '*' which caused container name auto-find to be used, where you can see the container name my-storage-container-name-0a8bafdd-55d2-4390-b4a6-d262414da558 was created/selected.

Performing a full cloud backup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
With your local |PROJNAME| client setup with a cloud storage definition configuration, we can now perform a backup. Let's perform the same backup as performed with the earlier local backup example.

The command to backup from the local C:\MyData directory to the |PROJNAME| 'my-backup-name' storage definition is as follows....

``atbu backup --full C:\MyData storage:my-backup-name``

Note, you would use --incremental for incremental, and --incremental-plus for Incremental Plus. 

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu backup --full C:\MyData storage:my-backup-name
    atbu - v0.01
    Backup location(s)...
    Source location #0 .............. C:\MyData
    Searching for files...
    Backup destination: storage:my-backup-name
    No backup history for 'my-backup-name'. Creating new history database.
    Starting backup 'my-backup-name-20220527-115038'...
    Scheduling hashing jobs...
    Waiting for completion of remaining hashing jobs...
    Wait backup file operations to complete...
    Backing up: C:\MyData\Documents\2021-Budget.xlsx
    0% completed of C:\MyData\Documents\2021-Budget.xlsx
    Backing up: C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    0% completed of C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    Backing up: C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    0% completed of C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    Backing up: C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    0% completed of C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    Backing up: C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    0% completed of C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    BackupFile: Completed C:\MyData\Documents\2021-Budget.xlsx
    Total bytes .............. 6184
    SHA256 original file ..... 9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    SHA256 encrypted file .... 0f9f547c816205dd273e896b8855aa718682b3da532476840d96358aadeb5a49
    ---
    Backup succeeded: Documents\2021-Budget.xlsx
    Backing up: C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    0% completed of C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    BackupFile: Completed C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    Total bytes .............. 798387
    SHA256 original file ..... 6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    SHA256 encrypted file .... 2a284b6e955858a4e6b9a9cffb132b2f9844bd6c172105184717fdeefd48a6fc
    ---
    Backup succeeded: Pictures\SocialMedia\20211017_162445.jpg
    Backing up: C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    0% completed of C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    BackupFile: Completed C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    Total bytes .............. 722770
    SHA256 original file ..... 1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    SHA256 encrypted file .... 69f2830107989f4cdf88688c13a8e6f68eaa2724b9ebd99ed7c9952de14494f5
    ---
    Backup succeeded: Pictures\Wildlife\Deer\20210704_222527.jpg
    BackupFile: Completed C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    Total bytes .............. 2405069
    SHA256 original file ..... b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    SHA256 encrypted file .... d247baa36ce6f1468e7cdc469f630bbeae692f4af1478cbae0064f98f317613e

    ... (edited for brevity) ...

    ---
    94% completed of C:\MyData\Pictures\Yellowstone\20210702_202504.jpg
    BackupFile: Completed C:\MyData\Pictures\Yellowstone\20210702_202504.jpg
    Total bytes .............. 5564491
    SHA256 original file ..... c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    SHA256 encrypted file .... ff1f179a0537d52213b6e95458afbbaccf52df76fb22daf5e1e95b006cad53b9
    ---
    Backup succeeded: Pictures\Yellowstone\20210702_202504.jpg
    Waiting for backup information to be saved...
    SpecificBackupInformation thread stop initiated. Finishing up...
    Saving in-progress backup information: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-115038.atbuinf.tmp
    Saving backup info file: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-115038.atbuinf
    Backup info file saved: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-115038.atbuinf
    SpecificBackupInformation background thread ending.
    Backing up: C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    0% completed of C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    BackupFile: Completed C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    Total bytes .............. 22022
    SHA256 original file ..... 3be7dc579c36090dc9d681eab7a3c4290b9e4e66530d20500164b1bcc3f2e487
    SHA256 encrypted file .... 6a21b8136222307208ec10eceb6c675972543ca72af790de998bbeec7daf7fa2
    ---
    The backup information has been successfully backed up: C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    All backup file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during backup.
    Total files ................................. 17
    Total unchanged files ....................... 0
    Total file results .......................... 17
    Total errors ................................ 0
    Total successful backups .................... 0
    Success, no errors detected.
    (venv2-3.9.12) PS C:\>

Performing an incremental cloud backup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Let's try an incremental backup. Before doing so, let's outline that C:\MyData has changed as follows...

* Modified existing file: C:\\MyData\\Documents\\MyImportantNotes.txt
* Added new file: C:\\MyData\\Documents\\NewNotes.txt

The command to perform an incremental backup is as follows...

``atbu backup --incremental C:\MyData storage:my-backup-name``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu backup --incremental C:\MyData storage:my-backup-name
    atbu - v0.01
    Backup location(s)...
    Source location #0 .............. C:\MyData
    Searching for files...
    Backup destination: storage:my-backup-name
    Starting backup 'my-backup-name-20220527-115820'...
    Scheduling hashing jobs...
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg
    Skipping unchanged file: C:\MyData\Documents\Textually speaking, a novel in pure text.txt
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    Skipping unchanged file: C:\MyData\Documents\2021-Budget.xlsx
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
    Scheduling backup of file never backed up before: C:\MyData\Documents\NewNotes.txt
    Skipping unchanged file: C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg
    Skipping unchanged file: C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202446.jpg
    Skipping unchanged file: C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
    Skipping unchanged file: C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    Skipping unchanged file: C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    Skipping unchanged file: C:\MyData\Pictures\Yellowstone\20210702_202504.jpg
    Scheduling backup of changed file: C:\MyData\Documents\MyImportantNotes.txt cur_date=2022-05-27T04:56:21.956714 old_date=2022-05-26T23:08:24.625664 cur_size=46 old_size=34
    Waiting for completion of remaining hashing jobs...
    Wait backup file operations to complete...
    Backing up: C:\MyData\Documents\MyImportantNotes.txt
    0% completed of C:\MyData\Documents\MyImportantNotes.txt
    Backing up: C:\MyData\Documents\NewNotes.txt
    0% completed of C:\MyData\Documents\NewNotes.txt
    BackupFile: Completed C:\MyData\Documents\MyImportantNotes.txt
    Total bytes .............. 46
    SHA256 original file ..... 5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    SHA256 encrypted file .... 4d2002f598be365d0c27f8a5d5e4f85292ad7e56480728dd34b17285df99fe28
    ---
    Backup succeeded: Documents\MyImportantNotes.txt
    BackupFile: Completed C:\MyData\Documents\NewNotes.txt
    Total bytes .............. 14
    SHA256 original file ..... 6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    SHA256 encrypted file .... fe58e3cf279ab6d2f0a45e3a10c97baee74ce5fbfbd2e802786bfa2804fb264f
    ---
    Backup succeeded: Documents\NewNotes.txt
    Waiting for backup information to be saved...
    SpecificBackupInformation thread stop initiated. Finishing up...
    Saving in-progress backup information: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-115820.atbuinf.tmp
    Saving backup info file: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-115820.atbuinf
    Backup info file saved: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-115820.atbuinf
    SpecificBackupInformation background thread ending.
    Backing up: C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    0% completed of C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    BackupFile: Completed C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    Total bytes .............. 42521
    SHA256 original file ..... e19f5daa7728923dbfb5c72825bb66ad8e027d9949832217af690347a104755f
    SHA256 encrypted file .... 4159e6e44b554d62d4a4aa20fdbf73381e8351b8a77213cc4b45025cde9eba7d
    ---
    The backup information has been successfully backed up: C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    All backup file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during backup.
    Total files ................................. 18
    Total unchanged files ....................... 16
    Total file results .......................... 2
    Total errors ................................ 0
    Total successful backups .................... 0
    Success, no errors detected.
    (venv2-3.9.12) PS C:\>

From the above, we can see that two files need to be backed up, one being a new file, the other an existing file that was modified.

Performing an Incremental Plus De-Duplication cloud backup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
An |PROJNAME| Incremental Plus backup is similar to incremental but it determines if a file has changed not only on modified date/time and size, but by using the SHA256 digest as well. This requires generating digests for all files, even if they have already been backed up, so may not be desirable to do for each backup depending on your data directory size.

Additionally, |PROJNAME| Incremental Plus has de-duplication options which can be enabled, to be demostrated in this section.

Before we try Incremental Plus w/De-Duplication, let's make the following modifications to C:\MyData...

* Copy C:\\MyData\\Pictures to C:\\MyData\\Pictures2 which effectively duplicates about 30MB worth of data/pictures etc.
* Rename C:\\MyData\\Pictures2\\Wildlife\\Geese\\20210703_193235.jpg to 20210703_193235-DifferentName.jpg which means both files have the same content but different names in different folders.
* Rename C:\\MyData\\Pictures2\\Wildlife\\Geese\\20210703_193244.jpg to 20210703_193244-DifferentName.jpg which means both files have the same content but different names in different folders.

With the above changes in place, the command to perform an Incremental Plus backup are is as follows...

``atbu backup --incremental-plus --dedup digest C:\MyData storage:my-backup-name``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu backup --incremental-plus --dedup digest C:\MyData storage:my-backup-name
    atbu - v0.01
    Backup location(s)...
    Source location #0 .............. C:\MyData
    Searching for files...
    Backup destination: storage:my-backup-name
    Starting backup 'my-backup-name-20220527-121517'...
    Scheduling hashing jobs...
    Waiting for completion of remaining hashing jobs...
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\SocialMedia\20211017_162445.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Documents\2021-Budget.xlsx
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Events\2021-HolidayParty\20210826_191432.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Wildlife\Deer\20210704_222623.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\SocialMedia\20211119_230028.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Yellowstone\20210702_202446.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Wildlife\Geese\20210703_193235-DifferentName.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Wildlife\Deer\20210704_222527.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Wildlife\Geese\20210703_193244-DifferentName.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Yellowstone\20210702_202504.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Yellowstone\20210702_202203.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Events\2021-HolidayParty\20210704_223018.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Wildlife\Deer\20210704_222626.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Yellowstone\20210702_202437.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Documents\Textually speaking, a novel in pure text.txt
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Yellowstone\20210702_202504.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures2\Yellowstone\20210702_202530.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Documents\MyImportantNotes.txt
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg
    Skipping unchanged file (dedup='digest'): C:\MyData\Documents\NewNotes.txt
    Skipping unchanged file (dedup='digest'): C:\MyData\Pictures\Yellowstone\20210702_202446.jpg
    Wait backup file operations to complete...
    Waiting for backup information to be saved...
    SpecificBackupInformation thread stop initiated. Finishing up...
    Saving in-progress backup information: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-121517.atbuinf.tmp
    Saving backup info file: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-121517.atbuinf
    Backup info file saved: C:\Users\User\.atbu\atbu-backup-info\my-backup-name-20220527-121517.atbuinf
    SpecificBackupInformation background thread ending.
    Backing up: C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    0% completed of C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    BackupFile: Completed C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    Total bytes .............. 78213
    SHA256 original file ..... 922efa71ddf3daf40572d1d78fb79b60a7f4cd45a96adc695bd43b1ff397ee77
    SHA256 encrypted file .... 3e3e62b2e7a0f6b9c8cf34e3bc34c1b442f06ce5c256e804416245fd6e167b84
    ---
    The backup information has been successfully backed up: C:\Users\User\.atbu\atbu-backup-info\my-backup-name.atbuinf
    All backup file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during backup.
    Total files ................................. 32
    Total unchanged files ....................... 32
    Total file results .......................... 0
    Total errors ................................ 0
    Total successful backups .................... 0
    Success, no errors detected.
    (venv2-3.9.12) PS C:\>

You can see above, despite our both copying the Pictures folder, and renaming two of the files in the copy, |PROJNAME| was able to determine there were effectively no new files. It did this by checking SHA256 digests, file modified date/time, and file size against files already backed up.

In the above example, |PROJNAME| will indicate you have backed up all the specified files but it did not have to physically backup any files. The above took a few seconds to run.

Listing the cloud backup information
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
With the above various experiments performed, let's now list the contents of that same cloud backup.

Let's start with the basic list command...

``atbu list storage:my-backup-name``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu list storage:my-backup-name
    atbu - v0.01

    Storage Definition    Provider        Container                                                       Interface    Encrypted    Persisted IV
    --------------------  --------------  --------------------------------------------------------------  -----------  -----------  --------------
    my-backup-name        google_storage  my-storage-container-name-0a8bafdd-55d2-4390-b4a6-d262414da558  google       True         True
    (venv2-3.9.12) PS C:\>

We see the backup exists, it is using the google interface (the google APIs instead of libcloud), and it is encrypted.

Let's see how many backups have been performed with the following list command...

``atbu list storage:my-backup-name backup:*``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu list storage:my-backup-name backup:*
    atbu - v0.01

    Storage Definition    Provider        Container                                                       Interface    Encrypted    Persisted IV
    --------------------  --------------  --------------------------------------------------------------  -----------  -----------  --------------
    my-backup-name        google_storage  my-storage-container-name-0a8bafdd-55d2-4390-b4a6-d262414da558  google       True         True
    Specific backups from storage definition 'my-backup-name'
    my-backup-name-20220527-121517
    my-backup-name-20220527-115820
    my-backup-name-20220527-115038
    (venv2-3.9.12) PS C:\>

We can see 3 backups have been performed. They are listed most recent first. They are as follows...

* my-backup-name-20220527-115038: Our initial full backup.
* my-backup-name-20220527-115820: Our normal incremental backup.
* my-backup-name-20220527-121517: Our de-duplicating Incremental Plus backup.

Let's look at the details of what was backed up in our most recent de-duplicating backup, my-backup-name-20220527-121517, by using the following command...

``atbu list storage:my-backup-name backup:my-backup-name-20220527-121517 files:*``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu list storage:my-backup-name backup:my-backup-name-20220527-121517 files:*
    atbu - v0.01

    Storage Definition    Provider        Container                                                       Interface    Encrypted    Persisted IV
    --------------------  --------------  --------------------------------------------------------------  -----------  -----------  --------------
    my-backup-name        google_storage  my-storage-container-name-0a8bafdd-55d2-4390-b4a6-d262414da558  google       True         True
    Specific backups from storage definition 'my-backup-name'
    my-backup-name-20220527-121517
        C:\MyData\Documents\2021-Budget.xlsx
        C:\MyData\Documents\MyImportantNotes.txt
        C:\MyData\Documents\NewNotes.txt
        C:\MyData\Documents\Textually speaking, a novel in pure text.txt
        C:\MyData\Pictures2\Events\2021-HolidayParty\20210704_223018.jpg
        C:\MyData\Pictures2\Events\2021-HolidayParty\20210826_191432.jpg
        C:\MyData\Pictures2\SocialMedia\20211017_162445.jpg
        C:\MyData\Pictures2\SocialMedia\20211119_230028.jpg
        C:\MyData\Pictures2\Wildlife\Deer\20210704_222527.jpg
        C:\MyData\Pictures2\Wildlife\Deer\20210704_222623.jpg
        C:\MyData\Pictures2\Wildlife\Deer\20210704_222626.jpg
        C:\MyData\Pictures2\Wildlife\Geese\20210703_193235-DifferentName.jpg
        C:\MyData\Pictures2\Wildlife\Geese\20210703_193244-DifferentName.jpg
        C:\MyData\Pictures2\Yellowstone\20210702_202203.jpg
        C:\MyData\Pictures2\Yellowstone\20210702_202437.jpg
        C:\MyData\Pictures2\Yellowstone\20210702_202446.jpg
        C:\MyData\Pictures2\Yellowstone\20210702_202504.jpg
        C:\MyData\Pictures2\Yellowstone\20210702_202530.jpg
        C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
        C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
        C:\MyData\Pictures\SocialMedia\20211017_162445.jpg
        C:\MyData\Pictures\SocialMedia\20211119_230028.jpg
        C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
        C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg
        C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
        C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg
        C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202437.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202446.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202504.jpg
        C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    (venv2-3.9.12) PS C:\>

As you can see, it shows that both Pictures and Picture2 were backed up even though we know Pictures2 was not physically backed up. 

Restore files from a cloud backup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Now let's restore that last de-duplicated Incremental Plus backup and see what actually gets restored. We will use the following restore command...

``atbu restore storage:my-backup-name backup:last files:* C:\MyRestore2``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu restore storage:my-backup-name backup:last files:* C:\MyRestore2
    atbu - v0.01
    Will restore 32 files from 'my-backup-name'
    Starting restore from 'my-backup-name'...
    Scheduling restore jobs...
    Wait for restore file operations to complete...
    0% completed of C:\MyRestore2\Documents\NewNotes.txt
    RestoreFile: Completed for C:\MyRestore2\Documents\NewNotes.txt
    Total bytes ............................... 14
    SHA256 download ........................... 6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    SHA256 original ........................... 6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    SHA256 encrypted download ................. fe58e3cf279ab6d2f0a45e3a10c97baee74ce5fbfbd2e802786bfa2804fb264f
    SHA256 encrypted original ................. fe58e3cf279ab6d2f0a45e3a10c97baee74ce5fbfbd2e802786bfa2804fb264f
    Restore succeeded: Documents\NewNotes.txt

    ... (edited for brevity) ...

    0% completed of C:\MyRestore2\Pictures2\Wildlife\Geese\20210703_193235-DifferentName.jpg
    0% completed of C:\MyRestore2\Pictures2\Yellowstone\20210702_202203.jpg
    RestoreFile: Completed for C:\MyRestore2\Pictures2\Wildlife\Geese\20210703_193235-DifferentName.jpg
    Total bytes ............................... 2858016
    SHA256 download ........................... a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    SHA256 original ........................... a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    SHA256 encrypted download ................. 4bfe636eed69858cad271ac6f79b523d5ab423e37928b87a68963a6c0dbccc38
    SHA256 encrypted original ................. 4bfe636eed69858cad271ac6f79b523d5ab423e37928b87a68963a6c0dbccc38
    Restore succeeded: Pictures2\Wildlife\Geese\20210703_193235-DifferentName.jpg
    RestoreFile: Completed for C:\MyRestore2\Pictures2\Yellowstone\20210702_202203.jpg
    Total bytes ............................... 2115565
    SHA256 download ........................... 41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    SHA256 original ........................... 41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    SHA256 encrypted download ................. f79d41b6ddc38a60d9f0db859e26a3d101ad9c41c16abfaa0cb29ea1579415d3
    SHA256 encrypted original ................. f79d41b6ddc38a60d9f0db859e26a3d101ad9c41c16abfaa0cb29ea1579415d3
    Restore succeeded: Pictures2\Yellowstone\20210702_202203.jpg
    0% completed of C:\MyRestore2\Pictures2\Wildlife\Geese\20210703_193244-DifferentName.jpg
    RestoreFile: Completed for C:\MyRestore2\Pictures2\Wildlife\Geese\20210703_193244-DifferentName.jpg
    Total bytes ............................... 2405069
    SHA256 download ........................... b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    SHA256 original ........................... b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    SHA256 encrypted download ................. d247baa36ce6f1468e7cdc469f630bbeae692f4af1478cbae0064f98f317613e
    SHA256 encrypted original ................. d247baa36ce6f1468e7cdc469f630bbeae692f4af1478cbae0064f98f317613e
    Restore succeeded: Pictures2\Wildlife\Geese\20210703_193244-DifferentName.jpg

    ... (edited for brevity) ...

    0% completed of C:\MyRestore2\Pictures\Wildlife\Geese\20210703_193235.jpg
    RestoreFile: Completed for C:\MyRestore2\Pictures\Wildlife\Geese\20210703_193235.jpg
    Total bytes ............................... 2858016
    SHA256 download ........................... a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    SHA256 original ........................... a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    SHA256 encrypted download ................. 4bfe636eed69858cad271ac6f79b523d5ab423e37928b87a68963a6c0dbccc38
    SHA256 encrypted original ................. 4bfe636eed69858cad271ac6f79b523d5ab423e37928b87a68963a6c0dbccc38
    Restore succeeded: Pictures\Wildlife\Geese\20210703_193235.jpg
    0% completed of C:\MyRestore2\Pictures\Wildlife\Geese\20210703_193244.jpg
    0% completed of C:\MyRestore2\Pictures\Yellowstone\20210702_202203.jpg
    RestoreFile: Completed for C:\MyRestore2\Pictures\Wildlife\Geese\20210703_193244.jpg
    Total bytes ............................... 2405069
    SHA256 download ........................... b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    SHA256 original ........................... b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    SHA256 encrypted download ................. d247baa36ce6f1468e7cdc469f630bbeae692f4af1478cbae0064f98f317613e
    SHA256 encrypted original ................. d247baa36ce6f1468e7cdc469f630bbeae692f4af1478cbae0064f98f317613e
    Restore succeeded: Pictures\Wildlife\Geese\20210703_193244.jpg

    ... (edited for brevity) ...

    All restore file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during restore.
    Total files ................................. 32
    Total errors ................................ 0
    Total success ............................... 32
    Finished... no errors detected.
    (venv2-3.9.12) PS C:\>

The above output was edited to keep it relatively brief, but the restored "Geese" files in both Pictures and Pictures2 were left in place so you can see all were restored. This shows that, while Pictures2 was never physically backed up, it has been effectively de-duplicated by |PROJNAME| Incremental Plus with de-duplication active.

Backup/Restore Walkthrough Conclusion
-------------------------------------

|PROJNAME| is a command-line Python command-line application that allows for encrypted backup/restore to local and cloud storage. It provides traditional full and incremental backup capabilities along with Incremental Plus w/de-duplication. 

The verbose output of the tool is by design. The tool is meant for people who are power users who want to see backup detailed of backups. |PROJNAME| source code is fully available, can be scrutinized/understood.

With a world full of personal data, one of the goals of |PROJNAME| is to provide something to anyone who needs the ability to safely manage their memories, documents, life's data. Whether it fulfills that goal remains to be seen... more testing and usage is required to truly get to that point. It is truly a personal application being shared.

I needed something that was always available, consistent in behavior, captured and retained history even across ad-hoc/disconnected usage, easy to modify as needed, relatively open, and, most importantly, something providing the features I needed. I do not want to rename a 10GB file and have to incur a storage impact for doing so, and I want to control when I apply that ability in a simple manner. I want to invest my backup efforts in a format that will always be available, that is open, that i can tweak as needed. To achieve all of that, I created |PROJNAME|. |PROJNAME| is a personal utility of my own which I am sharing.
