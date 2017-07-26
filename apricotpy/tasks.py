import logging
from abc import ABCMeta, abstractmethod
from collections import namedtuple

from . import objects

__all__ = ['Continue', 'Await', 'Task']

_LOGGER = logging.getLogger(__name__)


class _TaskDirective(object):
    pass


class Continue(_TaskDirective):
    def __init__(self, callback):
        self.callback = callback


class Await(_TaskDirective):
    def __init__(self, awaitable, callback):
        self.awaitable = awaitable
        self.callback = callback


_NO_RESULT = ()


class Task(objects.AwaitableMixin, objects.LoopObject):
    __metaclass__ = ABCMeta

    Terminated = namedtuple("Terminated", ['result'])

    def __init__(self, loop):
        super(Task, self).__init__(loop)

        self._directive = None
        self._awaiting = None
        self._callback = None
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
        if self.is_playing():
            self._schedule_next()

    def play(self):
        """
        Play the task if it was paused.
        """
        if self.done() or self.is_playing():
            return False

        self._paused = False
        self._schedule_next()

        return True

    def pause(self):
        """
        Pause a playing task.
        """
        if not self.is_playing():
            return True

        if self.done():
            return False

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

    def _start(self):
        self._callback_handle = None
        if self._paused:
            return

        try:
            result = self.execute()
        except BaseException as e:
            self.set_exception(e)
        else:
            self._proceed(result)

    def _continue(self, callback, last_result=_NO_RESULT):
        # Clear everything
        self._callback_handle = None
        self._directive = None
        self._awaiting_result = _NO_RESULT
        self._callback = None

        args = []
        if last_result is not _NO_RESULT:
            args.append(last_result)

        try:
            self._proceed(callback(*args))
        except BaseException as e:
            self.set_exception(e)

    def _proceed(self, result):
        if isinstance(result, _TaskDirective):
            if isinstance(result, Continue):
                self._directive = Continue.__name__
                self._callback = result.callback
                self._schedule_next()

            if isinstance(result, Await):
                self._directive = Await.__name__
                self._callback = result.callback
                self._awaiting = result.awaitable
                self._awaiting.add_done_callback(self._await_done)
        else:
            # This will also remove us from the loop
            self.set_result(result)

    def _schedule_next(self):
        assert self._callback_handle is None, "Callback handle is not None"

        if self._directive is Continue.__name__:
            self._callback_handle = self.loop().call_soon(self._continue, self._callback)
        elif self._directive is Await.__name__:
            if self._awaiting_result is not _NO_RESULT:
                self._callback_handle = self.loop().call_soon(self._continue, self._callback, self._awaiting_result)
        else:
            assert self._directive is None, "Unknown directive '{}'".format(self._directive)
            self._callback_handle = self.loop().call_soon(self._start)

    def _await_done(self, awaitable):
        if self.done():
            return

        # We shouldn't hold on to a reference to the awaitable
        self._awaiting = None

        if awaitable.cancelled():
            self.cancel()
        elif awaitable.exception() is not None:
            self.set_exception(awaitable.exception())
        elif self._directive is None:
            self.set_result(awaitable.result())
        else:
            self._awaiting_result = awaitable.result()
            self._schedule_next()
