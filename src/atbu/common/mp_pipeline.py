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
r"""MultiprocessingPipeline.
"""

# pylint: disable=missing-class-docstring

from abc import abstractmethod
import copy
import io
import logging
import multiprocessing
import concurrent.futures
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, ProcessPoolExecutor
from multiprocessing.connection import Connection
import queue
import time
from typing import Callable

from .exception import *
from .mp_global import get_verbosity_level

def _is_very_verbose_logging():
    return get_verbosity_level() >= 2 and logging.getLogger().getEffectiveLevel() >= logging.DEBUG

PIPE_CONN_MSG_CMD_DATA = "data"
PIPE_CONN_MSG_CMD_DATA_FINAL = "data-final"
PIPE_CONN_MSG_DATA_CMDS = [PIPE_CONN_MSG_CMD_DATA, PIPE_CONN_MSG_CMD_DATA_FINAL]
class PipeConnectionMessage:
    def __init__(self, cmd: str, data: bytes=None) -> None:
        if data is None:
            data = bytes()
        if not isinstance(data, (bytes, bytearray)):
            raise InvalidFunctionArgument(
                f"Expecting data to be bytes or bytearray."
            )
        self.cmd = cmd
        self.data = data

class PipeConnectionIO(io.RawIOBase):
    """Allow FileIO-like interface with a Pipe Connection object. Not a
    fully functional RawIOBase but close enough to meet certain the needs
    of certain classes which can accept/use such.
    """
    # pylint: disable=no-self-use
    def __init__(self, c: Connection, is_write: bool) -> None:
        super().__init__()
        self.c = c
        self.is_write = is_write
        self._num_bytes = 0
        self._cached_fileno = self.c.fileno()
        self._eof = False
        if _is_very_verbose_logging():
            logging.debug(
                f"ConnectionIO.__init__: fileno={self._cached_fileno} is_write={is_write} {'Sender' if is_write else 'Receiver'}."
            )

    @staticmethod
    def create_reader_writer_pair():
        r, w = multiprocessing.connection.Pipe(duplex=False)
        return (
            PipeConnectionIO(c=r, is_write=False),
            PipeConnectionIO(c=w, is_write=True)
        )

    def reset_num_bytes(self):
        self._num_bytes = 0

    @property
    def eof(self):
        return self._eof

    @property
    def num_bytes(self):
        return self._num_bytes

    def tell(self) -> int:
        return self.num_bytes

    def fileno(self) -> int:
        return self.c.fileno()

    def send_message(self, msg: PipeConnectionMessage):
        size = -1
        try:
            if not isinstance(msg, PipeConnectionMessage):
                raise InvalidFunctionArgument(
                    f"PipeConnectionIO.send_message: msg must be PipeConnectionMessage"
                )
            if msg.cmd is None or not isinstance(msg.cmd, str):
                raise InvalidFunctionArgument(
                    f"PipeConnectionIO.send_message: msg.cmd must be str"
                )
            if msg.data is not None and isinstance(msg.data, (bytes, bytearray)):
                size = len(msg.data)
            if msg.cmd == PIPE_CONN_MSG_CMD_DATA_FINAL and self.eof:
                raise PipeConnectionAlreadyEof(
                    f"PipeConnectionIO.send_message: cannot send PIPE_CONN_MSG_CMD_DATA_FINAL, already eof."
                )
            if _is_very_verbose_logging():
                logging.debug(
                    f"PipeConnectionIO.send_message: sending: fileno={self._cached_fileno} cmd={msg.cmd} size={size}..."
                )
            self.c.send(msg)
            if msg.cmd == PIPE_CONN_MSG_CMD_DATA_FINAL:
                self._eof = True
            if size != -1:
                self._num_bytes += size
                if _is_very_verbose_logging():
                    logging.debug(
                        f"PipeConnectionIO.send_message: sent: fileno={self._cached_fileno} cmd={msg.cmd} size={size} conv_total={self._num_bytes}"
                    )
            else:
                if _is_very_verbose_logging():
                    logging.debug(
                        f"PipeConnectionIO.send_message: sent: fileno={self._cached_fileno} cmd={msg.cmd}: data as bytes not present."
                    )
        except Exception as ex:
            logging.error(
                f"PipeConnectionIO.send_message: "
                f"fileno={self._cached_fileno} num_bytes={size} "
                f"Exception: {exc_to_string(ex)}"
            )
            raise

    def recv_message(self) -> PipeConnectionMessage:
        try:
            if _is_very_verbose_logging():
                logging.debug(
                    f"PipeConnectionIO.recv_message: receiving: fileno={self._cached_fileno}..."
                )
            msg  = self.c.recv()
            if not isinstance(msg, PipeConnectionMessage):
                raise InvalidPipeConnectionMessage(
                    f"PipeConnectionIO.recv_message: "
                    f"Expecting InvalidPipeConnectionMessage but got {type(msg)}"
                )
            if msg.cmd is None:
                raise InvalidPipeConnectionMessage(
                    f"PipeConnectionIO.recv_message: "
                    f"Expecting msg.cmd to be a str but got None."
                )
            if not isinstance(msg.cmd, str):
                raise InvalidPipeConnectionMessage(
                    f"PipeConnectionIO.recv_message: "
                    f"Expecting msg.cmd to be a str but got {type(msg.cmd)}"
                )
            if msg.cmd == PIPE_CONN_MSG_CMD_DATA_FINAL:
                self._eof = True
            if msg.data is not None and isinstance(msg.data, (bytes, bytearray)):
                self._num_bytes += len(msg.data)
                if _is_very_verbose_logging():
                    logging.debug(
                        f"PipeConnectionIO.recv_message: received: fileno={self._cached_fileno} cmd={msg.cmd} size={len(msg.data)} conv_total={self._num_bytes}"
                    )
            else:
                if _is_very_verbose_logging():
                    logging.debug(
                        f"PipeConnectionIO.recv_message: received: fileno={self._cached_fileno} cmd={msg.cmd}: data as bytes not present."
                    )
            return msg
        except EOFError:
            # Do not log EOFError at this point as caller
            # may not deem it to be an error.
            raise
        except Exception as ex:
            logging.error(
                f"PipeConnectionIO.recv_message: "
                f"fileno={self._cached_fileno} "
                f"Exception: {exc_to_string(ex)}"
            )
            raise

    def _write(self, cmd, buf) -> int:
        if not self.is_write:
            raise NotImplementedError(
                f"PipeConnectionIO.write: this is not a writeable side of the pipe."
            )
        if _is_very_verbose_logging():
            logging.debug(
                f"PipeConnectionIO.write: fileno={self._cached_fileno} num_bytes={len(buf)}."
            )
        msg = PipeConnectionMessage(cmd=cmd, data=buf)
        self.send_message(msg)
        return len(buf)

    def _validate_write_buf(self, buf):
        if buf is None:
            raise InvalidFunctionArgument(
                f"PipeConnectionIO.write: buf cannot be None."
            )
        if not isinstance(buf, (bytes, bytearray)):
            raise InvalidFunctionArgument(
                f"PipeConnectionIO.write: buf must be bytes or bytearray."
            )

    def write_eof(self, buf) -> int:
        if self.eof:
            raise PipeConnectionAlreadyEof(
                f"PipeConnectionIO.write_eof: already eof."
            )
        if _is_very_verbose_logging():
            logging.debug(
                f"PipeConnectionIO.write_eof: fileno={self._cached_fileno} writing EOF."
            )
        self._validate_write_buf(buf=buf)
        return self._write(PIPE_CONN_MSG_CMD_DATA_FINAL, buf)

    def write(self, buf) -> int:
        self._validate_write_buf(buf=buf)
        if len(buf) == 0:
            # Disallow writing of zero bytes until,
            # optionally, the last write which
            # indicates EOF. Some stream writers
            # expect writing zero to be a NOP.
            if _is_very_verbose_logging():
                logging.debug(
                    f"PipeConnectionIO.write: fileno={self._cached_fileno} Skipping zero-byte write."
                )
            return 0
        return self._write(PIPE_CONN_MSG_CMD_DATA, buf)

    def read(self, size: int = None) -> bytes:
        if self.is_write:
            raise NotImplementedError()
        if size is not None:
            raise InvalidPipeConnectionMessage(
                f"PipeConnectionIO.read: "
                f"Sender determines size, "
                f"cannot read with size specifications."
            )
        if self.eof:
            return bytes()
        try:
            msg = self.recv_message()
            if msg is None:
                raise InvalidPipeConnectionMessage(
                    f"PipeConnectionIO.read: NoneType message is unxpected."
                )
            if not isinstance(msg.cmd, str):
                raise InvalidPipeConnectionMessage(
                    f"PipeConnectionIO.read: msg.cmd must be str."
                )
            if msg.cmd not in PIPE_CONN_MSG_DATA_CMDS:
                raise InvalidPipeConnectionMessage(
                    f"PipeConnectionIO.read: "
                    f"Expecting one of '{PIPE_CONN_MSG_DATA_CMDS}' but got '{msg.cmd}'"
                )
            if not isinstance(msg.data, (bytes, bytearray)):
                raise InvalidPipeConnectionMessage(
                    f"PipeConnectionIO.read: "
                    f"Expecting msg.data to be bytes or bytearray but got {type(msg.data)}"
                )
            return msg.data
        except EOFError:
            if _is_very_verbose_logging():
                logging.debug(
                    f"PipeConnectionIO.read: fileno={self._cached_fileno} EOFError."
                )
            # Sender closes while we wait.
            return bytes()
        except Exception as ex:
            logging.error(
                f"PipeConnectionIO.read: fileno={self._cached_fileno} "
                f"Exception: {exc_to_string(ex)}"
            )
            raise

    def close(self) -> None:
        if _is_very_verbose_logging():
            logging.debug(
                f"PipeConnectionIO.close: fileno={self._cached_fileno}."
            )
            self.c.close()

    @property
    def closed(self) -> bool:
        return self.c.closed

    def seekable(self) -> bool:
        return False

    def seek(self, __offset: int, __whence: int = ...) -> int:
        raise NotImplementedError()

def wait_not_pending(fut: Future, timeout_secs: int = None):
    """Wait for ProcessPoolExecutor-submitted work to leave
    the PENDING state. Currently concurrent.futures provides
    no wait to wait for non-PENDING state, much less access
    that state specifically. We infer by looking for running
    or done at interval. Waiting for non-pending is important
    for sharing Pipe Connection ends, where this parent process
    wishes to close both ends which it does not need, or want
    to have remaining open.
    """
    s = time.perf_counter()
    while not fut.done() and not fut.running():
        e = time.perf_counter()
        if timeout_secs is not None:
            wait_secs = e - s
            if wait_secs >= timeout_secs:
                return False
        time.sleep(0.100)
    return True


class PipelineWorkItem:

    def __init__(
        self,
        user_obj: object = None,
        auto_copy_attr: bool=True,
        **kwargs,
    ) -> None:
        """Create a pipeline work item.

        user_obj is a caller object that must be pickle'able and
        is always picked to/from subprocesses back to this instance.

        If auto_copy_attr is True (default), copy all attributes
        not specified OUR_ATTRIBUTES to this instance after they
        are pickle'ed back from subprocesses. Again, these must
        be pickle'able.

        kwargs is anything else you want passed to all stages. It
        is recommended you avoid kwargs and use members of this
        instance.
        """
        #
        # IMPORTANT: Update OUR_ATTRIBUTES (above) if needed.
        #
        self._cur_stage = 0
        self.user_obj = user_obj
        self.user_kwargs = kwargs
        self.exceptions: list[Exception] = None
        self.pipe_conn: Connection = None
        self._auto_copy_attr = auto_copy_attr

    #
    # Update this if you add/remove or change names of
    # attributes that should not be auto-copy'ed.
    #
    OUR_ATTRIBUTES = [
        '_cur_stage',
        'user_obj',
        'user_kwargs',
        'exceptions',
        'pipe_conn',
        '_auto_copy_attr',
    ]

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: next_stage={self._cur_stage} user_obj={self.user_obj} exceps={self.exceptions}"
    @property
    def auto_copy_attr(self):
        return self._auto_copy_attr
    @auto_copy_attr.setter
    def auto_copy_attr(self, value):
        self._auto_copy_attr = value
    @property
    def is_failed(self):
        has_exceptions = (
            self.exceptions is not None
            and len(self.exceptions) > 0
        )
        return has_exceptions
    def increment_stage(self):
        self._cur_stage += 1
    @property
    def cur_stage(self):
        """Current stage which is usually the next stage to
        actually run, where the number increments after
        submitting the work.
        """
        return self._cur_stage
    @cur_stage.setter
    def cur_stage(self, value):
        self._cur_stage = value
    def append_exception(self, ex: Exception):
        if self.exceptions is None:
            self.exceptions = list[Exception]()
        self.exceptions.append(ex)
    def stage_complete(
        self,
        stage_num: int, # pylint: disable=unused-argument
        wi: 'PipelineWorkItem', # pylint: disable=unused-argument
        ex: Exception,
    ):
        """If ex is None, wi is the PipelineWorkItem from the stage's
        Future result. If ex is not None, wi is this instance for use
        as needed. The stage_num is the stage number that completed.
        Overrides should either call this method via super() or provide
        equal functionality to capture any error information. Beyond
        that, use wi to capture any info from a successful result as
        desired.
        """
        if ex is not None:
            self.append_exception(ex)
        if wi.is_failed:
            if self.exceptions is None:
                self.exceptions = list[Exception]()
            self.exceptions.extend(wi.exceptions)
        self.user_obj = wi.user_obj # Always copied.
        if self._auto_copy_attr:
            # By default, copy all of user's additions.
            # User can disable as desired.
            for k, v in wi.__dict__.items():
                if k not in PipelineWorkItem.OUR_ATTRIBUTES:
                    self.__dict__[k] = v

@dataclass(eq=True, frozen=True)
class _WorkItemStageRunCtx:
    cur_stage: int
    fut: Future
    wi: PipelineWorkItem
    def __str__(self) -> str:
        return f"cur_stage={self.cur_stage} wi={str(self.wi)} fut={str(self.fut)}"

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

    @property
    @abstractmethod
    def is_subprocess(self):
        raise NotImplementedError(
            f"is_subprocess is not implemented. "
            f"You probably want to use either "
            f"SubprocessPipelineStage or ThreadPipelineStage"
        )

    @property
    def is_pipe_with_next_stage(self):
        return False

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


class SubprocessPipelineStage(PipelineStage):
    @property
    def is_subprocess(self):
        return True


class ThreadPipelineStage(PipelineStage):
    @property
    def is_subprocess(self):
        return False

class MultiprocessingPipeline:
    def __init__(
        self,
        stages: list[PipelineStage]=None,
        max_simultaneous_work_items=None,
        name="unnamed",
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
        self._max_simultaneous_work_items = max_simultaneous_work_items
        self._is_shutdown = False  # Accessed by parent process only.
        self._wi_to_wifut = {}
        self._wi_to_fut_cond = multiprocessing.Condition()
        self._thread_exec = ThreadPoolExecutor(thread_name_prefix=f"MpPipeline-{name}")
        self._pl_worker_future = None
        self._input_queue_lock = multiprocessing.Lock()
        self._input_queue_fut: Future = None
        self._pl_input_queue = queue.Queue()  # Accessed in parent only.
        max_workers_each = None
        if self._max_simultaneous_work_items:
            max_workers_each = int(self._max_simultaneous_work_items + 2)
        self._process_exec = ProcessPoolExecutor(
            max_workers=max_workers_each,
            initializer=process_initfunc,
            initargs=process_initargs,
        )
        self._process_exec2 = ProcessPoolExecutor(
            max_workers=max_workers_each,
            initializer=process_initfunc,
            initargs=process_initargs,
        )
        # Given Future, find work item.
        self._plfut_to_wi = dict[Future, PipelineWorkItem]()
        # Given work item, find contexts for running work, if any.
        self._running_wi_contexts = dict[PipelineWorkItem, list[_WorkItemStageRunCtx]]()
        self._fut_to_pipe_conn = dict[Future, Connection]()
        self.was_graceful_shutdown = False
        self.anomalies = list[Anomaly]()

    def add_stage(self, stage: PipelineStage):
        self._stages.append(stage)

    @property
    def num_stages(self) -> int:
        return len(self._stages)

    def _start(self):
        if self._is_shutdown:
            raise InvalidFunctionArgument(
                f"QueuedSubprocessPipeline has already been started and stopped."
            )
        if self._pl_worker_future is not None:
            return
        self._pl_worker_future = self._thread_exec.submit(
            MultiprocessingPipeline._pl_worker, self
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
        wi: PipelineWorkItem
        for wi, wifut in self._wi_to_wifut.items():
            if wifut.done():
                continue
            wi.append_exception(ex)
            wifut.set_exception(ex)

    def _get_running_wi_count(
        self
    ):
        return len(self._running_wi_contexts)

    def _is_wi_still_running(
        self,
        wi: PipelineWorkItem,
    ):
        wi_contexts = self._running_wi_contexts.get(wi)
        if wi_contexts is None:
            return False
        return len(wi_contexts) > 0

    def _track_running_pipeline_work(
        self,
        cur_stage: int,
        fut: Future,
        wi: PipelineWorkItem,
    ):
        """Track a work item that is running within a stage.
        Currently this is most often one per work item, but
        can be two for dual-stage pipe connection case.
        The _get_completed_work_item_info untracks what
        this tracks.
        """
        if self._plfut_to_wi.get(fut) is not None:
            raise InvalidStateError(
                f"Expected _plfut_to_wi not to already have Future."
            )
        self._plfut_to_wi[fut] = wi
        if self._running_wi_contexts.get(wi) is None:
            self._running_wi_contexts[wi] = list[_WorkItemStageRunCtx]()
        self._running_wi_contexts[wi].append(
            _WorkItemStageRunCtx(
                cur_stage=cur_stage,
                fut=fut,
                wi=wi,
            )
        )

    def _get_completed_work_item_info(
        self,
        fut: Future,
    ) -> tuple[PipelineWorkItem, _WorkItemStageRunCtx]:
        """Given a Future, untrack and return its information.
        This method untracks what _track_running_pipeline_work
        tracks.
        """
        #
        # Find/remove the Future-to-work item tracking.
        #
        wi = self._plfut_to_wi.get(fut)
        if wi is not None:
            del self._plfut_to_wi[fut]

        #
        # Given the work item, find the contexts for each
        # running stage (often just 1, could be 2 in dual
        # stage pipe conn case).
        #
        wi_contexts = self._running_wi_contexts.get(wi)
        if wi_contexts is None:
            raise InvalidStateError(
                f"Unexpected, found work item from the Future "
                f"but not its _WorkItemStageRunCtx"
            )

        #
        # Remove the context for the completed portion of work.
        #
        c = None
        for c in list(wi_contexts):
            if c.fut == fut:
                wi_contexts.remove(c)
                break
        if len(wi_contexts) == 0:
            del self._running_wi_contexts[wi]
        if c is None:
            raise InvalidStateError(
                f"Unexpected, found work item from the Future, "
                f"and its context set, but not its specific "
                f" _WorkItemStageRunCtx instance."
            )

        return (wi, c,)

    def _get_queued_wi(
        self
    ):
        """Returns a tuple (wi, is_shutdown), where wi will
        be a work item if there's work that should run, else
        it will be None. If is_shutdown==True, caller should
        exit.
        """
        with self._input_queue_lock:
            if self._pl_input_queue.qsize() == 0:
                return (None, False)
            try:
                wi = self._pl_input_queue.get()
                return (wi, wi is None)
            except queue.Empty as ex:
                self.anomalies.append(
                    Anomaly(
                        kind=ANOMALY_KIND_EXCEPTION,
                        exception=ex,
                        message="Unexpected Empty on _pl_input_queue.get()"
                    )
                )
                return (None, None, False,)

    def _handle_completed_fut(
        self,
        done_fut: Future,
    ) -> tuple[PipelineWorkItem, _WorkItemStageRunCtx, bool]:
        """Processes done_fut, possibly returning a work item.
        Returns a tuple (wi, is_shutdown), where wi is the
        work item and is_shutdown is True if caller should exit.

        The work item is either already runing work which just
        completed a stage, or new work from the input queue.
        """
        wi: PipelineWorkItem = None

        if done_fut in self._plfut_to_wi:
            #
            # Completed future pertains to already running work.
            # Update the related stage with the results. If there
            # are parallel stages for the same work item, they are
            # completed separately from this call.
            #
            self._log_state(ctx_str="Future completion", futs_of_interest=set([done_fut]))
            wi, ctx = self._get_completed_work_item_info(fut=done_fut)
            if done_fut.exception() is not None:
                #
                # Some error occurred.
                #
                wi.stage_complete(
                    stage_num=ctx.cur_stage,
                    wi=wi,
                    ex=done_fut.exception(),
                )
            else:
                #
                # A successful result.
                #
                wi_from_sp: PipelineWorkItem = done_fut.result()
                if not isinstance(wi_from_sp, PipelineWorkItem):
                    ex = PipelineResultIsNotPipelineWorkItem(
                        f"The pipeline stage was successful but it returned "
                        f"something other than a PipelineWorkItem."
                    )
                    #
                    # Error: caller did not return a work item.
                    #
                    wi.stage_complete(
                        stage_num=ctx.cur_stage,
                        wi=wi,
                        ex=ex,
                    )
                else:
                    #
                    # Stage successful for work item.
                    #
                    wi.stage_complete(
                        stage_num=ctx.cur_stage,
                        wi=wi_from_sp,
                        ex=None,
                    )
            return (wi, False)

        #
        # Future is for input queue.
        #
        if done_fut == self._input_queue_fut:
            return self._get_queued_wi()

        #
        # Future is unknown.
        #
        msg = (
            f"Expected Future for pending pipeline activity or input queue, "
            f"but the Future matched neither. {str(done_fut)}"
        )
        self.anomalies.append(
            Anomaly(
                kind=ANOMALY_KIND_EXCEPTION,
                exception=InvalidStateError(msg),
                message=msg
            )
        )
        return self._get_queued_wi()

    def _cleanup_pipe_connections(self, done_fut: Future):
        conn = self._fut_to_pipe_conn.get(done_fut)
        if conn is not None:
            conn.close()
            del self._fut_to_pipe_conn[done_fut]

    def _handle_stages_for_wi(
        self,
        wi: PipelineWorkItem
    ):
        if wi.cur_stage < 0 or wi.cur_stage > self.num_stages:
            wi.append_exception(InvalidStateError(
                f"Invalid pipeline stage next_stage={wi.cur_stage}"
            ))
            wi.cur_stage = self.num_stages
            self._set_wi_to_finished(wi)
            return

        #
        # Advance to next stage, submit work item.
        #
        while wi.cur_stage < self.num_stages:
            next_stage = self._stages[wi.cur_stage]
            if next_stage.is_pipe_with_next_stage:
                if self._try_submit_to_dual_stage_with_pipe(wi=wi):
                    # Work item is now running on two stages w/pipe.
                    break
            elif self._try_submit_to_stage(wi=wi):
                # Work item is now running on one stage.
                break
            if wi.is_failed:
                # Failure occurred trying to submit.
                break
            # Work item was not submitted, not failed.
            # Ask next stage if it wants the work item.
            wi.increment_stage()
        if (
            not self._is_wi_still_running(wi=wi)
            and wi.cur_stage >= self.num_stages
        ):
            self._set_wi_to_finished(wi)


    def _pl_worker(self):
        try:
            is_shutdown: bool = False
            while not is_shutdown:

                #
                # Check for new work.
                #
                wi, is_shutdown = self._get_queued_wi()
                if is_shutdown:
                    break

                if wi is not None:
                    #
                    # New work available.
                    #
                    wi_needing_attention = set([wi])
                else:
                    #
                    # Wait on all pending work plus
                    # the new work input queue.
                    #
                    all_futs = set(self._plfut_to_wi)
                    self._renew_input_queue_future()
                    all_futs.add(self._input_queue_fut)
                    done_futs, _ = concurrent.futures.wait(
                        fs=all_futs,
                        return_when=FIRST_COMPLETED
                    )

                    #
                    # Something completed, gather list.
                    #
                    wi_needing_attention = set()
                    for done_fut in done_futs:
                        self._cleanup_pipe_connections(done_fut=done_fut)
                        wi, is_sd = self._handle_completed_fut(done_fut=done_fut)
                        is_shutdown = is_shutdown or is_sd
                        if wi is not None:
                            wi_needing_attention.add(wi)
                    if is_shutdown:
                        break

                #
                # Check completed results...
                #
                for wi in wi_needing_attention:

                    is_wi_still_running = self._is_wi_still_running(wi=wi)
                    if is_wi_still_running:
                        # Possible states:
                        #   * Two stages running, one just succeeded.
                        #   * Two stages running, one just failed.
                        # In either case, either the earlier or later stage is
                        # still running. Even if this is the later stage, the
                        # pipeline waits until the "paired earlier" stage completes.
                        # When a stage completes and is_wi_still_running is False,
                        # that is the time run the next wi.cur_stage stage.
                        # Wait until the remaining stage completes.
                        continue

                    if wi.is_failed:
                        # Failed and nothing else running for work item.
                        self._set_wi_to_finished(wi)
                        continue

                    self._handle_stages_for_wi(wi=wi)
        except Exception as ex:
            self._fail_all_pending(ex)
            raise
        self.was_graceful_shutdown = True

    def _submit_to_stage(
        self,
        stage: PipelineStage,
        wi: PipelineWorkItem,
        pipe_conn: Connection = None,
        use_second_pool: bool = False,
    ) -> Future:

        # Copy so work item state for submission.
        stage_wi_copy = copy.copy(wi)
        stage_wi_copy.pipe_conn = pipe_conn

        #
        # Submit the work item to the stage.
        #
        kwargs = stage.stage_kwargs
        if stage_wi_copy.user_kwargs is not None:
            kwargs = kwargs | stage_wi_copy.user_kwargs
        if stage.is_subprocess:
            if not use_second_pool:
                fut = self._process_exec.submit(
                    stage.perform_stage_work,
                    stage_wi_copy,
                    **kwargs
                )
            else:
                fut = self._process_exec2.submit(
                    stage.perform_stage_work,
                    stage_wi_copy,
                    **kwargs
                )
        else:
            fut = self._thread_exec.submit(
                stage.perform_stage_work,
                stage_wi_copy,
                **kwargs
            )

        #
        # Track the submitted work item.
        #
        self._track_running_pipeline_work(
            cur_stage=wi.cur_stage,
            fut=fut,
            wi=wi,
        )
        return fut

    def _is_stage_for_work_item(
        self,
        wi: PipelineWorkItem,
        stage_num: int = None,
    ) -> bool:
        """Returns True if next stage wants work item, else False.
        """
        if stage_num is None:
            stage_num = wi.cur_stage
        next_stage = self._stages[stage_num]
        try:
            # Ask stage if there's interest in this work item.
            return next_stage.is_for_stage(wi)
        except Exception as ex:
            # Unexpected failure, move past end of last stage
            # to trigger failure completion by caller.
            wi.append_exception(ex)
            return False

    def _try_submit_to_stage(
        self,
        wi: PipelineWorkItem
    ) -> bool:
        if not self._is_stage_for_work_item(wi=wi):
            if wi.is_failed:
                wi.cur_stage = self.num_stages
            return False
        fut = self._submit_to_stage(
            stage=self._stages[wi.cur_stage],
            wi=wi
        )
        self._log_state(ctx_str="single stage submission", futs_of_interest=set([fut]))
        wi.increment_stage()
        return True

    def _try_submit_to_dual_stage_with_pipe(
        self,
        wi: PipelineWorkItem,
    ) -> bool:
        """Some stages request to run the work item in two stages
        at once, the current and next stage, with a pipe to send
        data from current to next stage.
        """
        #
        # Last stage cannot request dual stage run.
        #
        if wi.cur_stage == self.num_stages - 1:
            raise PipelineLastStageError(
                f"Last stage of pipeline cannot request pipe, there is no next stage."
            )

        #
        # Current and next stage must approve.
        #
        if not self._is_stage_for_work_item(wi=wi, stage_num=wi.cur_stage):
            if wi.is_failed:
                wi.cur_stage = self.num_stages
            return False
        if not self._is_stage_for_work_item(wi=wi, stage_num=wi.cur_stage + 1):
            if wi.is_failed:
                wi.cur_stage = self.num_stages
            return False

        #
        # Create the pipe connections.
        #
        conn_w: Connection = None
        conn_r: Connection = None
        fut_w: Future = None # current stage
        fut_r: Future = None # next stage if current stage requests pipe.
        conn_r, conn_w = multiprocessing.Pipe(duplex=False)

        #
        # Submit work item to writer stage.
        #
        next_stage = self._stages[wi.cur_stage]
        fut_w = self._submit_to_stage(
            stage=next_stage,
            wi=wi,
            pipe_conn=conn_w
        )

        #
        # Submit work item to reader stage.
        #
        wi.increment_stage()
        next_stage = self._stages[wi.cur_stage]
        fut_r = self._submit_to_stage(
            stage=next_stage,
            wi=wi,
            pipe_conn=conn_r
        )
        self._log_state(ctx_str="dual stage submission", futs_of_interest=set([fut_w, fut_r]))

        wi.increment_stage()

        self._fut_to_pipe_conn[fut_w] = conn_w
        self._fut_to_pipe_conn[fut_r] = conn_r
        return True

    def _set_wi_to_finished(
        self,
        wi: PipelineWorkItem,
    ):
        fut: Future
        if self._is_wi_still_running(wi=wi):
            self._log_state(
                ctx_str="_set_wi_to_finished: wi still running",
                only_of_interest=False
            )
            raise InvalidStateError(
                f"Work item has ongoing work being tracked."
            )
        with self._wi_to_fut_cond:
            fut = self._wi_to_wifut.get(wi)
            if fut is None:
                raise InvalidStateError(
                    f"Cannot find Future for work item."
                )
            del self._wi_to_wifut[wi]
            if _is_very_verbose_logging():
                self._log_state(
                    ctx_str="fully completed user future",
                    futs_of_interest=set([fut]),
                    only_of_interest=False,
                )
            self._wi_to_fut_cond.notify_all()
            fut.set_result(wi)

    def _renew_input_queue_future(self):
        with self._input_queue_lock:
            self._input_queue_fut = Future()
            qsize = self._pl_input_queue.qsize()
            if qsize > 0:
                self._input_queue_fut.set_result(qsize)

    def _internal_submit(
        self,
        work_item: PipelineWorkItem,
    ) -> Future:

        self._start()

        # Track until all stages complete for work item.
        wi_fut = Future()
        self._wi_to_wifut[work_item] = wi_fut

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
        return wi_fut

    def _log_state(self, ctx_str=None, futs_of_interest: set[Future]=None, only_of_interest: bool=True):
        if not _is_very_verbose_logging():
            return
        if futs_of_interest is None:
            futs_of_interest = set()
        if ctx_str is not None:
            logging.debug(ctx_str)

        header = False
        for wi, wifut in self._wi_to_wifut.items():
            marker = ""
            if wifut in futs_of_interest:
                marker = " <---"
            if not only_of_interest or wifut in futs_of_interest:
                if not header:
                    logging.debug(f"  top-level of user:")
                    header = True
                logging.debug(f"    fut={str(wifut)} {str(wi)}{marker}")

        header = False
        for wi, plctx_list in self._running_wi_contexts.items():
            for plctx in plctx_list:
                marker = ""
                if plctx.fut in futs_of_interest:
                    marker = " <---"
                if not only_of_interest or plctx.fut in futs_of_interest:
                    if not header:
                        logging.debug(f"  pipeline stage work:")
                        logging.debug(f"    {str(wi)}")
                        header = True
                    logging.debug(f"      {str(plctx)}{marker}")

    def submit(
        self,
        work_item: PipelineWorkItem,
    ) -> Future:
        if work_item is None:
            raise InvalidFunctionArgument(
                f"work_item must be a PipelineWorkItem."
            )
        if self._wi_to_wifut.get(work_item) is not None:
            raise InvalidFunctionArgument(
                f"work_item is already in the pipeline."
            )
        return self._internal_submit(
            work_item=work_item,
        )
