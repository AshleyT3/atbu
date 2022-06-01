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

# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=unused-import

import os
from pathlib import Path
from uuid import uuid4
import logging
from pytest import LogCaptureFixture, CaptureFixture, fail, raises

from atbu.common.queued_worker import (
    QueuedSubprocessWorkManager,
)

LOGGER = logging.getLogger(__name__)


def setup_module(module):
    pass


def teardown_module(module):
    pass


def queue_worker_func(parm_top_secret, parent_pid):
    assert parent_pid != os.getpid()
    return (
        parent_pid,
        os.getpid(),
        parm_top_secret,
    )


def test_queue_worker(tmp_path: Path):
    top_secret = str(uuid4())
    qw = QueuedSubprocessWorkManager()
    qw.start()
    qw.put_work(queue_worker_func, top_secret, os.getpid())
    result = qw.get_result(timeout=60)
    assert result[0] == os.getpid()
    assert result[1] != os.getpid()
    assert result[2] == top_secret
    qw.stop()
