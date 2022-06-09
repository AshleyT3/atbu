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
r"""Singleton global hasher for the process.
"""

from atbu.common.exception import SingletonAlreadyCreated
from atbu.common.hasher import (
    DEFAULT_HASH_ALGORITHM,
    HasherDefinitions,
)
from atbu.common.singleton import Singleton

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
