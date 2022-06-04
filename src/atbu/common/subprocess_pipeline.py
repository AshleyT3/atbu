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
r"""SubprocessPipeline.
"""

import os
import logging
import multiprocessing
import concurrent.futures
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, ProcessPoolExecutor
import queue
from typing import Callable
from .exception import *

class PipelineWorkItem:
    def __init__(
        self,
        user_obj,
        **kwargs,
    ) -> None:
        self.cur_stage = 0
        self.user_obj = user_obj
        self.user_kwargs = kwargs
        self.exception: Exception = None
        self.is_failed: bool = False

class PipelineStage:
    def __init__(
        self,
        fn_determiner: Callable[[PipelineWorkItem], bool]=None,
        fn_worker: Callable[..., PipelineWorkItem]=None,
        **stage_kwargs,
    ) -> None:
        self.fn_determiner = fn_determiner
        self.fn_worker = fn_worker
        self.stage_kwargs = stage_kwargs

    def is_subprocess(self):
        return True

    def is_for_stage(self, pwi: PipelineWorkItem) -> bool:
        if self.fn_determiner is None:
            raise InvalidStateError(
                f"PipelineStage fn_determiner is None, cannot determine anything."
            )
        return self.fn_determiner(pwi)

    def perform_stage_work(
        self,
        pwi: PipelineWorkItem,
        **kwargs
    ):
        if self.fn_worker is None:
            raise InvalidStateError(
                f"PipelineStage fn_worker is None, cannot work, looks like a holiday today."
            )
        result = self.fn_worker(pwi, **kwargs)
        return result


class ThreadPipelineStage(PipelineStage):
    def is_subprocess(self):
        return False


class SubprocessPipeline:
    def __init__(
        self,
        stages: list[PipelineStage]=None,
        max_workers=None,
        process_initfunc=None,
        process_initargs=()
    ) -> None:
        if stages is None:
            stages = list[PipelineStage]()
        if not isinstance(stages, list):
            raise InvalidFunctionArgument(
                f"Expecting stages to be a non-zero length list."
            )
        self._stages = stages
        self._is_shutdown = False  # Accessed by parent process only.
        self._wi_to_wifut = {}
        self._wi_to_fut_cond = multiprocessing.Condition()
        self._thread_exec = ThreadPoolExecutor()
        self._pl_worker_future = None
        self._input_queue_lock = multiprocessing.Lock()
        self._input_queue_fut: Future = None
        self._pl_input_queue = queue.Queue()  # Accessed in parent only.
        self._process_exec = ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=process_initfunc,
            initargs=process_initargs,
        )
        self._pl_pending_futs: dict[Future] = {}
        self.was_graceful_shutdown = False
        self.anomalies = list[Anomaly]()

    def add_stage(self, stage: PipelineStage):
        self._stages.append(stage)

    def _start(self):
        if self._is_shutdown:
            raise InvalidFunctionArgument(
                f"QueuedSubprocessPipeline has already been started and stopped."
            )
        if self._pl_worker_future is not None:
            return
        self._pl_worker_future = self._thread_exec.submit(
            SubprocessPipeline._pl_worker, self
        )

    def shutdown(self):
        if self._pl_worker_future is None:
            return
        while len(self._wi_to_wifut) > 0:
            with self._wi_to_fut_cond:
                if len(self._wi_to_wifut) == 0:
                    break
                self._wi_to_fut_cond.wait()
        self._internal_submit(None)
        self._pl_worker_future.result()
        self._pl_worker_future = None
        if self._process_exec is not None:
            self._process_exec.shutdown()
        if self._thread_exec is not None:
            self._thread_exec.shutdown()


    def _fail_all_pending(self, ex: Exception):
        for wi, wifut in self._wi_to_wifut.items():
            if wifut.done():
                continue
            wi.exception = ex
            wi.is_failed = True
            wifut.set_exception(ex)

    def _pl_worker(self):
        try:
            self._pl_worker_inner()
            self.was_graceful_shutdown = True
        except Exception as ex:
            self._fail_all_pending(ex)
            raise

    def _pl_worker_inner(self):
        is_shutdown: bool = False
        while not is_shutdown:
            input_queue_fut = self._create_input_queue_future()
            all_futs = set(self._pl_pending_futs)
            all_futs.add(input_queue_fut)
            done_futs, not_done_futs = concurrent.futures.wait( # pylint: disable=unused-variable
                fs=all_futs,
                return_when=FIRST_COMPLETED
            )
            for done_fut in done_futs:
                wi: PipelineWorkItem = None
                if done_fut in self._pl_pending_futs:
                    wi = self._pl_pending_futs[done_fut]
                    del self._pl_pending_futs[done_fut]
                    if done_fut.exception():
                        wi.exception = done_fut.exception()
                        wi.is_failed = True
                    else:
                        wi_from_sp: PipelineWorkItem = done_fut.result()
                        if not isinstance(wi_from_sp, PipelineWorkItem):
                            wi.exception = PipelineResultIsNotPipelineWorkItem(
                                f"The pipeline stage was successful but it returned "
                                f"something other than a PipelineWorkItem."
                            )
                            wi.is_failed = True
                        else:
                            wi.__dict__ = wi_from_sp.__dict__.copy()
                            wi.cur_stage += 1
                elif done_fut == input_queue_fut:
                    with self._input_queue_lock:
                        if self._pl_input_queue.qsize() == 0:
                            continue
                        try:
                            wi = self._pl_input_queue.get()
                        except queue.Empty as ex:
                            self.anomalies.append(
                                Anomaly(
                                    kind=ANOMALY_KIND_EXCEPTION,
                                    exception=ex,
                                    message="Unexpected Empty on _pl_input_queue.get()"
                                )
                            )
                            continue
                        if wi is None:
                            is_shutdown = True
                            break
                else:
                    raise InvalidStateError(
                        f"Expected Future for pending pipeline activity or input queue, "
                        f"but the Future matched neither."
                    )
                if wi is None:
                    continue
                if wi.is_failed or wi.exception is not None:
                    wi.is_failed = True
                    self._pipeline_item_completed(wi)
                    continue
                if wi.cur_stage < 0 or wi.cur_stage > len(self._stages):
                    wi.exception = InvalidStateError(
                        f"Invalid pipeline stage cur_stage={wi.cur_stage}"
                    )
                    wi.is_failed = True
                    self._pipeline_item_completed(wi)
                    continue
                while wi.cur_stage < len(self._stages):
                    next_stage = self._stages[wi.cur_stage]
                    try:
                        is_for_next_stage = next_stage.is_for_stage(wi)
                    except Exception as ex:
                        wi.exception = ex
                        wi.is_failed = True
                        wi.cur_stage = len(self._stages)
                        break
                    if not is_for_next_stage:
                        wi.cur_stage += 1
                        continue
                    kwargs = next_stage.stage_kwargs
                    if wi.user_kwargs is not None:
                        kwargs = kwargs | wi.user_kwargs
                    if next_stage.is_subprocess():
                        fut = self._process_exec.submit(
                            next_stage.perform_stage_work,
                            wi,
                            **kwargs
                        )
                    else:
                        fut = self._thread_exec.submit(
                            next_stage.perform_stage_work,
                            wi,
                            **kwargs
                        )
                    self._pl_pending_futs[fut] = wi
                    break
                if wi.cur_stage >= len(self._stages):
                    self._pipeline_item_completed(wi)

    def _pipeline_item_completed(
        self,
        wi: PipelineWorkItem,
    ):
        fut: Future
        with self._wi_to_fut_cond:
            fut = self._wi_to_wifut.get(wi)
            if not fut:
                raise InvalidStateError(
                    f"Cannot find Future for work item."
                )
            del self._wi_to_wifut[wi]
            self._wi_to_fut_cond.notify_all()
            fut.set_result(wi)

    def _create_input_queue_future(self):
        with self._input_queue_lock:
            self._input_queue_fut = Future()
            qsize = self._pl_input_queue.qsize()
            if qsize > 0:
                self._input_queue_fut.set_result(qsize)
            return self._input_queue_fut

    def _internal_submit(
        self,
        work_item: PipelineWorkItem,
    ) -> Future:
        self._start()
        self._pl_input_queue.put(work_item)
        with self._input_queue_lock:
            if self._pl_input_queue.qsize() > 0:
                if (
                    self._input_queue_fut is not None
                    and not self._input_queue_fut.done()
                ):
                    self._input_queue_fut.set_result(
                        self._pl_input_queue.qsize()
                    )
        wi_fut = Future()
        self._wi_to_wifut[work_item] = wi_fut
        return wi_fut

    def submit(
        self,
        work_item: PipelineWorkItem,
    ) -> Future:
        if work_item is None:
            raise InvalidFunctionArgument(
                f"work_item must be a PipelineWorkItem."
            )
        if self._wi_to_wifut.get(work_item):
            raise InvalidFunctionArgument(
                f"work_item is already in the pipeline."
            )
        return self._internal_submit(
            work_item=work_item,
        )
