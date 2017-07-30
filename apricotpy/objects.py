import abc
from uuid import uuid1

from . import futures

__all__ = ['LoopObject',
           'TickingMixin',
           'TickingLoopObject',
           'AwaitableMixin']


class LoopObject(object):
    def __init__(self, loop, uuid=None):
        super(LoopObject, self).__init__()

        if uuid is None:
            self._uuid = uuid1()
        else:
            self._uuid = uuid

        self._loop = None

    @property
    def uuid(self):
        return self._uuid

    def on_loop_inserted(self, loop):
        """
        Called when the object is inserted into the event loop.

        :param loop: The event loop
        :type loop: `apricotpy.AbstractEventLoop`
        """
        self._loop = loop

    def on_loop_removed(self):
        """
        Called when the object is removed from the event loop.
        """
        if self._loop is None:
            raise RuntimeError("Not in an event loop")

        self._loop = None

    def loop(self):
        """
        Get the event loop, can be None.
        :return: The event loop
        :rtype: :class:`apricotpy.AbstractEventLoop`
        """
        return self._loop

    def in_loop(self):
        return self._loop is not None

    def remove(self):
        return self.loop().remove(self)


class TickingMixin(object):
    """
    A mixin that makes a LoopObject be 'ticked' each time around the event
    loop.  The user code should go in the `tick()` function.
    """
    __metaclass__ = abc.ABCMeta

    def on_loop_inserted(self, loop):
        super(TickingMixin, self).on_loop_inserted(loop)
        self._callback_handle = loop.call_soon(self._tick)

    @abc.abstractmethod
    def tick(self):
        pass

    def pause(self):
        self._callback_handle.cancel()
        self._callback_handle = None

    def play(self):
        if self._callback_handle is None:
            self._callback_handle = self.loop().call_soon(self._tick)

    def _tick(self):
        self.tick()
        if self._callback_handle is not None:
            self._callback_handle = self.loop().call_soon(self._tick)


class TickingLoopObject(TickingMixin, LoopObject):
    """Convenience class that defines a ticking LoopObject"""
    pass


class AwaitableMixin(futures.Awaitable):
    def __init__(self, *args, **kwargs):
        assert isinstance(self, LoopObject), "Must be used with a loop object"
        super(AwaitableMixin, self).__init__(*args, **kwargs)
        self._future = futures._FutureBase()
        self._callbacks = []

    def __invert__(self):
        return self._loop.run_until_complete(self)

    def on_loop_inserted(self, loop):
        super(AwaitableMixin, self).on_loop_inserted(loop)
        if self.done():
            self._schedule_callbacks()

    def done(self):
        return self._future.done()

    def result(self):
        return self._future.result()

    def set_result(self, result):
        self._future.set_result(result)
        if self.in_loop():
            self._schedule_callbacks()
            self.loop().remove(self)

    def exception(self):
        return self._future.exception()

    def set_exception(self, exception):
        self._future.set_exception(exception)
        if self.in_loop():
            self._schedule_callbacks()
            self.loop().remove(self)

    def cancel(self):
        self._future.cancel()
        if self.in_loop():
            self._schedule_callbacks()
            self.loop().remove(self)

    def cancelled(self):
        return self._future.cancelled()

    def add_done_callback(self, fn):
        """
        Add a callback to be run when the future becomes done.

        :param fn: The callback function.
        """
        if self.in_loop() and self.done():
            self.loop().call_soon(fn, self)
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
            self.loop().call_soon(callback, self)

    def _check_inserted(self):
        assert self.loop() is not None, \
            "Awaitable has not been inserted into the loop yet"
