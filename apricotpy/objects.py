import abc
import uuid
from future.utils import with_metaclass

from . import events
from . import futures

__all__ = ['LoopObject',
           'TickingMixin',
           'TickingLoopObject',
           'AwaitableMixin']


class LoopObject(object):
    def __init__(self, loop=None):
        super(LoopObject, self).__init__()

        if loop is None:
            self._loop = events.get_event_loop()
        else:
            self._loop = loop
        self._uuid = uuid.uuid4()
        self._loop_callback = None

        self.send_message('created', body=self._uuid)

    @property
    def uuid(self):
        return self._uuid

    def loop(self):
        """
        Get the event loop, can be None.
        :return: The event loop
        :rtype: :class:`apricotpy.AbstractEventLoop`
        """
        return self._loop

    def in_loop(self):
        return self._loop is not None

    def send_message(self, subject, recipient=None, body=None):
        """
        Send a message from this object.  The UUID will automatically be used
        as the sender id. 
        """
        self.loop().messages().send(
            subject=subject,
            body=body,
            recipient=recipient,
            sender_id=self._get_message_identifier()
        )

    def enable_message_listening(self):
        self.loop().messages.add_listener(
            self.message_received,
            sender_filter=self._get_message_identifier()
        )

    def disable_message_listening(self):
        self.loop().messages.remove_listener(self.message_received)

    def message_received(self, subject, body=None, recipient=None, sender_id=None):
        pass

    def _get_message_identifier(self):
        return self.__class__.__name__ + '.' + str(self.uuid)


class TickingMixin(with_metaclass(abc.ABCMeta, object)):
    """
    A mixin that makes a LoopObject be 'ticked' each time around the event
    loop.  The user code should go in the `tick()` function.
    """

    def __init__(self, *args, **kwargs):
        super(TickingMixin, self).__init__(*args, **kwargs)
        self._callback_handle = self.loop().call_soon(self._tick)

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
        self._future = futures.Future(loop=kwargs.get('loop', None))

    def __invert__(self):
        return self._loop.run_until_complete(self)

    def done(self):
        return self._future.done()

    def result(self):
        return self._future.result()

    def set_result(self, result):
        self._future.set_result(result)

    def exception(self):
        return self._future.exception()

    def set_exception(self, exception):
        self._future.set_exception(exception)

    def cancel(self):
        self._future.cancel()

    def cancelled(self):
        return self._future.cancelled()

    def add_done_callback(self, fn):
        """
        Add a callback to be run when the future becomes done.

        :param fn: The callback function.
        """
        self._future.add_done_callback(fn)

    def remove_done_callback(self, fn):
        """
        Remove all the instances of the callback function from the call when done list.

        :return: The number of callback instances removed
        :rtype: int
        """
        self._future.remove_done_callback(fn)
