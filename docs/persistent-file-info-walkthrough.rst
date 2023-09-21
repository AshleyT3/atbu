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

``atbu update-digests --per-dir --locations C:\MyData\ D:\MyData\``

Or using shorter argument names:

``atbu update-digests --pd -l C:\MyData\ D:\MyData\``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests --per-dir --locations C:\MyData\ D:\MyData\
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

``atbu diff --per-dir --location-a C:\MyData\ --location-b D:\MyData\``

Or using shorter argument names:

``atbu diff --pd --la C:\MyData\ --lb D:\MyData\``

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu diff --per-dir --location-a C:\MyData\ --location-b D:\MyData\
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

    (venv2-3.9.12) PS C:\> atbu update-digests --pd --change-detection-type digest -l D:\MyData\
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

    (venv2-3.9.12) PS C:\> atbu diff --pd --la C:\MyData\ --lb D:\MyData\
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

    (venv2-3.9.12) PS C:\> atbu save-db --db c:\my-ext-drives-photo-inventory.json --pd -l D:\MyData\ E:\MyData\
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

    (venv2-3.9.12) PS C:\> atbu diff --pd --la C:\MyData\ --lb C:\my-ext-drives-photo-inventory.json
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

``atbu save-db --db c:\my-D-backup-drive-inventory.json --pd -l D:\MyData\``

``atbu save-db --db c:\my-E-backup-drive-inventory.json --pd -l E:\MyData\``

**Example...**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu save-db --db c:\my-D-backup-drive-inventory.json --pd -l D:\MyData\
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
    (venv2-3.9.12) PS C:\> atbu save-db --db c:\my-E-backup-drive-inventory.json --pd -l E:\MyData\
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

    (venv2-3.9.12) PS C:\> atbu diff --pd --la C:\MyData\ --lb C:\my-D-backup-drive-inventory.json
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

Let's update-digests as before, but this time we will specify '--pf' or '--per-file' before the directory as follows...

* ``atbu update-digests --pf -l C:\MyData``
* ``atbu update-digests --per-file -l C:\MyData``

Specifying the '--pf' or '--per-file' as an argument before a location causes |PROJNAME| to store or use persistence information per-file (for each file). Or you can think of it as "persistence file" as opposed to "persistence directory .json db."

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests --pf -l C:\MyData
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

``atbu update-digests --per-file -l d:\MyData-Year-2015-Hard-Drive``

**Example output:**

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests --per-file -l d:\MyData-Year-2015-Hard-Drive
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

``atbu update-digests --cdt digest --per-file -l d:\MyData-Year-2015-Hard-Drive``

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu update-digests --cdt digest --per-file -l d:\MyData-Year-2015-Hard-Drive
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

* **Using the same persistence type:** First, let's note that, since we used "--per-file" in 2015, it is important to use "--per-file" again as shown above because, without doing that, |PROJNAME| would create a per-dir database by default, ignoring the information files already present. We want to take advantage of that history that has been living side-by-side with our important data files, so we use "--per-file" to instruct |PROJNAME| to check/update persisted file information in those locations. 
* **Forcing digest check after many years:** By specifying -cdt digest, we instruct |PROJNAME| to re-generate all digests and compare them with the existing 2015 history. This is being done in this example because 7 years is a long time, and that old 2015 hard drive has been used for many purposes, inserted in various machines, and sitting in various storage locations, some perhaps not so cool. We re-gen digests after a long period of time in this example because it's a way of comparing current content with the 2015 content.
* **New files discovered:** |PROJNAME| has observed that files within d:\\MyData-Year-2015-Hard-Drive\\files-while-traveling-in-2016 never had their persistent information saved so their information was saved as part of the above update-digests command (see lines with "Creating info").
* **Potential corruption:** |PROJNAME| detected potential bitrot or other sneaky corruption for the file 20210704_222527.jpg. Sneaky corruption is when the digest for a file differs from the last time it was captured despite the file date/time and size not having changed. With the file 20210704_222527.jpg in the example, it had one digest in 2015, but has a different digest now in 2022, but the file's date/time and size have not changed. It is typically bad practice and not typical for programs to update files and force an older date so |PROJNAME| diff views such as a potentially bad thing and alerts you so you can investigate.
    * **VERY IMPORTANT:** You only get one chance to see bitrot / sneaky file corruption because |PROJNAME| will update the file's persistent history to reflect the new digest, which means it will no longer detect the same issue on subsequent digest updates. Pay close attention, therefore, to the output of the command. You might consider using the |PROJNAME| --logfile command to capture the details in a file. You can keep the log file somewhere as a form of history you can review as needed.

So already we see one issue with that older hard drive. Let's say you prefer a manual process, you do not wnat tools deleting files, but you want to organize them automatically so you can see what's most important in consolidaton. One feature of |PROJNAME| diff is that it can move or delete files files that are both in location A and B. Let's try that with move using the old and new hard drives from the above example.

.. code-block:: console

    atbu diff --per-file --la d:\MyData-Year-2015-Hard-Drive --lb e:\MyData-Year-2022-Hard-Drive --action move-duplicates --md d:\MyData-Year-2015-Hard-Drive-Duplicates

.. code-block:: console

    (venv2-3.9.12) PS C:\> atbu diff --per-file --la d:\MyData-Year-2015-Hard-Drive --lb e:\MyData-Year-2022-Hard-Drive --action move-duplicates --md d:\MyData-Year-2015-Hard-Drive-Duplicates
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

Going forward, my ingestion workflow will, as a matter of course, involve generating .atbu digest sidecar files, at least for large irreplacable photos/videos. When those currently new drives age and become old, they will already have .atbu digest files so I'm good to go for validating and comparing contents as time moves forward.
