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

import setuptools

# Redirect from long_description to github README.rst since
# PyPi chokes on this particular README.rst.
# with open("README.rst", "r", encoding="utf-8") as fh:
#    long_description = fh.read()

setuptools.setup(
    name="atbu-pkg",
    version="0.0.22",
    author="Ashley R. Thomas",
    author_email="ashley.r.thomas.701@gmail.com",
    description= (
        "ATBU package supports local/cloud backup/restore "
        "as well as local file integrity diff tool for helping in "
        "efforts to manage file integrity, duplication, and bitrot detection."
    ),
    entry_points = {
        'console_scripts': ['atbu=atbu.tools.backup.command_line:main']
    },
    long_description="""
ATBU Backup & Persistent File Information is a local/cloud backup/restore
command-line utility with optional deduplication and bitrot detection,
plus a little utility with useful digest-based directory file diff'ing.

Install: `pip install atbu-pkg`

GitHub: https://github.com/AshleyT3/atbu

Documentation: https://atbu.readthedocs.io/en/latest/
""",
    long_description_content_type="text/markdown",
    url="https://github.com/AshleyT3/atbu",
    project_urls={
        "Bug Tracker": "https://github.com/AshleyT3/atbu/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_namespace_packages(where="src"),
    python_requires=">=3.9, <3.11",
    install_requires=[
        "atbu-common-pkg >= 0.0.6",
        "atbu-mp-pipeline-pkg >= 0.0.9",
        "cryptography >= 36.0.2",
        "pwinput >= 1.0.2",
        "keyring >= 23.5.0",
        "apache-libcloud >= 3.5.1",
        "azure-storage-blob >= 12.16.0",
        "google-auth >= 2.6.5",
        "google-cloud-storage >= 2.3.0",
        "google-resumable-media >= 2.3.2",
        "tabulate >= 0.8.9",
        "Send2Trash >= 1.8.0",
    ]
)
