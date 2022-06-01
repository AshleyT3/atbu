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

with open("README.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="atbu-pkg",
    version="0.0.1",
    author="Ashley R. Thomas",
    author_email="ashley.r.thomas.701@gmail.com",
    description= (
        "ATBU package supports local/cloud backup/restore "
        "as well as local file integrity diff tool for helping in "
        "efforts to manage file integrity, duplication, and bitrot detection."
    ),
    entry_points = {
        'console_scripts': ['atbu=atbu.common.command_line:main']
    },
    long_description=long_description,
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
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "cryptography >= 36.0.2",
        "pwinput >= 1.0.2",
        "keyring >= 23.5.0",
        "apache-libcloud >= 3.5.1",
        "google-auth >= 2.6.5",
        "google-cloud-storage >= 2.3.0",
        "google-resumable-media >= 2.3.2",
        "tabulate >= 0.8.9"
    ]
)
