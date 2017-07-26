import abc
from uuid import uuid1

from . import futures

__all__ = ['LoopObject', 'TickingMixin', 'AwaitableMixin']


class LoopObject(object):
    def __init__(self, loop, uuid=None):
        super(LoopObject, self).__init__()

        if uuid is None:
            self._uuid = uuid1()
        else:
            self._uuid = uuid

        self._loop = loop

    @property
    def uuid(self):
        return self._uuid

    def on_loop_inserted(self, loop):
        """
        Called when the object is inserted into the event loop.

        :param loop: The event loop
        :type loop: `apricotpy.AbstractEventLoop`
        """
        pass

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


class AwaitableMixin(futures.Awaitable):
    def __init__(self, *args, **kwargs):
        assert isinstance(self, LoopObject), "Must be used with a loop object"
        super(AwaitableMixin, self).__init__(*args, **kwargs)
        self._future = futures.Future(None)

    def on_loop_inserted(self, loop):
        super(AwaitableMixin, self).on_loop_inserted(loop)
        self._future._loop = loop

    def on_loop_removed(self):
        super(AwaitableMixin, self).on_loop_removed()
        self._future._loop = None

    def done(self):
        return self._future.done()

    def result(self):
        return self._future.result()

    def set_result(self, result):
        self._check_inserted()
        self._future.set_result(result)
        self.loop().remove(self)

    def exception(self):
        return self._future.exception()

    def set_exception(self, exception):
        self._check_inserted()
        self._future.set_exception(exception)
        self.loop().remove(self)

    def cancel(self):
        self._check_inserted()
        self._future.cancel()
        self.loop().remove(self)

    def cancelled(self):
        return self._future.cancelled()

    def add_done_callback(self, fn):
        return self._future.add_done_callback(fn)

    def remove_done_callback(self, fn):
        return self._future.remove_done_callback(fn)

    def _check_inserted(self):
        assert self._future._loop is not None, \
            "Awaitable has not been inserted into the loop yet"


class _GatheringFuture(futures.Future):
    def __init__(self, children, loop):
        super(_GatheringFuture, self).__init__(loop)
        self._children = children
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
        except futures.CancelledError as e:
            self.set_exception(e)
            return

        self._n_done += 1
        if self._n_done == len(self._children):
            self._all_done()

    def _all_done(self):
        self.set_result([child.result() for child in self._children])


def gather(tasks_or_futures, loop):
    if isinstance(tasks_or_futures, futures.Future):
        return tasks_or_futures

    futs = [futures.get_future(task_or_future) for task_or_future in tasks_or_futures]
    return _GatheringFuture(futs, loop)
