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

from dataclasses import dataclass
import os
from pathlib import Path
from uuid import uuid4
import logging
from pytest import LogCaptureFixture, CaptureFixture, fail, raises

from atbu.common.mp_pipeline import (
    MultiprocessingPipeline,
    PipelineStage,
    SubprocessPipelineStage,
    ThreadPipelineStage,
    PipelineWorkItem,
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

def int_stage0(wi: PipelineWorkItem):
    wi.user_obj[0] = 100
    return wi

def int_stage1(wi: PipelineWorkItem):
    wi.user_obj[0] = wi.user_obj[0] * 2
    wi.user_obj[1] = "stage1"
    return wi

def int_stage2(wi: PipelineWorkItem):
    wi.user_obj[0] = wi.user_obj[0] * 2
    wi.user_obj[2] = f"stage2: got this from parent: {wi.user_obj['parent']}"
    return wi

def always_yes(wi: PipelineWorkItem):
    return True

def test_subprocess_pipeline_basic(tmp_path: Path):
    sp = MultiprocessingPipeline(
        stages=[
            SubprocessPipelineStage(
                fn_determiner=always_yes,
                fn_worker=int_stage0,
            ),
            SubprocessPipelineStage(
                fn_determiner=always_yes,
                fn_worker=int_stage1,
            ),
            SubprocessPipelineStage(
                fn_determiner=always_yes,
                fn_worker=int_stage2,
            )
        ]
    )

    d = {}
    d["parent"] = "This is from parent"
    wi = PipelineWorkItem(d)
    f = sp.submit(wi)
    r_wi = f.result()
    assert wi == r_wi
    assert not wi.is_failed
    assert wi.exception is None
    assert wi.user_obj["parent"] == d["parent"]
    assert wi.user_obj[1] == "stage1"
    assert wi.user_obj[2] == "stage2: got this from parent: This is from parent"
    assert wi.user_obj[0] == 400
    sp.shutdown()
    assert sp.was_graceful_shutdown


class LargePipelineWorkItem(PipelineWorkItem):
    def __init__(self) -> None:
        super().__init__(user_obj=self)
        self.is_ok = True
        self.num = 0
        self.pid = os.getpid()


class LargePipelineStage(SubprocessPipelineStage):
    def __init__(self) -> None:
        super().__init__()
    def is_for_stage(self, pwi: LargePipelineWorkItem) -> bool:
        pwi.is_ok = not pwi.is_ok
        return not pwi.is_ok
    def perform_stage_work(
        self,
        pwi: LargePipelineWorkItem,
        **kwargs,
    ):
        pwi.num += 1
        return pwi


def test_subprocess_pipeline_large(tmp_path: Path):
    stages = 100
    sp = MultiprocessingPipeline()
    for i in range(stages):
        sp.add_stage(
            stage=LargePipelineStage()
        )
    wi = LargePipelineWorkItem()
    f = sp.submit(wi)
    r_wi: PipelineWorkItem = f.result()
    assert wi == r_wi
    if isinstance(r_wi.exception, Exception):
        # Should be succesful.
        # raise the exception so pytest displays its message.
        raise r_wi.exception
    assert not r_wi.is_failed
    assert r_wi.exception is None
    assert r_wi.is_ok
    assert r_wi.num == 50
    sp.shutdown()
    assert sp.was_graceful_shutdown

class MixedPipelineSubprocessStage(PipelineStage):
    def __init__(self) -> None:
        super().__init__()
    @property
    def is_subprocess(self):
        return True
    def is_for_stage(self, pwi: LargePipelineWorkItem) -> bool:
        return True
    def perform_stage_work(
        self,
        pwi: LargePipelineWorkItem,
        **kwargs,
    ):
        assert pwi.pid != os.getpid()
        pwi.num += 1
        return pwi

def perform_thread_stage_work(
    pwi: LargePipelineWorkItem,
    **kwargs,
):
    assert pwi.pid == os.getpid()
    pwi.num += 1
    return pwi

def test_subprocess_pipeline_large_mixed(tmp_path: Path):
    sp = MultiprocessingPipeline()
    for _ in range(10):
        sp.add_stage(
            stage=MixedPipelineSubprocessStage()
        )
        sp.add_stage(
            stage=ThreadPipelineStage(
                fn_determiner=lambda pwi: True,
                fn_worker=perform_thread_stage_work,
            )
        )
    wi = LargePipelineWorkItem()
    f = sp.submit(wi)
    r_wi: PipelineWorkItem = f.result()
    assert wi == r_wi
    if isinstance(r_wi.exception, Exception):
        # Should be succesful.
        # raise the exception so pytest displays its message.
        raise r_wi.exception
    assert not r_wi.is_failed
    assert r_wi.exception is None
    assert r_wi.is_ok
    assert r_wi.num == 20
    assert r_wi.pid == os.getpid()
    sp.shutdown()
    assert sp.was_graceful_shutdown
