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
r"""An instance of HasherDefinitions is configured with one or more
hashing algorithms, where it can create a Hasher instance that can
produce a hash for each algorithm simultaneously. Currently, only a
single algorithm of SHA256 is used but there is room to expand out
as needed (there just was not time during initial creation, so desire
was to focus on SHA256 as the so-called "primary" hash algo).
"""
import hashlib

from .singleton import Singleton
from .exception import SingletonAlreadyCreated

DEFAULT_HASH_ALGORITHM = "sha256"


class Hasher:
    def __init__(self, hashers):
        self.hashers = hashers

    def __iter__(self):
        return self.hashers

    def get_primary_hashing_algo_name(self):
        return self.hashers[0][0]

    def update_all(self, data):
        for h in self.hashers:
            h[1].update(data)

    def get_digests(self):
        r = {}
        for h in self.hashers:
            r[h[0]] = h[1].digest()
        return r

    def get_hexdigests(self):
        r = {}
        for h in self.hashers:
            r[h[0]] = h[1].hexdigest()
        return r

    def get_primary_hexdigest(self) -> str:
        return self.get_hexdigests()[self.get_primary_hashing_algo_name()]


class HasherDefinitions:
    def __init__(self, algos: list[str] = None):
        if algos is None:
            algos = [DEFAULT_HASH_ALGORITHM]
        self.hash_classes = []
        for a in algos:
            c = getattr(hashlib, a)
            if c is None:
                raise NameError(f"Algorithm unknown: {a}")
            self.hash_classes.append((a, c))

    def create_hasher(self) -> Hasher:
        r = []
        for c in self.hash_classes:
            r.append((c[0].lower(), c[1]()))
        return Hasher(r)

    def get_primary_hashing_algo_name(self):
        return self.hash_classes[0][0].lower()


class GlobalHasherDefinitions(HasherDefinitions, metaclass=Singleton):
    _init_algos: list[str] = None

    def __init__(self, algos: list[str] = None):
        if self._init_algos:
            if algos:
                raise SingletonAlreadyCreated(
                    "Access to singleton after initial creation must have no arguments."
                )
            return  # do not call base class __init__ after first-time init.
        if not algos:
            algos = [DEFAULT_HASH_ALGORITHM]
        if not isinstance(algos, list):
            raise ValueError(
                f"GlobalHasherDefinitions: The algos argument must be a list of algorithms."
            )
        self._init_algos = algos
        super().__init__(algos)
