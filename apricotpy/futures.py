import abc
import concurrent.futures
import sys
import traceback

from future.utils import with_metaclass 

from . import events

__all__ = ['CancelledError', 'Awaitable', 'Future',
           'InvalidStateError', 'gather']

Error = concurrent.futures._base.Error
CancelledError = concurrent.futures.CancelledError


class InvalidStateError(Error):
    """The operation is not allowed in this state."""


_PENDING = 'PENDING'
_CANCELLED = 'CANCELLED'
_FINISHED = 'FINISHED'


class Awaitable(with_metaclass(abc.ABCMeta, object)):
    """
    An interface that defines an object that is awaitable e.g. a Future
    """

    @abc.abstractmethod
    def done(self):
        pass

    @abc.abstractmethod
    def result(self):
        pass

    @abc.abstractmethod
    def exception(self):
        pass

    @abc.abstractmethod
    def cancelled(self):
        pass

    @abc.abstractmethod
    def add_done_callback(self, fn):
        pass

    @abc.abstractmethod
    def remove_done_callback(self, fn):
        pass


class Future(Awaitable):
    # Class variables serving as defaults for instance variables.
    _state = _PENDING
    _result = None
    _exception = None
    _loop = None
    _source_traceback = None

    def __init__(self, loop=None):
        """Initialize the future.
        The optional event_loop argument allows explicitly setting the event
        loop object used by the future. If it's not provided, the future uses
        the default event loop.
        """
        if loop is None:
            self._loop = events.get_event_loop()
        else:
            self._loop = loop
        self._callbacks = []
        if self._loop.get_debug():
            self._source_traceback = traceback.extract_stack(sys._getframe(1))

    def __invert__(self):
        return self._loop.run_until_complete(self)

    def cancel(self):
        if self.done():
            return False

        self._state = _CANCELLED
        self._schedule_callbacks()
        return True

    def cancelled(self):
        return self._state is _CANCELLED

    def done(self):
        return self._state != _PENDING

    def result(self):
        if self.cancelled():
            raise CancelledError()
        elif self._state is not _FINISHED:
            raise InvalidStateError("The future has not completed yet")
        elif self._exception is not None:
            raise self._exception

        return self._result

    def set_result(self, result):
        if self.done():
            raise InvalidStateError("The future is already done")

        self._result = result
        self._state = _FINISHED
        self._schedule_callbacks()

    def set_exception(self, exception):
        if self.done():
            raise InvalidStateError("The future is already done")

        self._exception = exception
        self._state = _FINISHED
        self._schedule_callbacks()

    def exception(self):
        if self.cancelled():
            raise CancelledError()
        if self._state is not _FINISHED:
            raise InvalidStateError("Exception not set")

        return self._exception

    def add_done_callback(self, fn):
        """
        Add a callback to be run when the future becomes done.

        :param fn: The callback function.
        """
        if self.done():
            self._loop.call_soon(fn, self)
        else:
            self._callbacks.append(fn)

    def remove_done_callback(self, fn):
        """
        Remove all the instances of the callback function from the call when done list.

        :return: The number of callback instances removed
        :rtype: int
        """
        filtered_callbacks = [f for f in self._callbacks if f != fn]
        removed_count = len(self._callbacks) - len(filtered_callbacks)
        if removed_count:
            self._callbacks[:] = filtered_callbacks

        return removed_count

    def _schedule_callbacks(self):
        """
        Ask the event loop to call all callbacks.

        The callbacks are scheduled to be called as soon as possible.
        """
        callbacks = self._callbacks[:]
        if not callbacks:
            return

        self._callbacks[:] = []
        for callback in callbacks:
            self._loop.call_soon(callback, self)


def _gathering_future_template(future_type):
    class _GatheringFutureTemplate(future_type):
        def __init__(self, children, loop):
            super(_GatheringFutureTemplate, self).__init__(loop)
            self._children = tuple(children)
            self._n_done = 0

            for child in self._children:
                child.add_done_callback(self._child_done)

        def cancel(self):
            if self.done():
                return False

            ret = False
            for child in self._children:
                if child.cancel():
                    ret = True

            return ret

        def _child_done(self, future):
            if self.done():
                return

            try:
                if future.exception() is not None:
                    self.set_exception(future.exception())
                    return
            except CancelledError as e:
                self.set_exception(e)
                return

            self._n_done += 1
            if self._n_done == len(self._children):
                self._all_done()

        def _all_done(self):
            self.set_result(tuple(child.result() for child in self._children))

    return _GatheringFutureTemplate


_GatheringFuture = _gathering_future_template(Future)


def gather(awaitables, loop):
    """
    Gather multiple awaitables into a single :class:`Awaitable`

    :param awaitables: The awaitables to gather
    :param loop: The event loop
    :return: An awaitable representing all the awaitables
    :rtype: :class:`Awaitable`
    """
    if isinstance(awaitables, Awaitable):
        return awaitables

    return _GatheringFuture(awaitables, loop)
