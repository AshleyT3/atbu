Securing the Backup with YubiKey
=========================================================

Overview
--------

|PROJNAME| allows you to secure your backup encryption key using a combination of a hardware YubiKey via USB token and your password. Once |PROJNAME| is setup to work with YubiKey, you cannot backup or restore files without both having your YubiKey and knowing your password.

|PROJNAME| uses the YubiKey's HMAC-SHA1 challenge/response capabilities to achieve backup encryption protection. You do not need to understand HMAC-SHA1 challenge/response to make use of this feature.

Generally, think of HMAC-SHA1 challenge/response as the ability for a YubiKey to act as a blackbox which takes your password as input, and responds with a special code only it knows how to generate (assuming you have kept your YubiKey HMAC-SHA1 secret secure... more on this below).

The basic steps discussed in the following sections are:

    * You obtain a YubiKey. |PROJNAME| supports a YubiKey via USB using Slot 2 configured for HMAC-SHA1 Challenge/Response. YubiKey has been tested with YubiKey 4 but should work fine with YubiKey 5.
    * After obtaining a YubiKey, you configure it's Slot 2 configuration with a special secret. You can then start using that YubiKey with |PROJNAME|.
    * You create a new, or update an existing local or cloud backup to use a password, but you specify the ``--yk`` command line option to instruct |PROJNAME| to use YubiKey.
        * If you already have a password protecting your encryption key, you will need to first remove the password from protecting the backup, then re-add a password while the ``--yk`` command line option is active, and while you have a YubiKey inserted into a USB port.
    * You can use all the same cloud/local backup/restore commands outlined in :ref:`cloud-and-local-backup` but, when using password protection, ensure the ``--yk`` command line option is active so that all password operations utilize the YubiKey (examples given later in this section).
    * |PROJNAME| will use the first YubiKey it finds. It is recommended you only have one YubiKey connected to the system when you use ``--yk``.

Setup Steps
-----------

Preface
^^^^^^^

The YubiKey HMAC-SHA1 setup steps outlined below are obviously not official YubiKey setup documentation. If you find all/part of these steps to be dated/unhelpful, refer to the YubiKey documentation for setting HMAC-SHA1 on Slot 2.

At some point in the future, |PROJNAME| may be updated to walk you through configuring Slot 2 HMAC-SHA1 but at this time, you need to use the YubiKey Personalization Tool (UI tool) to configure the YubiKey.

These steps are based off of using YubiKey 4 with the latest Personalization Tool.

The steps for using the Personalization Tool to setup a YubiKey were tested on Windows.

The steps to setup |PROJNAME| so it uses YubiKey Manager to integrate HMAC-SHA1 were tested on both Windows/Linux but the Linux steps were a little more involved. This was a test on on one particular Ubuntu system and may vary depending on distribution and overall setup. The extra steps involved using root to allow the system to build certain components indirectly required by the primary package being installed. YMMV but FYI (more on this in the Linux section below).

YubiKey is a versatile device with many features. |PROJNAME| chose to use the HMAC-SHA1 feature of YubiKey because it allows the user to what seems like the most optimum flexibility, including control what secret is programed on the YubiKey, and the ability to back up that secret, or provision additional YubiKeys in advance so backups are available as needed.

YubiKey Setup
^^^^^^^^^^^^^

1. Download the YubiKey Personalization Tool:
   https://www.yubico.com/support/download/yubikey-personalization-tools/

2. Start the Personalization Tool:

   .. image:: /_static/yubi/yubikey-perstool-01-no-key.jpg

3. Insert the YubiKey and choose the Challenge/Response tab at the top of the Personalization Tool:

   .. image:: /_static/yubi/yubikey-perstool-03-CHAL-RESP-Page.jpg

4. Click the HMAC-SHA1 button which takes you to the HMAC-SHA1 programming/setup page:

   .. image:: /_static/yubi/yubikey-perstool-04-HMAC-SHA1-AfterConfig.jpg

5. From the HMAC-SHA1 programming/setup page:
    a. Click to select "Configuration Slot 2."
    b. Click "Require user input." 
    c. Click "Variable input."
    d. If you wish to have the tool generate a secret code for you, click "Generate." If you wish to use your own chosen secret code, enter in 20 bytes as hex digits. Regardless of which method you use, make sure you backup the 20 byte code (the 20 hex digits entered or generated). See additional discussion below regarding backing up your codes and encryption key.
    e. Finally, click "Write Configuration" which will write your secret code and settings to the Slot 2 configuration on the YubiKey. When doing this, the Personalization Tool will prompt you to save a log file containing the secret code. If you use this for a backup, do not make assumptions, check to ensure sure the code is there in the log file. As well, after you backup your HMAC-SHA1 secret, ensure you securely delete the log file and any other remnants of the secret. If you leave the log on your PC, anyone with access can easily get the code.

   .. image:: /_static/yubi/yubikey-perstool-04-HMAC-SHA1-AfterConfig-Annotated.jpg

The following is an example log file created by the Personalization Tool. It contains the example secret created by clicking Generate:

   .. image:: /_static/yubi/yubikey-perstool-05-LogFileNotepad.jpg

Secret/Key Backup
-----------------

Before proceeding, a quick comment about backing up your encryption key and YubiKey secret. This section will not repeat the discussion on exporting/importing your encryption key (see :ref:`exporting-backup-config` for details).

First, for those not familiar with encryption keys and HMAC-SHA1 secrets, a quick recap from a high-level:

   * Encryption key: This is the secret key used to encrypt and decrypt your backed up files. This key may or may not be password-protected. It is up to you to choose to use a password or not. If you use a password, you must enter the password before any backup or restore operation. By default, the password feature works without any extra hardware (no YubiKey required).
   * HMAC-SHA1 secret: This is the "secret code" mentioned above. This is a secret that your YubiKey holds within itself. You program the YubiKey to have this code. You can choose the code, or you can have something create a code for you as we saw with the Generate button with the Personalization Tool mentioned in the prior section.

When you do not have a YubiKey, your password is simply the characters that you type in on the keyboard. Those are used to unlock/lock your encryption key. If you choose not to have a password-protected backup, you do not have to enter a password, but this then means your backup's encryption key is stored directly in the keystore. Accessing the encryption key is as simple as having access to your machine and your keystore (usually by having access to your machine and your login on that machine).

When you add a YubiKey, you specify ``--yk`` on the |PROJNAME| command line. That instructs |PROJNAME| to use a YubiKey for password protection. You still need to choose the option to enable password projection. The ``--yk`` option alone will not do it. You must choose the options to enable password protection when setting up a backup (or you must change the backup to use password projection).

When you use ``--yk``, you still enter a textual password, but after you enter your password, and press the YubiKey plate to allow access for an HMAC-SHA1 Challenge/Response, the YubiKey will take your password and create a new special code by using two things:

    a) The special HMAC-SHA1 code you program into the YubiKey as discussed earlier. This is what you do once when setting up the YubiKey, or you might do it, for example, when creating additional YubiKeys in case your primary YubiKey is lost/stolen, etc.
    b) Your textual password entered each time you perform a backup/restore.

After a Challenge (your typed password) is sent to the YubiKey, the YubiKey responds back with that new special code derived from your typped password and the secret code you program into the YubiKey.

That is why it is called Challenge/Response. The YubiKey is given your password as a Challenge, where it performs some processing using the Challenge and the secret it has, providing the Response back to |PROJNAME|.

The Response from the YubiKey is the ultimate password that protects the encryption key. 

The levels of protection are generally as follows:

   * Your files are protected by the encryption private key.
   * Without YubiKey: The encryption private key is protected by your textual password alone.
   * With YubiKey: The encryption private key is protected by both your textual password and the YubiKey's secret code.

You can view the various protection approaches as follows:

   * With the Yubikey, anyone with both your password and a YubiKey programmed with your secret code (used to setup HMAC-SHA1), can access your backup encryption private key.
   * Without the YubiKey, anyone with your backup password can access your backup encryption private key.
   * Without any password protecting your backup encryption private key, anyone who can access the keystore on your PC, or any backups you have of the exported backup configuration, can access your encryption private key.

Setup |PROJNAME|
-----------------

By default, when |PROJNAME| is installed via the `pip` command, the packages required for using YubiKey are *not* installed by default. You must install them manually separately. This may change in the future, but the reason for doing this is to limit any issues by implicitly including the YubiKey packages.

The reason for the packages not being installed by default is because |PROJNAME| currently uses YubiKey Manager (yubikey-manager) package to access the YubiKey Challenge/Response API and when installing that package on Linux, it seems some other packages may require building some components. If you are not logged in as root, you may see issues with those builds.

There is another API that uses libusb but libusb is not readily available on Windows and it is not included with the YubiKey package. In this case, the YubiKey Manager package is easier to use beyond initial installation on Linux (observed once on Ubuntu).

|PROJNAME| may be updated to simplify the Linux use case but for now the yubikey-manager package is required.

Setup |PROJNAME| on Windows
+++++++++++++++++++++++++++

On Windows, YubiKey Manager installed with the following simple command:

1. `pip install yubikey-manager`

That's it. After installing yubikey-manager, |PROJNAME| works with YubiKey.

Setup |PROJNAME| on Linux (Ubuntu tested)
+++++++++++++++++++++++++++++++++++++++++

You should probably start by trying to install yubikey-manager directly as follows:

``pip install yubikey-manager``

If you see errors, they obviously need to be resolved.

When errors were experienced in the one test, they were resolved as discussed in the following. YMMV.

On Linux/Ubuntu, the following steps worked on one system tested where a Python venv (Python virtual environment) was used.

In that one case, Python 3.9 was being used so below you will see Python 3.9-related packages being installed to resolve the errors observed when running ``pip install yubikey-manager``.

You will likely need to change what packages you use depending on your version and errors you observe trying to install the first time.

The command ``pip install yubikey-manager`` was attempted first, but errors were observed. It seemed root was needed, but for a virtual environment it was necessary to use `su` then activate the Python venv while `su` / root was active. If you are not using a Python venv, you may have an easier situation.

As mentioned, try ``pip install yubikey-manager`` first to see how it goes, resolve errors from there. The following steps are for reference FWIW only...

The ``pip install yubikey-manager`` command was run and errors were observed. To resolve the errors, ultimately the following was performed...

1. `su <user>`
2. If desired, activate a virtual environment.
3. `pip install wheel`
4. `sudo apt-get install python-dev`
5. `sudo apt-get install python3-dev`
6. `sudo apt-get install libpython3-dev`
7. `sudo apt install libpython3.9-dev`
8. `pip install yubikey-manager`

When there's time, some of this may be simplified but for now, to get things going, the above is where things are at, |PROJNAME| currently uses yubikey-manager so that is the package that needs to be installed.

Backup with YubiKey
-------------------

You can use a configured YubiKey with the same commands discussed in the main backup/restore documentation (:ref:`cloud-and-local-backup`), for either local or cloud backups. This section will give a brief demo using a local backup.

First, let's create a new encrypted backup, securing the encryption key with a password and the YubiKey:

``atbu backup --full C:\MyData\ G:\MyBackup --yk``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu backup --full C:\MyData\ G:\MyBackup --yk
    atbu - v0.01
    Writing new configuration: G:\MyBackup\.atbu\atbu-config.json
    Storage location: G:\MyBackup
    Storage definition: G:\MyBackup\.atbu\atbu-config.json
    Backup destinations require a storage definition which retains information about the
    storage location, including how to access it and whether it's cloud or filesystem-based.
    Enter a user-friendly name for this backup destination's storage definition.
    Any name you enter will be converted to all lower case.
    If you press ENTER without entering anything, 'mybackup' will be used.
    Enter a name (letters, numbers, spaces): my-backup
    Using the name 'my-backup'...
    Creating backup storage definition...
    Created storage definition my-backup for G:\MyBackup
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
    Require a (p)assword or allow (a)utomatic use of your backup's private key?  [p/A] p
    Creating key...created.

    You have chosen to require a password before a backup/restore can begin which requires you
    to enter a password.

    IMPORTANT: No YubiKey was detected. Please insert your YubiKey before entering your password.
    Enter a password for this backup:******
    Enter a password for this backup again:******
    Press your key now to allow challenge/response...
        (the YubiKey's metal plate was touched at this point)
    Encrypting key...encrypted.
    Storing...
    Keyring information:
    Key=encryption-key
    Service=my-backup
    Username=ATBU-backup-enc-key
    Your key is stored.
    Saving G:\MyBackup\.atbu\atbu-config.json
    G:\MyBackup\.atbu\atbu-config.json has been saved.
    A YubiKey was detected.
    Enter the password for this backup:******
    Press your key now to allow challenge/response...
    Backup location(s)...
    Source location #0 .............. C:\MyData\
    Searching for files...
    Backup destination: G:\MyBackup
    No backup history for 'my-backup'. Creating new history database.
    Starting backup 'my-backup-20220615-053317'...
    Scheduling hashing jobs...
    Wait for 26 backup file operations to complete...
    0% completed of C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    0% completed of C:\MyData\Documents\2021-Budget.xlsx
    88% completed of C:\MyData\Documents\2021-Budget.xlsx
    100% completed of C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    BackupFile: Completed C:\MyData\Documents\2021-Budget.xlsx
    Total bytes .............. 211
    SHA256 original file ..... 9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    SHA256 encrypted file .... 4d47b8ffb952aaa34126d61ebf786e4803ad07511298041a18b37169a140d898
    ---
    BackupFile: Completed C:\MyData\Pictures\Wildlife\Geese\20210703_193244.jpg
    Total bytes .............. 227
    SHA256 original file ..... b8be04fb1a691ff37ef08b0db03c62dd3aa52127944cd5899cbd8ce9bc9ab55e
    SHA256 encrypted file .... c10d64f36a99dad45b104c301cfd05ddb55b96696f96c9a82ac0aba12b3df0a0
    ---
    Backup succeeded: Documents\2021-Budget.xlsx
    Backup succeeded: Pictures\Wildlife\Geese\20210703_193244.jpg
    0% completed of C:\MyData\Pictures\noext\noext1
    0% completed of C:\MyData\Documents\MyImportantNotes.txt
    100% completed of C:\MyData\Documents\MyImportantNotes.txt
    0% completed of C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    0% completed of C:\MyData\Documents\Textually speaking, a novel in pure text.txt
    100% completed of C:\MyData\Documents\Textually speaking, a novel in pure text.txt
    0% completed of C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    0% completed of C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
    98% completed of C:\MyData\Pictures\noext\noext1
    100% completed of C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    100% completed of C:\MyData\Pictures\Wildlife\Deer\20210704_222626.jpg
    100% completed of C:\MyData\Pictures\Yellowstone\20210702_202530.jpg
    BackupFile: Completed C:\MyData\Pictures\Yellowstone\20210702_202203.jpg
    Total bytes .............. 227
    SHA256 original file ..... 41c722fcf02fccf69cc49b3a7a3e46b97a5f1df207c5657feee2d863cd838d5a
    SHA256 encrypted file .... 2bbeeefdd59242465cae98c60b2d99435d4c1200bee175ed3d68dedd2e2ee0fb
    ---
    BackupFile: Completed C:\MyData\Documents\Textually speaking, a novel in pure text.txt
    Total bytes .............. 243
    SHA256 original file ..... c855e8fb8de9fa13b145e4c023ea76b70312cd3624eaf55fda787bb3b9707e4f
    SHA256 encrypted file .... 26e49dec877dfee1a0413f05903058159e5634ca9682dd962dd6081bbde25516

        ... (edited for brevity) ...

    Waiting for backup information to be saved...
    SpecificBackupInformation thread stop initiated. Finishing up...
    Saving in-progress backup information: C:\Users\User\.atbu\atbu-backup-info\my-backup-20220615-053317.atbuinf.tmp
    Saving backup info file: C:\Users\User\.atbu\atbu-backup-info\my-backup-20220615-053317.atbuinf
    Backup info file saved: C:\Users\User\.atbu\atbu-backup-info\my-backup-20220615-053317.atbuinf
    Copying primary C:\Users\User\.atbu\atbu-backup-info\my-backup-20220615-053317.atbuinf to G:\MyBackup\.atbu\atbu-backup-info...
    SpecificBackupInformation background thread ending.
    0% completed of C:\Users\User\.atbu\atbu-backup-info\my-backup.atbuinf
    17% completed of C:\Users\User\.atbu\atbu-backup-info\my-backup.atbuinf
    BackupFile: Completed C:\Users\User\.atbu\atbu-backup-info\my-backup.atbuinf
    Total bytes .............. 243
    SHA256 original file ..... bdcff60fb53cde5eba06f7cdccb1c201460e2a6f7a0e07b3a29c9d583ddb9993
    SHA256 encrypted file .... 0b6f315c01a330bece91e4c3906de8fe1d1695b4859942754997245519989543
    ---
    The backup information has been successfully backed up: C:\Users\User\.atbu\atbu-backup-info\my-backup.atbuinf
    All backup file operations have completed.

    Extension compression ratio report (lower is better):
    '.atbudb' ..................................  11.7%
    '.atbuinf' .................................  16.3%
    '.xlsx' ....................................  84.8%
    '.cr2' .....................................  98.6%
    '.cr2-copy' ................................  98.7%
    '(no extension)' ...........................  99.0%

    ***************
    *** SUCCESS ***
    ***************
    No errors detected during backup.
    Total files ................................. 26
    Total unchanged files ....................... 0
    Total backup operations ..................... 26
    Total errors ................................ 0
    Total successful backups .................... 26
    Success, no errors detected.
    (venv2-3.9.12) PS C:\>

In the above example, the ``--yk`` command line option was specified. The ``--yk`` command line option causes all password operations relating to the backup encryption key password to use the YubiKey.

|PROJNAME| then asks the question...

``Would you like encryption enabled? [Y/n] y``

\.\.\.to which we answer Yes. We then get asked whether or not to use a password...

``Require a (p)assword or allow (a)utomatic use of your backup's private key?  [p/A] p``

We answer 'p' to use a password. Since the ``--yk`` option was specified, this will cause |PROJNAME| to use a password with the YubiKey as described earlier.

You will notice in the example output, it outputs ``IMPORTANT: No YubiKey was detected`` which occurs because the YubiKey was not inserted into the device at the time. Since ``--yk`` was specified on the command line, |PROJNAME| expects a YubiKey to be present in one of the USB ports on the device.

The YubiKey was inserted and we then entered the textual password twice... 

.. code-block:: console

        IMPORTANT: No YubiKey was detected. Please insert your YubiKey before entering your password.
        Enter a password for this backup:******
        Enter a password for this backup again:******
        Press your key now to allow challenge/response...

\.\.\.after entering the password a second time, |PROJNAME| pompts you to "press your key" which is the metal plate on the YubiKey. This instructs the YubiKey that you approve of an HMAC-SHA1 Challenge/Response taking place.

After the key is touched, the backup encryption key is itself encrypted using the YubiKey's response...

.. code-block:: console

    Press your key now to allow challenge/response...
        (the YubiKey's metal plate was touched at this point)
    Encrypting key...encrypted.
    Storing...
    Keyring information:
    Key=encryption-key
    Service=my-backup
    Username=ATBU-backup-enc-key
    Your key is stored.

In the example output further above, you will notice the following 3rd password entry. This is actually |PROJNAME| asking you for your password before it begins a backup. When you enter your password, it again asks you to touch the YubiKey as a way of approving that HMAC-SHA1 Challenge/Response take place.

.. code-block:: console

    A YubiKey was detected.
    Enter the password for this backup:******
    Press your key now to allow challenge/response...
    Backup location(s)...
    Source location #0 .............. C:\MyData\
    Searching for files...
    Backup destination: G:\MyBackup
    No backup history for 'my-backup'. Creating new history database.
    Starting backup 'my-backup-20220615-053317'...

Restore with YubiKey
--------------------

Before we restore with YubiKey, let's try to restore a backup protected by YubiKey without the YubiKey and without the ``--yk`` command line option...

``atbu restore G:\MyBackup backup:last files:* C:\RestorePoint``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu restore G:\MyBackup backup:last files:* C:\RestorePoint
    atbu - v0.01
    Enter the password for this backup:******
    The password appears to be invalid, try again.
    Enter the password for this backup:
    (venv2-3.9.12) PS C:\>

The above command is almost correct except it is missing the ``--yk`` option so |PROJNAME| thinks the backup is protected by a normal textual password alone. Because of that, the textual password alone fails verification. We press CTRL-BREAK or CTRL-C to stop |PROJNAME| and then we enter the correct command by adding the ``--yk`` command line option...

``atbu restore G:\MyBackup backup:last files:* C:\RestorePoint --yk``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu restore G:\MyBackup backup:last files:* C:\RestorePoint --yk
    atbu - v0.01
    A YubiKey was detected.
    Enter the password for this backup:******
    Press your key now to allow challenge/response...
    Will restore 26 files from 'my-backup'
    Starting restore from 'my-backup'...
    Scheduling restore jobs...
    Wait for restore file operations to complete...
    0% completed of C:\RestorePoint\c4198ead-0b50-4f0e-b52b-685b64e7b9f0.atbudb
    0% completed of C:\RestorePoint\Documents\2021-Budget.xlsx
    0% completed of C:\RestorePoint\Documents\MyImportantNotes.txt
    0% completed of C:\RestorePoint\Documents\Textually speaking, a novel in pure text.txt
    0% completed of C:\RestorePoint\Pictures\Events\2021-HolidayParty\20210704_223018.jpg
    0% completed of C:\RestorePoint\Pictures\Events\2021-HolidayParty\20210826_191432.jpg
    RestoreFile: Completed for C:\RestorePoint\c4198ead-0b50-4f0e-b52b-685b64e7b9f0.atbudb
    Total bytes ............................... 17097
    SHA256 download ........................... 147380d26b5037a3732615faf9ea44c72671e0bbd2957d712688e9a58c118595
    SHA256 original ........................... 147380d26b5037a3732615faf9ea44c72671e0bbd2957d712688e9a58c118595
    SHA256 encrypted download ................. 97869486b5a925a8061cb15cbca12883220e45bdfb61c692d0b76bc27b9e57fc
    SHA256 encrypted original ................. 97869486b5a925a8061cb15cbca12883220e45bdfb61c692d0b76bc27b9e57fc
    Restore succeeded: c4198ead-0b50-4f0e-b52b-685b64e7b9f0.atbudb
    RestoreFile: Completed for C:\RestorePoint\Documents\2021-Budget.xlsx
    Total bytes ............................... 6184
    SHA256 download ........................... 9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    SHA256 original ........................... 9d5e060908090d826ee1063bf02fc653c868c952bb4ffd306cf925ae752f2de6
    SHA256 encrypted download ................. 4d47b8ffb952aaa34126d61ebf786e4803ad07511298041a18b37169a140d898
    SHA256 encrypted original ................. 4d47b8ffb952aaa34126d61ebf786e4803ad07511298041a18b37169a140d898
    RestoreFile: Completed for C:\RestorePoint\Documents\MyImportantNotes.txt
    Total bytes ............................... 63
    SHA256 download ........................... 8241f62228083fc758ed375de66123cc1cae138702cc329c8404998854fc0e90
    SHA256 original ........................... 8241f62228083fc758ed375de66123cc1cae138702cc329c8404998854fc0e90
    SHA256 encrypted download ................. ac365477a2ca9493a1b38619c4f41234de8b31dce5c964b64bd74e8746cc0c51
    SHA256 encrypted original ................. ac365477a2ca9493a1b38619c4f41234de8b31dce5c964b64bd74e8746cc0c51
        ...(edited for brevity)...
    All restore file operations have completed.
    ***************
    *** SUCCESS ***
    ***************
    No errors detected during restore.
    Total files ................................. 26
    Total errors ................................ 0
    Total success ............................... 26
    Finished... no errors detected.
    (venv2-3.9.12) PS C:\>

From the above example output, you can see we entered the password after which |PROJNAME| prompted ``Press your key now to allow challenge/response``...

.. code-block:: console


    (venv2-3.9.12) PS C:\> atbu restore G:\MyBackup backup:last files:* C:\RestorePoint --yk
    atbu - v0.01
    A YubiKey was detected.
    Enter the password for this backup:******
    Press your key now to allow challenge/response...

At that point, where it says ``Press your key now to allow challenge/response...`` we have a few seconds to touch the YubiKey before the operation times out. When we touch the YubiKey before the time out, it allowed the YubiKey to process the typed password (the challenge) and provide back, as a response to the challenge, the final code that will unlock the backup encryption key.

After the password is verified, the restore option proceeds and completes successfully.
