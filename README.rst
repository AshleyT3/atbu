.. |PROJNAMELONG| replace:: ATBU Backup & Persistent File Information
.. |PROJNAME| replace:: ATBU
.. |PKGNAME| replace:: atbu-pkg

TL;DR: |PROJNAMELONG| is a local/cloud backup/restore command-line utility with optional deduplication and bitrot detection, plus a little utility with useful digest-based directory file diff'ing. Click to go to Setup, then read desired walkthroughs. Software is alpha.

Documentation: https://atbu.readthedocs.io/en/latest/

The following is a subset of the documentation at the link above.

.. contents:: **Contents**
    :depth: 3

Overview
========
Intro - READ THIS FIRST!
------------------------
|PROJNAME| is a Python command line utility with two general areas of features as follows...

* **Backup/Restore:** Cloud and local backup/restore/verify, including deduplication capabilities, bitrot detection, and more.
* **Persistent file information:** A relatively simple but useful utility to diff/compare directories to gain insight into undesired file duplication, missing expected redundancy, and bitrot detection.

**IMPORTANT:**

* This tool should be considered "alpha" as of May 2022.
* Given |PROJNAME|'s alpha state, please do not use it as your primary/only backup/restore tool. Have redundancy elsewhere. Your test-driving is welcome, just be reasonably cautious.
* The walkthroughs outline the most tested/common scenarios.
* This is my own personal utility being shared via open source. I need more time actually using it to speak more confidently about it, to eventually remove these precautionary bullet points.

For developers, those viewing the source code:

* Beyond ad-hoc Python usage here/there, this project is my first significant Python coding in more than 10 years.
* I had to essentially learn Python again, to come back up to speed on many aspects of the language in short order.
* Forgive any source code which may not be written in the most appropriate Pythonic manner. (Feedback welcome!)
* It really was an ad-hoc tool for my own usage at the start... but then seemed like a good opportunity to try out the whole github/OSS thing from a creator standpoint.

Highlights
----------

* **Backup** local files to either local drives or cloud storage faciltiies.
   * Use the same command-line tool to perform **full**, **incremental**, or **incremental Plus** backups to a local folder on any drive, or the cloud.
   * **Verify/Restore** files using the same command line tool.
   * View listings and information of backups.
   * Optionally utilize **SHA256-based de-duplication capabilities.** (Incremental Plus and Increment Plus with de-duplication)
   * **Encryption/decryption keys are completely under your control.**
   * Support for YubiKey HMAC-SHA1 backup encryption key protection.
   * Some perhaps useful technical details:
      * **Uses libcloud** so can likely easily be configured for at least some libcloud storage providers (currently tested for Azure Storage and Google Cloud Storage).
      * Uses **multipart uploads** and will keep trying to upload "forever" until you make it stop so goal is for it to be resilient to network disconnections/disruptions.
      * Written in Python, fully command-line driven, with logging output for max detail for those who like to see the operations taking place.
            * Examine the source code, understand how your files are backed up and restored, or simply gain confidence by hearing about those details from technical experts you trust.
            * Have peace of mind that the tool is available for use when you need it. Just download Python, install the tool, begin backing up or restoring.
* **File integrity and duplication management** capabilities...
   * Scan folders of cherished media to **detect bitrot.**
   * **Gain insight toward helping with personal data consolidation/redundancy management:** Scan and compare hard drives and folders to detect duplication you might want to retire in order to, as one example, reallocate devices, or discover lack of duplication (redundancy) where you expected it.
      * Helps with manual review/consolidation efforts around cherised data/media files.
   * In addition to offline copies you can maintain of persistent file information, you can optionally instruct the tool to keep small persistent information sidecar files side-by-side next to cherished large media files (i.e., videos/photos), allowing you detect changes based on not only modified time/size changes, but also content changes.

The remainder of this page is the getting started followed by walkthroughs for the two general areas outlined above. This README is a bit long but there's a contents section at the top to help you navigate it. I will look into setting up readthedocs.io but at this time, I just needed to get the repo going.

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

By now you should have your cloud storage provider's credentials, which will consist of some kind of key or username, and some kind of password or secret (which may be a .json file in some cases).

The general command line to setup a cloud storage definition is as follows...

For Azure Blob Storage:

.. code-block:: console

    atbu creds create-storage-def my-backup-name libcloud azure_blobs my-storage-container-name key=<access_key>,secret=<secret>

For Google Storage:

.. code-block:: console

    atbu creds create-storage-def my-backup-name google google_storage my-storage-bucket-name key=<access_key>,secret=<secret>

In this case, <access_key>/<secret> are either your HMAC compat mode key/secret, or your .json client_email value (open .json to get it) and a path to the .json file.

If you are using a non-default project, you can specify the project ID as follows: 

.. code-block:: console

    atbu creds create-storage-def my-backup-name google google_storage my-storage-bucket-name key=<access_key>,secret=<secret>,project=<project_id>

You can see the commands for both Azure Blob Storage and Google Storage Services are pretty much the same.

The general format for create-storage-def is as follows:

atbu creds create-storage-def <interface> <provider> <container> key=<key>,secret=<secret>,[project=<project_id>] [--create-container]

where

* <interface>    <'filesystem','libcloud'|'google'>
* <provider>     <'filesystem'|'azure_blobs'|'google_storage'>
* <container>    The cloud storage container or bucket name.
* <key>          storage key
* <secret>       storage secret
* <project_id>   project if required.

If you specify --create-container, |PROJNAME| will attempt to create the container for you. Some important points on container creation...

If you use --create-container, and you specify an explicit single container name such as "my-container" then that container must not already be in use or the creation will fail.

Alternatively, when using --create-container, you can specify a container name ending with an asterisk '*' which activates the |PROJNAME| auto-find capability which causes |PROJNAME| to use the specified container name as a base name to which it appends a code until finding an available name.

It is recommended that you use auto-find if you wish |PROJNAME| to create the container name, and you do not wish to control the specific name used (beyond the base name).

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

|PROJNAME| Persistent File Information Getting Started
=========================================================

Setup
-----

|PROJNAME| has been tested on Python 3.9.12 and higher... so first install Python, possibly creating a virtual environment if you wish.

After your environment is setup with Python...

To use |PROJNAME|, first install it using pip |PKGNAME|:

.. code-block::

   pip install |PKGNAME|


.. contents:: Table of Contents
    :depth: 3

Persistent File Information
---------------------------

Overview
^^^^^^^^
Following is a highlevel overview followed by a few walkthroughs. See :ref:`label_detailed_overview` for additional details.

The persistent file information portion of |PROJNAME| contains the following commands:

* **update-digests:** For each file in a directory, capture file information, including the SHA256 digest, last modified date/time, and size, and persist that captured file information to either an .atbu sidecar file, or a single .json database file located at the root of search directory where the file was found.
    * An .atbu sidecar file is a file that has the same name as a file whose information it holds except its suffix or extension is .atbu.
    * A single .json database file is a json file located at the root of the search directory of the file's whose information is being gathered.
    * The tradeoff betweeen sidecar and single .json database file will be discussed in details later in this section.
* **save-db:** Given one or more directories (aka "locations") where ``update-digests`` has been run, where there exists persistent file information (either sidecar or .json database), gather all such persistent file information and place it into a single .json database file at the path you specify.
    * Using this command, you can gather information one or more directories, located on any drives, and store it in a single .json database file.
    * This can be useful for keeping a .json online as a form of file inventory when the drives relating to the information are disconnected/offline. You can still perform diff commands (see next bullet) without the drives connected. A demo of this is later in this section.
* **diff:** Given two locations, A and B, each of which can be either a directory or an |PROJNAME| persistent file information .json database file, perform a diff of A and B toward producing a report of what files in A are not within B, optionally performing a remove or move action on duplicates.
    * This can be used for figuring out what files are backed up and where. If you are trying to get rid of old hard drives, or consolidate data onto newer media, perhaps to use semi-older media for new purposes, you can use this diff feature to help in your overall efforts to gain assurance as you retire or repurpose media.
    * You can also detect issues such as bitrot by recreating digests for files on data drives, comparing them with known good copies of the captured digests.
* Whether you use sidecar files or a single .json database will depend solely on your preferences. There are tradeoffs to each approach:
    * Generally, sidecar files are perferred for large or important irresplaceable media (photos/videos) which you never expect any application to edit, where you want to keep a sidecar file next to that media file so that it is copied anywhere that media file goes. Since the sidecar file retains a history of any digest or other changes, the ``update-digests`` command along with the sidecar file history can be a way of understanding when changes occurred, and detecting changes to content when such changes are not expected.
    * A single .json db in the root folder does not clutter your folders. Such clutter may be reasonable for large media storage (videos, photos) of irreplacable media. The files are often large, the integirty of those files is important, so a small sidecar file may be seen as worth it. By contrast, for a directory of relatively mundane but not unimportant files, text files, etc., may be more deserving of a single .json db rather than a sidecar for small and/or unimportant text files.
    * If you move a data file (i.e., media/photo/video or whatever your use case is) with its sidecar .atbu file, all information is immediately available at the new location without re-scanning the new folder with ``update-digests``. By contrast, if you move a file within a directory, tracked by a single .json db, to a new directory, both the new and old directory need to be rescanned by ``update-digests`` to update each directory's .json db file.
* See  :ref:`label_detailed_overview` for more details. 

Update Digests
^^^^^^^^^^^^^^
We have two directories:

* C:\\MyData which is the main data drive on PC.
* D:\\MyData which is a backup on an external hard drive.

Both directories contain the following contents:

.. code-block:: console

    C:\MyData
    ├───Documents
    │       2021-Budget.xlsx
    │       MyImportantNotes.txt
    │       NewNotes.txt
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

Let's capture persistent file information for all files in both C:\\MyData and D:\\MyData by running the following command:

``atbu update-digests C:\MyData\ D:\MyData\``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests C:\MyData\ D:\MyData\
    atbu - v0.01
    Updating files in C:\MyData...
    Creating info for C:\MyData\Documents\2021-Budget.xlsx...
    Checking for changes to C:\MyData\Documents\2021-Budget.xlsx...
    The file info was added: path=C:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Creating info for C:\MyData\Documents\MyImportantNotes.txt...
    Checking for changes to C:\MyData\Documents\MyImportantNotes.txt...
    The file info was added: path=C:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Creating info for C:\MyData\Documents\NewNotes.txt...
    Checking for changes to C:\MyData\Documents\NewNotes.txt...
    The file info was added: path=C:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Creating info for C:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    Checking for changes to C:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was added: path=C:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Creating info for C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was added: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Creating info for C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was added: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Creating info for C:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was added: path=C:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Creating info for C:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was added: path=C:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Creating info for C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was added: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Creating info for C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was added: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Creating info for C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was added: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Creating info for C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was added: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Creating info for C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was added: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .................................... C:\MyData
        Location total files ........................ 18
        Location files info created ................. 18
        Location files info updated ................. 0
        Location files no update required ........... 0
        Location files info stale/error, skipped..... 0
    Updating files in D:\MyData...
    Creating info for D:\MyData\Documents\2021-Budget.xlsx...
    Checking for changes to D:\MyData\Documents\2021-Budget.xlsx...
    The file info was added: path=D:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Creating info for D:\MyData\Documents\MyImportantNotes.txt...
    Checking for changes to D:\MyData\Documents\MyImportantNotes.txt...
    The file info was added: path=D:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Creating info for D:\MyData\Documents\NewNotes.txt...
    Checking for changes to D:\MyData\Documents\NewNotes.txt...
    The file info was added: path=D:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Creating info for D:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    Checking for changes to D:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was added: path=D:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Creating info for D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was added: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Creating info for D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was added: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Creating info for D:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was added: path=D:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Creating info for D:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was added: path=D:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Creating info for D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was added: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Creating info for D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was added: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Creating info for D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was added: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Creating info for D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was added: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Creating info for D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was added: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Creating info for D:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was added: path=D:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Creating info for D:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was added: path=D:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Creating info for D:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was added: path=D:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Creating info for D:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was added: path=D:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Creating info for D:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was added: path=D:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .................................... D:\MyData
        Location total files ........................ 18
        Location files info created ................. 18
        Location files info updated ................. 0
        Location files no update required ........... 0
        Location files info stale/error, skipped..... 0
    -------------------------------------------------------------------------
    Total all locations processed:
        Total files ................................. 36
        Total Files info created .................... 36
        Total files info updated .................... 0
        Total files no update required .............. 0
        Total files info stale/error, skipped........ 0
    (venv2-3.9.12) PS C:\>


The above ``update-digests`` command creates a persistent file information .json database in both C:\\MyData and D:\\MyData as follows:

.. code-block:: console

    (venv2-3.9.12) PS C:\> dir C:\MyData
        Directory: C:\MyData
    Mode                 LastWriteTime         Length Name
    ----                 -------------         ------ ----
    d-----         5/27/2022   4:56 AM                Documents
    d-----         5/26/2022  11:07 PM                Pictures
    -a----         5/27/2022  12:28 PM          16152 c4198ead-0b50-4f0e-b52b-685b64e7b9f0.atbudb

    (venv2-3.9.12) PS C:\> dir D:\MyData\

        Directory: D:\MyData
    Mode                 LastWriteTime         Length Name
    ----                 -------------         ------ ----
    d-----         5/27/2022  12:08 PM                Documents
    d-----         5/27/2022  12:08 PM                Pictures
    -a----         5/27/2022  12:28 PM          16152 c4198ead-0b50-4f0e-b52b-685b64e7b9f0.atbudb

    (venv2-3.9.12) PS C:\>

The name ``c4198ead-0b50-4f0e-b52b-685b64e7b9f0.atbudb`` is a unique name chosen by |PROJNAME| for its .json db file.

Diff Locations
^^^^^^^^^^^^^^
With both C:\\MyData and D:\\MyData each having an updated persistent file information database, let's diff them as follows:

``atbu diff C:\MyData\ D:\MyData\``

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu diff C:\MyData\ D:\MyData\
    atbu - v0.01
    Location A ............................. C:\MyData
    Location A persist types ............... ['per-dir']
    Location B ............................. D:\MyData
    Location B persist types ............... ['per-dir']
    Searching location A: C:\MyData
    Checking for changes to C:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=C:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to C:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to C:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to C:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=C:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=C:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=C:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Searching location B: D:\MyData
    Checking for changes to D:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=D:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to D:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=D:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to D:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=D:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to D:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=D:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=D:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=D:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Logging A unique objects ..... 18
    Logging B unique objects ..... 18
    Location A and B digests match: sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6 2021-Budget.xlsx
    Location A and B digests match: sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9 MyImportantNotes.txt
    Location A and B digests match: sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069 NewNotes.txt
    Location A and B digests match: sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f Textually speaking, a novel in pure text.txt
    Location A and B digests match: sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f 20210704_223018.jpg
    Location A and B digests match: sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0 20210826_191432.jpg
    Location A and B digests match: sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200 20211017_162445.jpg
    Location A and B digests match: sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814 20211119_230028.jpg
    Location A and B digests match: sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581 20210704_222527.jpg
    Location A and B digests match: sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e 20210704_222623.jpg
    Location A and B digests match: sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872 20210704_222626.jpg
    Location A and B digests match: sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4 20210703_193235.jpg
    Location A and B digests match: sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e 20210703_193244.jpg
    Location A and B digests match: sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a 20210702_202203.jpg
    Location A and B digests match: sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090 20210702_202437.jpg
    Location A and B digests match: sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774 20210702_202446.jpg
    Location A and B digests match: sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309 20210702_202504.jpg
    Location A and B digests match: sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23 20210702_202530.jpg
    All items in Location A were found in Location B
    Location A ...................................................... C:\MyData
    Location B ...................................................... D:\MyData
    Total Location A unique files ................................... 18
    Total Location A skipped files .................................. 0
    Total Location B unique files ................................... 18
    Total Location B skipped files .................................. 0
    Total Location A unique files also in Location B ................ 18
    Total Location A unique files not found in Location B ........... 0
    (venv2-3.9.12) PS C:\>

If we are expecting both locations to be identical, a key piece of information above is the message ``"All items in Location A were found in Location B."``

Let's simulate some bitrot by modifying one byte in the following file:

* D:\\MyData\\Pictures\\Wildlife\\Deer\\20210704_222527.jpg

.. code-block:: console

    (venv2-3.9.12) PS C:\> $f = Get-Item D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg; $lw = $f.LastWriteTime
    (venv2-3.9.12) PS C:\> $lw
    Sunday, July 4, 2021 10:25:32 PM
    (venv2-3.9.12) PS C:\> # At this point, I used a binary editor to modify one byte in the file.
    (venv2-3.9.12) PS C:\> $f = Get-Item D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg; $lw2 = $f.LastWriteTime
    (venv2-3.9.12) PS C:\> $lw2
    Friday, May 27, 2022 12:45:21 PM
    (venv2-3.9.12) PS C:\> $f.LastWriteTime = $lw
    (venv2-3.9.12) PS C:\> (Get-Item D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg).LastWriteTime
    Sunday, July 4, 2021 10:25:32 PM
    (venv2-3.9.12) PS C:\>

Now the D:\\MyData copy of the file has a one byte difference, with the file modified date/time and size unchanged.

|PROJNAME| can detect changes a few different ways. The default way is to observe changes in a file's modified date/time or size. This is fast/efficient and is fine for more situations where one might be looking for changes to a file caused by use of the operating system's APIs. For some issues, though, like bitrot, it is the natural disk which deteriorates, where changes to the disk are not caused by the operating system, but by natural causes which generally will not change the file's size or modified date/time (unless bitrot changes that information too). 

For cases like bitrot, we cannot merely use the default. We need to use digest change detection which itself implies digest re-generation for the sake of such detection.

In our example scenario, let's say it has been many years since D:\\MyData was created. Normally, by default, the ``update-digests`` command will only update digests for files whose modified date/time and/or size has changed (``--change-detection-type datesize``). Since our goal is to detect potential bit changes that would not affect either the date/time or size, we will instead specify ``--change-detection-type digest`` to recalculate digests for all files. If any digests have been changed, the persistent information for that file will be updated as follows...

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests --change-detection-type digest D:\MyData\
    atbu - v0.01
    Updating files in D:\MyData...
    Checking for changes to D:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=D:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to D:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=D:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to D:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=D:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to D:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=D:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=D:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=D:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    Updating file info for D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was updated: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=29de887060a6e62aaee6b339548f564d86630a521e99552aec18b9145a005291
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .................................... D:\MyData
        Location total files ........................ 18
        Location files info created ................. 0
        Location files info updated ................. 1
        Location files no update required ........... 17
        Location files info stale/error, skipped..... 0
    -------------------------------------------------------------------------
    Total all locations processed:
        Total files ................................. 18
        Total Files info created .................... 0
        Total files info updated .................... 1
        Total files no update required .............. 17
        Total files info stale/error, skipped........ 0
    (venv2-3.9.12) PS C:\>

The above recalculated all digests for files within D:\\MyData, where we can see 1 file had a digest mismatched to the last captured persistent info state. In this example, that would have been about 5 years ago. In the above, we also see the following message...

``Updating file info for D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg``

...which indicates 20210704_222527.jpg has changed. 

With the persistent info of D:\\MyData up to date, let's perform another diff between C:\\MyData and D:\\MyData...

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu diff C:\MyData\ D:\MyData\
    atbu - v0.01
    Location A ............................. C:\MyData
    Location A persist types ............... ['per-dir']
    Location B ............................. D:\MyData
    Location B persist types ............... ['per-dir']
    Searching location A: C:\MyData
    Checking for changes to C:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=C:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to C:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    ... (edited for brevity) ...
    Logging A unique objects ..... 18
    Logging B unique objects ..... 18
    Location A and B digests match: sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6 2021-Budget.xlsx
    Location A and B digests match: sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9 MyImportantNotes.txt
    Location A and B digests match: sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069 NewNotes.txt
    Location A and B digests match: sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f Textually speaking, a novel in pure text.txt
    Location A and B digests match: sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f 20210704_223018.jpg
    Location A and B digests match: sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0 20210826_191432.jpg
    Location A and B digests match: sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200 20211017_162445.jpg
    Location A and B digests match: sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814 20211119_230028.jpg
    Location A and B digests match: sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e 20210704_222623.jpg
    Location A and B digests match: sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872 20210704_222626.jpg
    Location A and B digests match: sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4 20210703_193235.jpg
    Location A and B digests match: sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e 20210703_193244.jpg
    Location A and B digests match: sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a 20210702_202203.jpg
    Location A and B digests match: sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090 20210702_202437.jpg
    Location A and B digests match: sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774 20210702_202446.jpg
    Location A and B digests match: sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309 20210702_202504.jpg
    Location A and B digests match: sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23 20210702_202530.jpg
    ======================================== RESULTS =============================================
    Files in Location A *not* found in Location B:
    File in A *not* in B: C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    ----------------------------------------
    Location A ...................................................... C:\MyData
    Location B ...................................................... D:\MyData
    Total Location A unique files ................................... 18
    Total Location A skipped files .................................. 0
    Total Location B unique files ................................... 18
    Total Location B skipped files .................................. 0
    Total Location A unique files also in Location B ................ 17
    Total Location A unique files not found in Location B ........... 1
    (venv2-3.9.12) PS C:\>

From the above, we can see the message ``File in A *not* in B: C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg`` indicates D:\\MyData has an *unexpected* difference. 

Taking from the above example, if you now imagine that C:\\MyData was instead E:\\MyData, where E:\\MyData is not a system drive, but perhaps a second *newer* external hard drive containing the same important files, the above might be detecting an issue with photos in the older D:\\MyData hard drive.

You might ask, why not always use digest change detection? Well, as alluded to above, digest change detection must re-generate digests so that they are up to date which can be time-consuming.

Given this, |PROJNAME| uses the lightweight modified date/time and size check by default. If a date/time or size change is detected, such will trigger |PROJNAME| to update that file's digest (because it has obviously changed). Note, though, that this will not automatically update a digest when the date/time and size have not changed (i.e., bitrot). So, at the very least, you may consider re-generating all of your digests every once in a while (i.e., cadence depends on your needs, could be every few months, years, etc.).

If a date/time or size change does not occur when there is nevertheless file corruption (i.e., bitrot, something nefarious), the digest will remain older without re-generating the digests as shown in the prior example.

Given all of this, if any changes are caused by the OS which affect modified date/time or size, a change will be detected even if the digest is old, and that by itself will cause that one file's digest to be re-generated.

Generally, you likely want to re-gen digests every now and then, and perhaps run more regular checks using the default modified date/time and size check.

You can also capture digest information with ``save-db`` and save it offline so it will not be affected if your system crashes or has other such problems. Doing this may help you in assessing file wellness through the use of the saved information.

Combining multiple locations into a single .json DB
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You can combine multiple locations into a single persistent file information .json database file by using the save-db command as follows:

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu save-db --db c:\my-ext-drives-photo-inventory.json D:\MyData\ E:\MyData\
    atbu - v0.01
    Database: c:\my-ext-drives-photo-inventory.json
    Checking for changes to D:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=D:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to D:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=D:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to D:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=D:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to D:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=D:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=D:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=D:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=29de887060a6e62aaee6b339548f564d86630a521e99552aec18b9145a005291
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .............................. D:\MyData
    Location total all files .............. 18
    Location total found unique files ..... 18
    Location total found physical files ... 18
    Location total skipped files .......... 0
    Checking for changes to E:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=E:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to E:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=E:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to E:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=E:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to E:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=E:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to E:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to E:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to E:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=E:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to E:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=E:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to E:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Checking for changes to E:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to E:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to E:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to E:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .............................. E:\MyData
    Location total all files .............. 18
    Location total found unique files ..... 18
    Location total found physical files ... 18
    Location total skipped files .......... 0
    =========================================================================
    The following is a recap of summary information output above:
    Location .............................. D:\MyData
    Location total all files .............. 18
    Location total found unique files ..... 18
    Location total found physical files ... 18
    Location total skipped files .......... 0
    -------------------------------------------------------------------------
    Location .............................. E:\MyData
    Location total all files .............. 18
    Location total found unique files ..... 18
    Location total found physical files ... 18
    Location total skipped files .......... 0
    -------------------------------------------------------------------------
    All locations total unique files ...... 19
    All locations total physical files .... 36
    All locations skipped files ........... 0
    (venv2-3.9.12) PS C:\>

Since c:\\my-ext-drives-photo-inventory.json is kept online, the two drives D:\\ and E:\\ do not need to be available to compare against them. Let's compare C:\\MyData against both D:\\MyData and E:\\MyData without having D:\\ or E:\\ available...

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu diff C:\MyData\ C:\my-ext-drives-photo-inventory.json
    atbu - v0.01
    Location A ............................. C:\MyData
    Location A persist types ............... ['per-dir']
    Location B ............................. C:\my-ext-drives-photo-inventory.json
    Location B persist types ............... ['per-dir']
    Searching location A: C:\MyData
    Checking for changes to C:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=C:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to C:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to C:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to C:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=C:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=C:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=C:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Searching location B: C:\my-ext-drives-photo-inventory.json
    Logging A unique objects ..... 18
    Logging B unique objects ..... 19
    Location A and B digests match: sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6 2021-Budget.xlsx
    Location A and B digests match: sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9 MyImportantNotes.txt
    Location A and B digests match: sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069 NewNotes.txt
    Location A and B digests match: sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f Textually speaking, a novel in pure text.txt
    Location A and B digests match: sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f 20210704_223018.jpg
    Location A and B digests match: sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0 20210826_191432.jpg
    Location A and B digests match: sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200 20211017_162445.jpg
    Location A and B digests match: sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814 20211119_230028.jpg
    Location A and B digests match: sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581 20210704_222527.jpg
    Location A and B digests match: sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e 20210704_222623.jpg
    Location A and B digests match: sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872 20210704_222626.jpg
    Location A and B digests match: sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4 20210703_193235.jpg
    Location A and B digests match: sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e 20210703_193244.jpg
    Location A and B digests match: sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a 20210702_202203.jpg
    Location A and B digests match: sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090 20210702_202437.jpg
    Location A and B digests match: sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774 20210702_202446.jpg
    Location A and B digests match: sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309 20210702_202504.jpg
    Location A and B digests match: sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23 20210702_202530.jpg
    All items in Location A were found in Location B
    Location A ...................................................... C:\MyData
    Location B ...................................................... C:\my-ext-drives-photo-inventory.json
    Total Location A unique files ................................... 18
    Total Location A skipped files .................................. 0
    Total Location B unique files ................................... 19
    Total Location B skipped files .................................. 0
    Total Location A unique files also in Location B ................ 18
    Total Location A unique files not found in Location B ........... 0
    (venv2-3.9.12) PS C:\>

Remember that C:\\my-ext-drives-photo-inventory.json is a .json database of both D:\\MyData and E:\\MyData. E:\\MyData was created from the good C:\\MyData, while D:\\MyData is the simulated bitrot copy, where one file has the same modified date/time, size but its content is different by one bit so it's hash will not match anything in C:\\MyData.

Above you can see that all files in C:\\MyData match the union of D:\\MyData and E:\\MyData within C:\\my-ext-drives-photo-inventory.json. If you look closely, you can see that location B within the union of D:\\MyData and E:\\MyData contains 19 unique files. That extra file is the simulated bitrot file.

If you think of C:\\my-ext-drives-photo-inventory.json as "all of my backup data drives," we know that C:\\MyData is properly represented among the set of all of those drives (albeit certain redundancy may not be present given the difference).

The above was merely to show you that you can combine multiple locations into a single .json DB for later use/diff'ing as desired. Perhaps a more effective use of offline .json DB is to save each drive in its own .json DB. Let's try that now by running these two commands...

``atbu save-db --db c:\my-D-backup-drive-inventory.json D:\MyData\``

``atbu save-db --db c:\my-E-backup-drive-inventory.json E:\MyData\``

**Example...**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu save-db --db c:\my-D-backup-drive-inventory.json D:\MyData\
    atbu - v0.01
    Database: c:\my-D-backup-drive-inventory.json
    Checking for changes to D:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=D:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to D:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=D:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to D:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=D:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to D:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=D:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=D:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to D:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=D:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=29de887060a6e62aaee6b339548f564d86630a521e99552aec18b9145a005291
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to D:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=D:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .............................. D:\MyData
    Location total all files .............. 18
    Location total found unique files ..... 18
    Location total found physical files ... 18
    Location total skipped files .......... 0
    =========================================================================
    The following is a recap of summary information output above:
    Location .............................. D:\MyData
    Location total all files .............. 18
    Location total found unique files ..... 18
    Location total found physical files ... 18
    Location total skipped files .......... 0
    -------------------------------------------------------------------------
    All locations total unique files ...... 18
    All locations total physical files .... 18
    All locations skipped files ........... 0
    (venv2-3.9.12) PS C:\> atbu save-db --db c:\my-E-backup-drive-inventory.json E:\MyData\
    atbu - v0.01
    Database: c:\my-E-backup-drive-inventory.json
    Checking for changes to E:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=E:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to E:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=E:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to E:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=E:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to E:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=E:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to E:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to E:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to E:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=E:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to E:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=E:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to E:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Checking for changes to E:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to E:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to E:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to E:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to E:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=E:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .............................. E:\MyData
    Location total all files .............. 18
    Location total found unique files ..... 18
    Location total found physical files ... 18
    Location total skipped files .......... 0
    =========================================================================
    The following is a recap of summary information output above:
    Location .............................. E:\MyData
    Location total all files .............. 18
    Location total found unique files ..... 18
    Location total found physical files ... 18
    Location total skipped files .......... 0
    -------------------------------------------------------------------------
    All locations total unique files ...... 18
    All locations total physical files .... 18
    All locations skipped files ........... 0
    (venv2-3.9.12) PS C:\>

Given the above commands, we have the following two database files:

* c:\\my-D-backup-drive-inventory.json
* c:\\my-E-backup-drive-inventory.json

We can use each of those to see if our C:\\MyData is backed up redundantly to both drives...

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu diff C:\MyData\ C:\my-D-backup-drive-inventory.json
    atbu - v0.01
    Location A ............................. C:\MyData
    Location A persist types ............... ['per-dir']
    Location B persist types ............... ['per-dir']
    Searching location A: C:\MyData
    Checking for changes to C:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=C:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to C:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to C:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to C:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=C:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=C:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=C:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Searching location B: C:\my-D-backup-drive-inventory.json
    Logging A unique objects ..... 18
    Logging B unique objects ..... 18
    Location A and B digests match: sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6 2021-Budget.xlsx
    Location A and B digests match: sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9 MyImportantNotes.txt
    Location A and B digests match: sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069 NewNotes.txt
    Location A and B digests match: sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f Textually speaking, a novel in pure text.txt
    Location A and B digests match: sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f 20210704_223018.jpg
    Location A and B digests match: sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0 20210826_191432.jpg
    Location A and B digests match: sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200 20211017_162445.jpg
    Location A and B digests match: sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814 20211119_230028.jpg
    Location A and B digests match: sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e 20210704_222623.jpg
    Location A and B digests match: sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872 20210704_222626.jpg
    Location A and B digests match: sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4 20210703_193235.jpg
    Location A and B digests match: sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e 20210703_193244.jpg
    Location A and B digests match: sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a 20210702_202203.jpg
    Location A and B digests match: sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090 20210702_202437.jpg
    Location A and B digests match: sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774 20210702_202446.jpg
    Location A and B digests match: sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309 20210702_202504.jpg
    Location A and B digests match: sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23 20210702_202530.jpg
    ======================================== RESULTS =============================================
    Files in Location A *not* found in Location B:
    File in A *not* in B: C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg
    ----------------------------------------
    Location A ...................................................... C:\MyData
    Location B ...................................................... C:\my-D-backup-drive-inventory.json
    Total Location A unique files ................................... 18
    Total Location A skipped files .................................. 0
    Total Location B unique files ................................... 18
    Total Location B skipped files .................................. 0
    Total Location A unique files also in Location B ................ 17
    Total Location A unique files not found in Location B ........... 1
    (venv2-3.9.12) PS C:\> atbu diff C:\MyData\ C:\my-E-backup-drive-inventory.json
    atbu - v0.01
    Location A ............................. C:\MyData
    Location A persist types ............... ['per-dir']
    Location B ............................. C:\my-E-backup-drive-inventory.json
    Location B persist types ............... ['per-dir']
    Searching location A: C:\MyData
    Checking for changes to C:\MyData\Documents\2021-Budget.xlsx...
    The file info was up to date: path=C:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to C:\MyData\Documents\MyImportantNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Checking for changes to C:\MyData\Documents\NewNotes.txt...
    The file info was up to date: path=C:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Checking for changes to C:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The file info was up to date: path=C:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The file info was up to date: path=C:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The file info was up to date: path=C:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The file info was up to date: path=C:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Searching location B: C:\my-E-backup-drive-inventory.json
    Logging A unique objects ..... 18
    Logging B unique objects ..... 18
    Location A and B digests match: sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6 2021-Budget.xlsx
    Location A and B digests match: sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9 MyImportantNotes.txt
    Location A and B digests match: sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069 NewNotes.txt
    Location A and B digests match: sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f Textually speaking, a novel in pure text.txt
    Location A and B digests match: sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f 20210704_223018.jpg
    Location A and B digests match: sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0 20210826_191432.jpg
    Location A and B digests match: sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200 20211017_162445.jpg
    Location A and B digests match: sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814 20211119_230028.jpg
    Location A and B digests match: sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581 20210704_222527.jpg
    Location A and B digests match: sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e 20210704_222623.jpg
    Location A and B digests match: sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872 20210704_222626.jpg
    Location A and B digests match: sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4 20210703_193235.jpg
    Location A and B digests match: sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e 20210703_193244.jpg
    Location A and B digests match: sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a 20210702_202203.jpg
    Location A and B digests match: sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090 20210702_202437.jpg
    Location A and B digests match: sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774 20210702_202446.jpg
    Location A and B digests match: sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309 20210702_202504.jpg
    Location A and B digests match: sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23 20210702_202530.jpg
    All items in Location A were found in Location B
    Location A ...................................................... C:\MyData
    Location B ...................................................... C:\my-E-backup-drive-inventory.json
    Total Location A unique files ................................... 18
    Total Location A skipped files .................................. 0
    Total Location B unique files ................................... 18
    Total Location B skipped files .................................. 0
    Total Location A unique files also in Location B ................ 18
    Total Location A unique files not found in Location B ........... 0
    (venv2-3.9.12) PS C:\>

As can be seen above, the comparison with the E:\\MyData copy was 100% successful, but the older drive D:\\MyData shows one file from C:\\MyData which is not in D:\\MyData, and it indicates difference with the following file...

``File in A *not* in B: C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg``

Something modified that file, or perhaps the one on C:\\ ... an investigation of those files can take place.

Using the sidecar .atbu file approach
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The following is an example of one of the benefits to using sidecar .atbu files. For this demo, we will use the same C:\\MyData directory from earlier examples...

.. code-block:: console

    C:\MyData
    ├───Documents
    │       2021-Budget.xlsx
    │       MyImportantNotes.txt
    │       NewNotes.txt
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

Let's update-digests as before, but this time we will specify 'pf:' or 'per-file:' before the directory as follows...

* ``atbu update-digests pf: C:\MyData``
* ``atbu update-digests per-file: C:\MyData``

Specifying the 'pf:' or 'per-file:' as an argument before a location causes |PROJNAME| to store or use persistence information per-file (for each file). Or you can think of it as "persistence file" as opposed to "persistence directory .json db."

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests pf: C:\MyData
    atbu - v0.01
    Updating files in C:\MyData...
    Creating info for C:\MyData\Documents\2021-Budget.xlsx...
    Checking for changes to C:\MyData\Documents\2021-Budget.xlsx...
    The .atbu file info was added: path=C:\MyData\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Creating info for C:\MyData\Documents\MyImportantNotes.txt...
    Checking for changes to C:\MyData\Documents\MyImportantNotes.txt...
    The .atbu file info was added: path=C:\MyData\Documents\MyImportantNotes.txt sha256=5c575cfae16e5f9b04101ce50409dfbf3062ac3ebd90829ad764518abcbc57a9
    Creating info for C:\MyData\Documents\NewNotes.txt...
    Checking for changes to C:\MyData\Documents\NewNotes.txt...
    The .atbu file info was added: path=C:\MyData\Documents\NewNotes.txt sha256=6007edb0b8d52d8f7c572af8e418cb86439ce84cc8dbafff3d23a09f731eb069
    Creating info for C:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    Checking for changes to C:\MyData\Documents\Textually speaking, a novel in pure text.txt...
    The .atbu file info was added: path=C:\MyData\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Creating info for C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Creating info for C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    Checking for changes to C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Creating info for C:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211017_162445.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Creating info for C:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    Checking for changes to C:\MyData\Pictures\SocialMedia\20211119_230028.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Creating info for C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Creating info for C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Creating info for C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Creating info for C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Creating info for C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    Checking for changes to C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202203.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202437.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202446.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202504.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Creating info for C:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    Checking for changes to C:\MyData\Pictures\Yellowstone\20210702_202530.jpg...
    The .atbu file info was added: path=C:\MyData\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .................................... C:\MyData
        Location total files ........................ 18
        Location files info created ................. 18
        Location files info updated ................. 0
        Location files no update required ........... 0
        Location files info stale/error, skipped..... 0
    -------------------------------------------------------------------------
    Total all locations processed:
        Total files ................................. 18
        Total Files info created .................... 18
        Total files info updated .................... 0
        Total files no update required .............. 0
        Total files info stale/error, skipped........ 0
    (venv2-3.9.12) PS C:\>

The above command created new .atbu files as shown below...

.. code-block:: console

    C:\MyData
    ├───Documents
    │       2021-Budget.xlsx
    │       2021-Budget.xlsx.atbu
    │       MyImportantNotes.txt
    │       MyImportantNotes.txt.atbu
    │       NewNotes.txt
    │       NewNotes.txt.atbu
    │       Textually speaking, a novel in pure text.txt
    │       Textually speaking, a novel in pure text.txt.atbu
    │
    └───Pictures
        ├───Events
        │   └───2021-HolidayParty
        │           20210704_223018.jpg
        │           20210704_223018.jpg.atbu
        │           20210826_191432.jpg
        │           20210826_191432.jpg.atbu
        │
        ├───SocialMedia
        │       20211017_162445.jpg
        │       20211017_162445.jpg.atbu
        │       20211119_230028.jpg
        │       20211119_230028.jpg.atbu
        │
        ├───Wildlife
        │   ├───Deer
        │   │       20210704_222527.jpg
        │   │       20210704_222527.jpg.atbu
        │   │       20210704_222623.jpg
        │   │       20210704_222623.jpg.atbu
        │   │       20210704_222626.jpg
        │   │       20210704_222626.jpg.atbu
        │   │
        │   └───Geese
        │           20210703_193235.jpg
        │           20210703_193235.jpg.atbu
        │           20210703_193244.jpg
        │           20210703_193244.jpg.atbu
        │
        └───Yellowstone
                20210702_202203.jpg
                20210702_202203.jpg.atbu
                20210702_202437.jpg
                20210702_202437.jpg.atbu
                20210702_202446.jpg
                20210702_202446.jpg.atbu
                20210702_202504.jpg
                20210702_202504.jpg.atbu
                20210702_202530.jpg
                20210702_202530.jpg.atbu

Now, let's say we deside to put both Yellowstone under a directory named .\\Outdoors\\Parks, and Wildlife under .\\Outdoors\\Wildlife...

.. code-block:: console

    C:\MyData
    ├───Documents
    │       2021-Budget.xlsx
    │       2021-Budget.xlsx.atbu
    │       MyImportantNotes.txt
    │       MyImportantNotes.txt.atbu
    │       NewNotes.txt
    │       NewNotes.txt.atbu
    │       Textually speaking, a novel in pure text.txt
    │       Textually speaking, a novel in pure text.txt.atbu
    │
    └───Pictures
        ├───Events
        │   └───2021-HolidayParty
        │           20210704_223018.jpg
        │           20210704_223018.jpg.atbu
        │           20210826_191432.jpg
        │           20210826_191432.jpg.atbu
        │
        ├───Outdoors
        │   ├───Parks
        │   │   └───Yellowstone
        │   │           20210702_202203.jpg
        │   │           20210702_202203.jpg.atbu
        │   │           20210702_202437.jpg
        │   │           20210702_202437.jpg.atbu
        │   │           20210702_202446.jpg
        │   │           20210702_202446.jpg.atbu
        │   │           20210702_202504.jpg
        │   │           20210702_202504.jpg.atbu
        │   │           20210702_202530.jpg
        │   │           20210702_202530.jpg.atbu
        │   │
        │   └───Wildlife
        │       ├───Deer
        │       │       20210704_222527.jpg
        │       │       20210704_222527.jpg.atbu
        │       │       20210704_222623.jpg
        │       │       20210704_222623.jpg.atbu
        │       │       20210704_222626.jpg
        │       │       20210704_222626.jpg.atbu
        │       │
        │       └───Geese
        │               20210703_193235.jpg
        │               20210703_193235.jpg.atbu
        │               20210703_193244.jpg
        │               20210703_193244.jpg.atbu
        │
        └───SocialMedia
                20211017_162445.jpg
                20211017_162445.jpg.atbu
                20211119_230028.jpg
                20211119_230028.jpg.atbu

We use our operating system's file manager UI to move the directories. After doing so, immediately, without even running |PROJNAME|, the |PROJNAME| .atbu persistent file information files are in the right place. There is no need to even run |PROJNAME| to do anything. 

If we had used a single .json db at the top of the hierarchy, located in C:\\MyData as in the earlier examples, we would have to run |PROJNAME| to update the database. Since |PROJNAME| cannot assume a seemingly identical file at a different location is the same file, it must re-generate all of the digests, etc., to update the .json db. With the .atbu sidecar approach, the sidecar itself follows the file it represents so we know the information within it pertains the related file.

Yes, .atbu files may become dated, but that's not the point of this discussion. Any captured digest can become dated even one second after it is captured. That is not the point here as such affects any digest-capturing system unless, somehow, a hard drive or SSD system has instant hardware-based digests that are maintained (as one example). 

What we are saying is that, from the standpoint of maintaining a history of your file's digests, if you use .atbu files, they implicitly follow the file they represent so long as you copy them with the original. And even if such sidecar files become stale, that stale information can be used to detect the change itself. If you re-generate .json db digests, you are not maintaining a history but recreating a new history.

|PROJNAME| could be updated to provide move or copy capabilities that update the .json db but it does not do that today. Today, the recommended way to have history live with the file is to use sidecar .atbu files.

.. _label_detailed_overview:


As a tool to help hard drive consolidation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This example shows how |PROJNAME| diff can be used to help in manual hard drive examination and consolidation procedures. 

Let's say the year is 2015 and you have a hard drive with large/important media located within d:\\MyData-Year-2015-Hard-Drive and run the following command to persist your drive's current information because you want to check it over time as needed.

Let's establish digests now in 2015... 

``atbu update-digests per-file: d:\MyData-Year-2015-Hard-Drive``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests per-file: d:\MyData-Year-2015-Hard-Drive
    atbu - v0.01
    Updating files in d:\MyData-Year-2015-Hard-Drive...
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg sha256=a6996a2b2f0c208d17782bc12a898ef682fb9d8905c5ed8f4309f744fdca69d6
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg sha256=b658c01348ac5aaac8dc634ab9086b55eb698f4eb15d0eb71d670ebe4e721f0d
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Creating info for d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .................................... d:\MyData-Year-2015-Hard-Drive
        Location total files ........................ 16
        Location files info created ................. 16
        Location files info updated ................. 0
        Location files no update required ........... 0
        Location files info stale/error, skipped..... 0
    -------------------------------------------------------------------------
    Total all locations processed:
        Total files ................................. 16
        Total Files info created .................... 16
        Total files info updated .................... 0
        Total files no update required .............. 0
        Total files info stale/error, skipped........ 0
    (venv2-3.9.12) PS C:\>

Now let's say it is a year later, 2016, we were traveling, and while traveling, we ad-hoc copy'ed a few files to that same d:\\MyData-Year-2015-Hard-Drive hard drive...

.. code-block:: console

    D:\MyData-Year-2015-Hard-Drive
    ├───files-while-traveling-in-2016           <--- Added in 2016 while traveling.
    │       AnotherDocument.txt
    │       ImportantLetter.docx
    │       SomeImportantDocument.txt
    │
    └───Pictures                                <--- Pictures added in 2015.
        ├───Events
        │   └───2021-HolidayParty
        │           20210704_223018.jpg
        │           20210704_223018.jpg.atbu
        │           20210826_191432.jpg
        │           20210826_191432.jpg.atbu
        │
        ├───SocialMedia
        │       20211017_162445.jpg
        │       20211017_162445.jpg.atbu
        │       20211119_230028.jpg
        │       20211119_230028.jpg.atbu
        │
        ├───Wildlife
        │   ├───Deer
        │   │       20210704_222527.jpg
        │   │       20210704_222527.jpg.atbu
        │   │       20210704_222623.jpg
        │   │       20210704_222623.jpg.atbu
        │   │       20210704_222626.jpg
        │   │       20210704_222626.jpg.atbu
        │   │
        │   ├───Geese
        │   │       20210703_193235.jpg
        │   │       20210703_193235.jpg.atbu
        │   │       20210703_193244.jpg
        │   │       20210703_193244.jpg.atbu
        │   │
        │   └───Heron
        │           20220530_140532.jpg
        │           20220530_140532.jpg.atbu
        │           20220530_140645.jpg
        │           20220530_140645.jpg.atbu
        │
        └───Yellowstone
                20210702_202203.jpg
                20210702_202203.jpg.atbu
                20210702_202437.jpg
                20210702_202437.jpg.atbu
                20210702_202446.jpg
                20210702_202446.jpg.atbu
                20210702_202504.jpg
                20210702_202504.jpg.atbu
                20210702_202530.jpg
                20210702_202530.jpg.atbu

Now let's say it's about 7 years later, in 2022, and you have a new hard drive E:\\MyData-Year-2022-Hard-Drive. You are going through older hard drives because you move critical backups to newer media every number of years, but before destroying older media, you want to ensure all files are accounted for one way or another.

The 2015 hard drive D:\\MyData-Year-2015-Hard-Drive data has not had its digests checked in about 7 years, so the first thing we may want to do is update all digests...

``atbu update-digests --cdt digest per-file: d:\MyData-Year-2015-Hard-Drive``

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests --cdt digest per-file: d:\MyData-Year-2015-Hard-Drive
    atbu - v0.01
    -------------------------------------------------------------------------
    Updating files in d:\MyData-Year-2015-Hard-Drive...
    Creating info for d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\AnotherDocument.txt...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\AnotherDocument.txt...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\AnotherDocument.txt sha256=c6efa5c08cad7357eb8bb11484616d53ffaf3f4f388f1d3d484493d6e2d42739
    Creating info for d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\ImportantLetter.docx...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\ImportantLetter.docx...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\ImportantLetter.docx sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    Creating info for d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\SomeImportantDocument.txt...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\SomeImportantDocument.txt...
    The .atbu file info was added: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\SomeImportantDocument.txt sha256=06d90109c8cce34ec0c776950465421e176f08b831a938b3c6e76cb7bee8790b
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg...
    Change detected: d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg:
        cur size=722770
        old size=722770
        cur time=2021-07-04T22:25:32.000000
        old time=2021-07-04T22:25:32.000000
        cur digest=845fcd2ba9d1e2ccaa9e46dfa4781bf998ff32fee268fe80b786313e6b6e096e
        old digest=b9e3a8e4fb26c41b7c82c00bfef6e7de64d07b0f1834069acf22a0742e9e8d4b
    WARNING: Potential bitrot or other sneaky corruption: d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg
    Updating file info for d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The .atbu file info was updated: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=845fcd2ba9d1e2ccaa9e46dfa4781bf998ff32fee268fe80b786313e6b6e096e
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg sha256=a6996a2b2f0c208d17782bc12a898ef682fb9d8905c5ed8f4309f744fdca69d6
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg sha256=b658c01348ac5aaac8dc634ab9086b55eb698f4eb15d0eb71d670ebe4e721f0d
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Location .................................... d:\MyData-Year-2015-Hard-Drive
        Location total files ........................ 19
        Location files info created ................. 3
        Location files info updated ................. 1
        Location files no update required ........... 15
        Location files info stale/error, skipped..... 0
    Total potential sneaky corruption............ 1 (see details above)
    =================================================================
    =================================================================
    Potential sneaky corruption all locations processed:
        path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg
        old_size=722770
        cur_size=722770
        old_time=2021-07-04T22:25:32.000000
        cur_time=2021-07-04T22:25:32.000000
        old_digest=b9e3a8e4fb26c41b7c82c00bfef6e7de64d07b0f1834069acf22a0742e9e8d4b
        cur_digest=845fcd2ba9d1e2ccaa9e46dfa4781bf998ff32fee268fe80b786313e6b6e096e
    -----------------------------------------------------------------
        Total potential sneaky corruption Location A: 1
    =================================================================
    Total all locations processed:
        Total files ................................. 19
        Total Files info created .................... 3
        Total files info updated .................... 1
        Total files no update required .............. 15
        Total files info stale/error, skipped........ 0
        Total potential sneaky corruption............ 1 (see details above)
    (venv2-3.9.12) PS C:\>

A few important things to note when running update-digests above...

* **Using the same persistence type:** First, let's note that, since we used "per-file:" in 2015, it is important to use "per-file:" again as shown above because, without doing that, |PROJNAME| would create a per-dir database by default, ignoring the information files already present. We want to take advantage of that history that has been living side-by-side with our important data files, so we use "per-file:" to instruct |PROJNAME| to check/update persisted file information in those locations. 
* **Forcing digest check after many years:** By specifying -cdt digest, we instruct |PROJNAME| to re-generate all digests and compare them with the existing 2015 history. This is being done in this example because 7 years is a long time, and that old 2015 hard drive has been used for many purposes, inserted in various machines, and sitting in various storage locations, some perhaps not so cool. We re-gen digests after a long period of time in this example because it's a way of comparing current content with the 2015 content.
* **New files discovered:** |PROJNAME| has observed that files within d:\\MyData-Year-2015-Hard-Drive\\files-while-traveling-in-2016 never had their persistent information saved so their information was saved as part of the above update-digests command (see lines with "Creating info").
* **Potential corruption:** |PROJNAME| detected potential bitrot or other sneaky corruption for the file 20210704_222527.jpg. Sneaky corruption is when the digest for a file differs from the last time it was captured despite the file date/time and size not having changed. With the file 20210704_222527.jpg in the example, it had one digest in 2015, but has a different digest now in 2022, but the file's date/time and size have not changed. It is typically bad practice and not typical for programs to update files and force an older date so |PROJNAME| diff views such as a potentially bad thing and alerts you so you can investigate.
    * **VERY IMPORTANT:** You only get one chance to see bitrot / sneaky file corruption because |PROJNAME| will update the file's persistent history to reflect the new digest, which means it will no longer detect the same issue on subsequent digest updates. Pay close attention, therefore, to the output of the command. You might consider using the |PROJNAME| --logfile command to capture the details in a file. You can keep the log file somewhere as a form of history you can review as needed.

So already we see one issue with that older hard drive. Let's say you prefer a manual process, you do not wnat tools deleting files, but you want to organize them automatically so you can see what's most important in consolidaton. One feature of |PROJNAME| diff is that it can move or delete files files that are both in location A and B. Let's try that with move using the old and new hard drives from the above example.

.. code-block:: console

    atbu diff per-file: d:\MyData-Year-2015-Hard-Drive e:\MyData-Year-2022-Hard-Drive --action move-duplicates --md d:\MyData-Year-2015-Hard-Drive-Duplicates

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu diff per-file: d:\MyData-Year-2015-Hard-Drive e:\MyData-Year-2022-Hard-Drive --action move-duplicates --md d:\MyData-Year-2015-Hard-Drive-Duplicates
    atbu - v0.01
    Location A ............................. d:\MyData-Year-2015-Hard-Drive
    Location A persist types ............... ['per-file']
    Location B ............................. e:\MyData-Year-2022-Hard-Drive
    Location B persist types ............... ['per-file']
    -----------------------------------------------------------------
    Searching location A: d:\MyData-Year-2015-Hard-Drive
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\AnotherDocument.txt...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\AnotherDocument.txt sha256=c6efa5c08cad7357eb8bb11484616d53ffaf3f4f388f1d3d484493d6e2d42739
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\ImportantLetter.docx...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\ImportantLetter.docx sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\SomeImportantDocument.txt...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\SomeImportantDocument.txt sha256=06d90109c8cce34ec0c776950465421e176f08b831a938b3c6e76cb7bee8790b
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=845fcd2ba9d1e2ccaa9e46dfa4781bf998ff32fee268fe80b786313e6b6e096e
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg sha256=a6996a2b2f0c208d17782bc12a898ef682fb9d8905c5ed8f4309f744fdca69d6
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg sha256=b658c01348ac5aaac8dc634ab9086b55eb698f4eb15d0eb71d670ebe4e721f0d
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    -----------------------------------------------------------------
    Searching location B: e:\MyData-Year-2022-Hard-Drive
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Documents\2021-Budget.xlsx...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Documents\2021-Budget.xlsx sha256=9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Documents\MyImportantNotes.txt...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Documents\MyImportantNotes.txt sha256=3efb41e3ada35977bd17d9360318197193d8e20f557c89f5f13f8aa89743e5ea
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Documents\Textually speaking, a novel in pure text.txt...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Documents\Textually speaking, a novel in pure text.txt sha256=c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=1da008e928b843c14aff8df533a3da1c35f762f01e91ad50d99fd83ab7fdd581
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg sha256=a6996a2b2f0c208d17782bc12a898ef682fb9d8905c5ed8f4309f744fdca69d6
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg sha256=b658c01348ac5aaac8dc634ab9086b55eb698f4eb15d0eb71d670ebe4e721f0d
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Checking for changes to e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg...
    The .atbu file info was up to date: path=e:\MyData-Year-2022-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Logging A unique objects ..... 19
    Logging B unique objects ..... 19
    Location A and B digests match: sha256=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f 20210704_223018.jpg
    Location A and B digests match: sha256=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0 20210826_191432.jpg
    Location A and B digests match: sha256=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200 20211017_162445.jpg
    Location A and B digests match: sha256=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814 20211119_230028.jpg
    Location A and B digests match: sha256=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e 20210704_222623.jpg
    Location A and B digests match: sha256=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872 20210704_222626.jpg
    Location A and B digests match: sha256=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4 20210703_193235.jpg
    Location A and B digests match: sha256=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e 20210703_193244.jpg
    Location A and B digests match: sha256=a6996a2b2f0c208d17782bc12a898ef682fb9d8905c5ed8f4309f744fdca69d6 20220530_140532.jpg
    Location A and B digests match: sha256=b658c01348ac5aaac8dc634ab9086b55eb698f4eb15d0eb71d670ebe4e721f0d 20220530_140645.jpg
    Location A and B digests match: sha256=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a 20210702_202203.jpg
    Location A and B digests match: sha256=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090 20210702_202437.jpg
    Location A and B digests match: sha256=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774 20210702_202446.jpg
    Location A and B digests match: sha256=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309 20210702_202504.jpg
    Location A and B digests match: sha256=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23 20210702_202530.jpg
    ======================================== RESULTS =============================================
    Files in Location A *not* found in Location B:
    File in A *not* in B: d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\AnotherDocument.txt
    ----------------------------------------
    File in A *not* in B: d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\ImportantLetter.docx
    ----------------------------------------
    File in A *not* in B: d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\SomeImportantDocument.txt
    ----------------------------------------
    File in A *not* in B: d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg
    ----------------------------------------
    ======================================================================
                                    MOVING
    ======================================================================
    Moving duplicates in Location A: d:\MyData-Year-2015-Hard-Drive
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Events\2021-HolidayParty\20210704_223018.jpg digest=7fee4ed7cdd1f47f50a5ee34c5e4d664d084f6b214c035b66d12d778b100547f
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210704_223018.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Events\2021-HolidayParty\20210704_223018.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Events\2021-HolidayParty\20210826_191432.jpg digest=8f4d4f96cc03e1d2325131ebc0f2d185f5672ca50d9ed6cb01c0b30d7a8995c0
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty\20210826_191432.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Events\2021-HolidayParty\20210826_191432.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\SocialMedia\20211017_162445.jpg digest=6ee2386f90dd6d2ed672d72e7fb4fe326a5fc7e24b8d4b162fc3f108f8d7e200
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211017_162445.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\SocialMedia\20211017_162445.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\SocialMedia\20211119_230028.jpg digest=6d7eb15812bad686523cc15129949c079099c0914a61a718c02b800c68ff2814
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia\20211119_230028.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\SocialMedia\20211119_230028.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Deer\20210704_222623.jpg digest=034b5cf3d336f257d610256fe1eef4d3cb030f3e3abc535dc5da881b112d694e
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222623.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Deer\20210704_222623.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Deer\20210704_222626.jpg digest=ae1c456c3e22e9f9afaa0a0950fbf943883a54b0c3182b8c4c7d04a0ea788872
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222626.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Deer\20210704_222626.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Geese\20210703_193235.jpg digest=a4b968f8ba7a1f9dc011d7e3ed1211fc8a60be7553af5960e7ca08b9536185d4
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193235.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Geese\20210703_193235.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Geese\20210703_193244.jpg digest=b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese\20210703_193244.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Geese\20210703_193244.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Heron\20220530_140532.jpg digest=a6996a2b2f0c208d17782bc12a898ef682fb9d8905c5ed8f4309f744fdca69d6
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140532.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Heron\20220530_140532.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Heron\20220530_140645.jpg digest=b658c01348ac5aaac8dc634ab9086b55eb698f4eb15d0eb71d670ebe4e721f0d
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron\20220530_140645.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Wildlife\Heron\20220530_140645.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202203.jpg digest=41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202203.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202203.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202437.jpg digest=16600056b63e727776fb6c3e092faa5523410044168754c3076eb1223f9dd090
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202437.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202437.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202446.jpg digest=0f7e82f0e2e545f0fb42bbec1d20b2833cb2e5c29243377e86b0cb76666f9774
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202446.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202446.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202504.jpg digest=c674781eedeb046aea388e19a1af08db269137a01d5ce8efabfdb9c61febd309
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202504.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202504.jpg.atbu
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202530.jpg digest=5540e0a2316fb020de634e8ec7962214cd6540b48e41b70985b64b91e838ca23
    Moving d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone\20210702_202530.jpg.atbu ---to--> d:\MyData-Year-2015-Hard-Drive-Duplicates\Pictures\Yellowstone\20210702_202530.jpg.atbu
    Removing empty directories...
    Successfully removed d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Geese
    Successfully removed d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer
    Successfully removed d:\MyData-Year-2015-Hard-Drive\Pictures\SocialMedia
    Successfully removed d:\MyData-Year-2015-Hard-Drive\Pictures\Yellowstone
    Successfully removed d:\MyData-Year-2015-Hard-Drive\Pictures\Events\2021-HolidayParty
    Successfully removed d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Heron
    Starting post-command location A update...
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\AnotherDocument.txt...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\AnotherDocument.txt sha256=c6efa5c08cad7357eb8bb11484616d53ffaf3f4f388f1d3d484493d6e2d42739
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\ImportantLetter.docx...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\ImportantLetter.docx sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\SomeImportantDocument.txt...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\files-while-traveling-in-2016\SomeImportantDocument.txt sha256=06d90109c8cce34ec0c776950465421e176f08b831a938b3c6e76cb7bee8790b
    Checking for changes to d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg...
    The .atbu file info was up to date: path=d:\MyData-Year-2015-Hard-Drive\Pictures\Wildlife\Deer\20210704_222527.jpg sha256=845fcd2ba9d1e2ccaa9e46dfa4781bf998ff32fee268fe80b786313e6b6e096e
    Location A ...................................................... d:\MyData-Year-2015-Hard-Drive
    Location B ...................................................... e:\MyData-Year-2022-Hard-Drive
    Total Location A unique files ................................... 19
    Total Location A skipped files .................................. 0
    Total Location B unique files ................................... 19
    Total Location B skipped files .................................. 0
    Total Location A unique files also in Location B ................ 15
    Total Location A unique files not found in Location B ........... 4
    Summary 'move-duplicates'...
    Total Location A unique files moved ............................. 15
    Total Location A physical files moved ........................... 15
    Total Location A config files moved ............................. 15
    Total Location A config files not moved ......................... 0
    Total Location A affected directories ........................... 6
    Total Location A affected directories emptied/removed ........... 5
    (venv2-3.9.12) PS C:\>

The above results in the following two structures on the old 2015 hard drive:

**The original D:\\MyData-Year-2015-Hard-Drive directory:**

.. code-block:: console

    D:\MyData-Year-2015-Hard-Drive
    ├───files-while-traveling-in-2016
    │       AnotherDocument.txt
    │       AnotherDocument.txt.atbu
    │       ImportantLetter.docx
    │       ImportantLetter.docx.atbu
    │       SomeImportantDocument.txt
    │       SomeImportantDocument.txt.atbu
    │
    └───Pictures
        └───Wildlife
            └───Deer
                    20210704_222527.jpg
                    20210704_222527.jpg.atbu

**The newly created D:\\MyData-Year-2015-Hard-Drive-Duplicates directory:**

.. code-block:: console

    D:\MyData-Year-2015-Hard-Drive-Duplicates
    └───Pictures
        ├───Events
        │   └───2021-HolidayParty
        │           20210704_223018.jpg
        │           20210704_223018.jpg.atbu
        │           20210826_191432.jpg
        │           20210826_191432.jpg.atbu
        │
        ├───SocialMedia
        │       20211017_162445.jpg
        │       20211017_162445.jpg.atbu
        │       20211119_230028.jpg
        │       20211119_230028.jpg.atbu
        │
        ├───Wildlife
        │   ├───Deer
        │   │       20210704_222623.jpg
        │   │       20210704_222623.jpg.atbu
        │   │       20210704_222626.jpg
        │   │       20210704_222626.jpg.atbu
        │   │
        │   ├───Geese
        │   │       20210703_193235.jpg
        │   │       20210703_193235.jpg.atbu
        │   │       20210703_193244.jpg
        │   │       20210703_193244.jpg.atbu
        │   │
        │   └───Heron
        │           20220530_140532.jpg
        │           20220530_140532.jpg.atbu
        │           20220530_140645.jpg
        │           20220530_140645.jpg.atbu
        │
        └───Yellowstone
                20210702_202203.jpg
                20210702_202203.jpg.atbu
                20210702_202437.jpg
                20210702_202437.jpg.atbu
                20210702_202446.jpg
                20210702_202446.jpg.atbu
                20210702_202504.jpg
                20210702_202504.jpg.atbu
                20210702_202530.jpg
                20210702_202530.jpg.atbu

There are two directories shown above...

* D:\\MyData-Year-2015-Hard-Drive: The original old hard drive directory.
* D:\\MyData-Year-2015-Hard-Drive-Duplicates: The "duplicates" directory created from the -md argument (see the |PROJNAME| command above).

Since the -md argument moved the files from one location to another on the *same hard drive*, the cost of the move was relatively little in terms of time. This is because moving files from one location to another on the same drive is fairly quick and non-intensive since the file's content is usually not touched to perform the move, unlike copying between drives. This is, perhaps, more ideal for an older drive since you can rearrange the file at lower cost of disk usage. Anyway, this is an approach I use and, after all, this is a personal ad-hoc tool being shared so YMMV.

So moving duplicates to the duplicate directory on the same drive did not affect thes files being moved beyond the OS updating disk structures to show the files now being in the new location.

Why do this, you ask? Great question!

Well, since your focus is ensuring D:\\MyData-Year-2015-Hard-Drive is backed up elsewhere, you are trying to see what in the older drive is not already on the newer drive. Moving duplicates clears out D:\\MyData-Year-2015-Hard-Drive except for files not known to be elsewhere.

At this point, we can see the following files on D:\\MyData-Year-2015-Hard-Drive are not backed up on the newer drive.

* D:\\MyData-Year-2015-Hard-Drive\\files-while-traveling-in-2016\\...
    * These are file's from that 2016 travel... we forgot about these files, we will copy them to the new 2022 drive.
* D:\\MyData-Year-2015-Hard-Drive\\Pictures\\Wildlife\\Deer\\20210704_222527.jpg
    * This is that file which had apparent sneaky corruption. We may decide to rename this to 20210704_222527-potentially-corrupt.jpg or something like that, and copy it side-by-side with the known good copy. Or, if it's a known edit to the file, such metadata, we can other choices.

Transitive property among known duplicate drives
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Related to the earlier example scenarios, you can use |PROJNAME| diff to establish that hard drives are effective duplicates of other drives from a digest perspective. For example, let's say you have the following...

* DriveA: 2015 hard drive.
* DriveB: 2017 hard drive.
* DriveC: 2019 hard drive.
* DriveD: 2022 hard drive.

If you know that DriveC matches DriveD and DriveB matches DriveC, then you know DriveB matches DriveD, and you can therefore use DriveB as a "working" drive to diff with other drives (or a .json db of DriveB).

* DriveB -> DriveC -> DriveD

Using DriveB in diffs is pretty much like diff'ing with the newest/best DriveD, but you can use DriveB and keep DriveC/DriveD minimally used to preserve functionality.

Referring to the immediate proceeding section/example, DriveB could be the 2022 drive we were using, redundant with some other 2022 "DrivesC" and "DrivesD".

Additional Details
^^^^^^^^^^^^^^^^^^
The persistent file information portion of |PROJNAME| provides the ability to capture the state of your cherished files at a particular point in time, and to compare or diff that information with new information captured at a later time.

Persistent file information provides the following command line operations:

* **update-digests:** Scans and captures information for all files within one or more specified directories. The following information is captured:
    * SHA256 digest of the file's contents.
    * The file's last modified date/time.
    * The file's size.
    * The file's path.
    * A history of the above information: Each time you update-digests, if a file's information is changed, new information is captured, saving the older information in that file's lifetime history.
* **save-db:** Given one or more directories where ``update-digests`` has been run, and where persistent file information is therefore maintained, capture all such information into a single .json "database" file.
    * A persistent file informaiton .json database file can serve as a dataset in a diff command, which means you can specify a path to such a .json file instead of a directory location when performing a diff (see diff below).
    * For a directory not using sidecar files, but instead using a single .json db, you can use ``save-db`` to include that .json db in the db you are saving. Again, this is somewhat like treating as though it were a directory on the ``save-db`` command line.
    * Saving a persistent file information .json database file can be a convenient way of saving an external hard drive's persistent file information for online or offline usage, allowing you to reference it as needed without having the hard drive itself.
        * This could, for example, help your own manual consolidation or data inventory efforts. Every few years, some people go through all of their data, ensure backups are in good form, etc. Keeping track of what different drives contain can certainly help consolidation, or find undesired or desired/missing redundancy. 
* **diff:** Given two datasets of persistent file information, each referred to as location A and B, perform a diff of A and B, producing a report of files in A that are not in B.
    * The diff command requires two "locations" referred to as Location A and Location B.
    * Each location can either be a directory location, or a persistent file information database .json file captured using save-db mentioned above. 
    * Since a ``save-db`` .json database can contain information from one or more directories where ``update-digests`` has been run, a diff using a .json database containing information for more than one directory effectively allows you to diff multiple locations with some other .json database or a directory.
    * In addition to a report, you can instruct diff to perform an action based on the outcome of the diff. Currently, two actions exist based on what my own personal consolidation needs were: a) remove duplicates, or b) move duplicates. I used this capability with manual consolidation efforts. Once I knew that newer media had copies of files on older media, I could safely retire the older media (or repurpose that older media for less important backup needs). By moving or deleting duplicate files, I would have less remaining files in the drive being assessed. This was simply the way I needed to use the tool given my tendency to give manual attention to consolidation efforts.

My personal experience, some thoughts on sidecar files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TL;DR: For important irreplacable media, sidecar files generally rock (meaning they are "the thing", "the way to go", "totally awesome").

Some people think, for example, that a program which modifyies an original photo file to embed desired metadata is a great thing: convenient, single file, etc. I am the opposite: I *cannot stand* the notion of this for my own library of irreplacable media. 

**The reason?** Originals are originals and they should be thought of and left as originals. In the days of film, I did not draw or scratch on negatives or original irreplacable photos! There's no reason to "draw or scratch" onto original jpg, raw, mp4/mpeg, other such files. Doing so always risks harming the original. Make a copy and modify the copy!

Think of it this way: You cannot fully control the photo/video programs you use if they are proprietary. There is nothing stopping your fav photo editing or DAM management app from being updated with some bug that causes harm to your files. I do not want 10 different companies and their programs modifying my originals... please... Programs... stay away from my originals, please, companies who make cool programs, offer sidecar functionality for "editing" needs. Let me create a copy with modifications as needed.

Some programs support sidecar files, not all. If you have not figured out yet, I love sidecar files, and I cannot stand programs that modify my originals. You know what? There was a really well-known raw file editor that used to *never* touch original raw files, but nowadays it *actually updates the raw file* with my metadata changes!! That is just *crazy crazy crazy* in my, perhaps not so humble, opinion.

This is why |PROJNAME| employs sidecar files for persistence information. I personally started with sidecar files because I knew it was the way to go for my own needs. I added the .json db capability afterwards. I have not used the single .json db capability much yet. I have used, to great value, the sidecar .atbu approach. Basically, I populate older media hard drives with digest info using .atbu persistence info... that info is then "locked in" to those hard drives. I never edit files on those drives, so those .atbu files should represent good digests. If I copy the media from that drive, the .atbu files follow the media. If I recategorize the structure, moving files around, the .atbu sidear files simply go with the originals, no need to scan or update digests. To me, this is the "pro" way to go. 

Even though |PROJNAME| does not embed files, sidecar files have benefits in that they do not modify originals, but contain good useful inventory-like information that lives side-by-side with the original media file.

Side note, it is always a risk to write data to very hold hard drives... not necessarily a bad risk but just a risk of sorts... hard drives age, can go bad... but writing .atbu digest files to older drives was a choice I was willing to make because I have redundancy so the point was to ensure everything got moved to newer media... anyway, I did not have issues so all was well.

Going fordware, my ingestion workflow will, as a matter of course, involve generating .atbu digest sidecar files, at least for large irreplacable photos/videos. When those currently new drives age and become old, they will already have .atbu digest files so I'm good to go for validating and comparing contents as time moves forward.
