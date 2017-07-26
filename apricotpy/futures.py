import abc
import concurrent.futures

__all__ = ['CancelledError', 'Future', 'get_future', 'InvalidStateError']

Error = concurrent.futures._base.Error
CancelledError = concurrent.futures.CancelledError


class InvalidStateError(Error):
    """The operation is not allowed in this state."""


_PENDING = 'PENDING'
_CANCELLED = 'CANCELLED'
_FINISHED = 'FINISHED'


class Awaitable(object):
    """
    An interface that defines an object that is awaitable e.g. a Future
    """
    __metaclass__ = abc.ABCMeta

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
    def cancel(self):
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
    def __init__(self, loop):
        self._loop = loop
        self._state = _PENDING
        self._result = None
        self._exception = None
        self._callbacks = []

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


def get_future(task_or_future):
    if isinstance(task_or_future, Future):
        return task_or_future
    else:
        return task_or_future.future()
