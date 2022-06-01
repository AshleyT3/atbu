Overview
========
Intro - READ THIS FIRST!
------------------------
|PROJNAME| is a Python command line utility with two general areas of features as follows...

* **Backup/Restore:** Cloud and local backup/restore/verify, including deduplication capabilities, bitrot detection, and more.
* **Persistent file information:** A relatively simple but useful utility to diff/compare directories to gain insight into undesired file duplication, missing expected redundancy, and bitrot detection.

**IMPORTANT: READ THIS**
* I created this tool given my own personal needs.
* Beyond my own ad-hoc usage, for open source use by others, it should be considered "alpha" as of May 2022.
* With regards to backup/restore, given |PROJNAME|'s alpha nature, please do not use it as your primary/only backup/restore tool. Have redundancy elsewhere. Your test-driving is welcome, just be reasonably cautious.
* The walkthroughs outline the most tested/common scenarios.
* This is my own personal utility being shared via open source. I need more time actually using it to speak more confidently about it, to eventually remove these precautionary bullet points.

Highlights
----------

* **Backup** local files to either local drives or cloud storage faciltiies.
   * Use the same command-line tool to perform **full**, **incremental**, or **incremental Plus** backups to a local folder on any drive, or the cloud.
   * **Verify/Restore** files using the same command line tool.
   * View listings and information of backups.
   * Optionally utilize **SHA256-based de-duplication capabilities.** (Incremental Plus and Increment Plus with de-duplication)
   * **Encryption/decryption keys are completely under your control.**
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

|PROJNAME| Walkthroughs
-----------------------

.. toctree::
   :maxdepth: 1

   backup-restore-walkthrough
   persistent-file-info-walkthrough
