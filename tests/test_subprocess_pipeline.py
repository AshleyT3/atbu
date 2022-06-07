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

from cmath import exp
from concurrent.futures import Future, ProcessPoolExecutor
import os
from pathlib import Path
import logging
from random import randint
import time
from pytest import LogCaptureFixture, CaptureFixture, fail
import pytest
from atbu.common.exception import PipeConnectionAlreadyEof


from atbu.common.mp_pipeline import (
    MultiprocessingPipeline,
    PipeConnectionIO,
    PipelineStage,
    SubprocessPipelineStage,
    ThreadPipelineStage,
    PipelineWorkItem,
)
from .common_helpers import establish_random_seed

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
        name="test_subprocess_pipeline_basic",
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
    sp = MultiprocessingPipeline(
        max_simultaneous_work_items=min(os.cpu_count(), 15),
        name="test_subprocess_pipeline_large",
    )
    for i in range(stages):
        sp.add_stage(
            stage=LargePipelineStage()
        )
    wi = LargePipelineWorkItem()
    f = sp.submit(wi)
    r_wi: PipelineWorkItem = f.result()
    assert wi == r_wi
    if r_wi.exceptions is not None:
        # Should be succesful.
        # raise the the first exception so pytest displays its message.
        raise r_wi.exceptions[0]
    assert not r_wi.is_failed
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
    sp = MultiprocessingPipeline(
        name="test_subprocess_pipeline_large_mixed",
        max_simultaneous_work_items=min(os.cpu_count(), 15),
    )
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
    if r_wi.exceptions is not None:
        # Should be succesful.
        # raise the first exception in the list so pytest displays its message.
        raise r_wi.exceptions[0]
    assert not r_wi.is_failed
    assert r_wi.is_ok
    assert r_wi.num == 20
    assert r_wi.pid == os.getpid()
    sp.shutdown()
    assert sp.was_graceful_shutdown

def gather_func(idnum, pr: PipeConnectionIO):
    print(f"ENTER id={idnum} pid={os.getpid()}")
    results = []
    while not pr.eof:
        results.append(pr.read())
    assert pr.read() == bytes()
    print(f"EXIT id={idnum} {os.getpid()} len={len(results)}")
    pr.close()
    return results

def test_pipe_io_connection_basic(tmp_path: Path):
    ppe = ProcessPoolExecutor()
    pr, pw = PipeConnectionIO.create_reader_writer_pair()
    fut = ppe.submit(
        gather_func,
        0,
        pr
    )
    expected = [
        "abc".encode(),
        "123".encode(),
        "the end".encode(),
    ]
    for i, e in enumerate(expected):
        if i < len(expected)-1:
            num_written = pw.write(e)
            assert num_written == len(e)
        else:
            num_written = pw.write_eof(e)
            assert num_written == len(e)
    with pytest.raises(PipeConnectionAlreadyEof):
        pw.write_eof(b'xyz')
    r = fut.result(timeout=60)
    assert len(r) == 3
    assert r == expected

def test_pipe_io_connection_many(tmp_path: Path):
    seed = bytes([0xdb, 0x9e, 0xec, 0x45])
    seed = establish_random_seed(tmp_path=tmp_path, random_seed=seed)
    print(f"Seed={seed.hex(' ')}")
    print(f"Parent pid={os.getpid()}")
    total_conn = 50
    ppe = ProcessPoolExecutor(max_workers=total_conn)
    rw_fut_conn: list[tuple[Future, PipeConnectionIO]] = []
    for i in range(total_conn):
        pr, pw = PipeConnectionIO.create_reader_writer_pair()
        fut = ppe.submit(
            gather_func,
            i,
            pr
        )
        rw_fut_conn.append((i, fut, pw,))
        print(f"#{len(rw_fut_conn)-1} submitted.")

    expected = [
        ("abc"*1024*1024*7).encode(),
        ("123"*1024*1024*3).encode(),
        ("the end"*100).encode(),
    ]

    print(f"Begin writing...")

    process_writing = list(rw_fut_conn)
    while len(process_writing) > 0:
        idx = randint(0, len(process_writing) - 1)
        idnum, fut, pw = process_writing[idx]
        is_done = fut.done()
        is_running = fut.running()
        if not is_running:
            time.sleep(0.010)
            continue
        print(f"id={idnum}: is_done={is_done} is_running={is_running} {str(fut)}")
        for i, e in enumerate(expected):
            if i < len(expected)-1:
                num_written = pw.write(e)
                assert num_written == len(e)
            else:
                num_written = pw.write_eof(e)
                assert num_written == len(e)
        with pytest.raises(PipeConnectionAlreadyEof):
            pw.write_eof(b'xyz')
        del process_writing[idx]

    print(f"Waiting for Futures...")
    while len(rw_fut_conn) > 0:
        idx = randint(0, len(rw_fut_conn) - 1)
        idnum, fut, pw = rw_fut_conn[idx]
        is_done = fut.done()
        is_running = fut.running()
        print(f"BEGIN WAIT: id={idnum}: is_done={is_done} is_running={is_running}")
        assert is_running or is_done
        r = fut.result(timeout=120)
        print(f"END WAIT: id={idnum}: is_done={is_done} is_running={is_running}")
        assert len(r) == 3
        assert r == expected
        del rw_fut_conn[idx]
