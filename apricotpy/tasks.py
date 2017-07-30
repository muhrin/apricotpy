import logging
from abc import ABCMeta, abstractmethod
from collections import namedtuple

from . import objects
from . import futures

__all__ = ['Continue', 'Await', 'Task']

_LOGGER = logging.getLogger(__name__)


class _TaskDirective(object):
    pass


class Continue(_TaskDirective):
    def __init__(self, callback):
        self.callback = callback


class Await(_TaskDirective):
    def __init__(self, awaitable, callback):
        assert isinstance(awaitable, futures.Awaitable), \
            "awaitable must be of Awaitable type"
        self.awaitable = awaitable
        self.callback = callback


_NO_RESULT = ()


class Task(objects.AwaitableMixin, objects.LoopObject):
    __metaclass__ = ABCMeta

    Terminated = namedtuple("Terminated", ['result'])

    def __init__(self, loop):
        super(Task, self).__init__(loop)

        self._awaiting = None
        self._next_step = None
        self._awaiting_result = _NO_RESULT

        self._paused = False
        self._callback_handle = None

    def awaiting(self):
        """
        :return: The awaitable this task is awaiting, or None
        :rtype: :class:`apricotpy.Awaitable` or None
        """
        return self._awaiting

    def on_loop_inserted(self, loop):
        super(Task, self).on_loop_inserted(loop)
        if self._awaiting is not None:
            self._awaiting.add_done_callback(self._await_done)
        elif not self.done() and self.is_playing():
            self._schedule_step()

    def on_loop_removed(self):
        super(Task, self).on_loop_removed()
        if self._callback_handle is not None:
            self._callback_handle.cancel()
        if self._awaiting is not None:
            self._awaiting.remove_done_callback(self._await_done)

    def play(self):
        """
        Play the task if it was paused.
        """
        if self.done() or self.is_playing():
            return False

        self._paused = False
        self._schedule_step()

        return True

    def pause(self):
        """
        Pause a playing task.
        """
        if not self.is_playing():
            return True

        if self.done():
            return False

        # Could be None if we are awaiting something
        if self._callback_handle is not None:
            self._callback_handle.cancel()
            self._callback_handle = None

        self._paused = True

        return True

    def is_playing(self):
        return not self._paused

    def cancel(self):
        cancelled = super(Task, self).cancel()
        if cancelled and self.awaiting() is not None:
            self.awaiting().cancel()
            self._awaiting = None
        return cancelled

    @abstractmethod
    def execute(self):
        pass

    def _step(self):
        self._callback_handle = None

        args = []
        if self._next_step:
            fn = self._next_step
            if self._awaiting_result is not _NO_RESULT:
                args.append(self._awaiting_result)
        else:
            # First time
            fn = self.execute

        try:
            result = fn(*args)
            self._set_next_step(None)
        except BaseException as e:
            # This will also remove us from the loop
            self.set_exception(e)
        else:
            if isinstance(result, _TaskDirective):
                if isinstance(result, Continue):
                    self._set_next_step(result.callback)
                    self._schedule_step()

                if isinstance(result, Await):
                    self._set_next_step(result.callback)
                    self._awaiting = result.awaitable
                    self._awaiting.add_done_callback(self._await_done)
            else:
                # This will also remove us from the loop
                self.set_result(result)

    def _schedule_step(self):
        assert self._callback_handle is None, "Step already scheduled"
        self._callback_handle = self.loop().call_soon(self._step)

    def _set_next_step(self, fn):
        if fn is not None:
            try:
                assert fn.__self__ is self, "Next step function must be a member of this class"
            except AttributeError:
                raise AssertionError("Next step function must be a member of this class")

        self._next_step = fn

    def _await_done(self, awaitable):
        if self.done():
            return

        # We shouldn't hold on to a reference to the awaitable
        self._awaiting = None

        if awaitable.cancelled():
            self.cancel()
        elif awaitable.exception() is not None:
            self.set_exception(awaitable.exception())
        elif self._next_step is None:
            self.set_result(awaitable.result())
        else:
            self._awaiting_result = awaitable.result()
            self._schedule_step()
