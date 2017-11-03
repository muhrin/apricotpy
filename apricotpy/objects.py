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
    # Class defaults
    _listening_for_messages = False

    def __init__(self, loop=None):
        super(LoopObject, self).__init__()

        if loop is None:
            self._loop = events.get_event_loop()
        else:
            self._loop = loop
        self._uuid = uuid.uuid4()
        self._loop_callback = None
        self.enable_message_listening()

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

    def send_message(self, subject, to=None, body=None):
        """
        Send a message from this object.  The UUID will automatically be used
        as the sender id.
        
        If no recipient is specified (to=None) then the message will be broadcast
        to anyone listening.
        
        :param subject: The message subject
        :type subject: basestring
        :param to: The recipient of the message, can be None.
        :param body: The body of the message, can be None.
        """
        self.loop().messages().send(
            subject=subject,
            body=body,
            to=to,
            sender_id=self.uuid
        )

    def enable_message_listening(self):
        if not self._listening_for_messages:
            self.loop().messages().add_listener(
                self._message_received, recipient_id=self._uuid)
            self._listening_for_messages = True

    def disable_message_listening(self):
        if self._listening_for_messages:
            self.loop().messages().remove_listener(
                self._message_received)
            self._listening_for_messages = False

    def message_received(self, subject, body, sender_id):
        pass

    def _message_received(self, loop, subject, to=None, body=None, sender_id=None):
        self.message_received(subject, body, sender_id)


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
        self._future = futures.Future(loop=self.loop())

    def __invert__(self):
        return self._loop.run_until_complete(self)

    def done(self):
        return self._future.done()

    def result(self):
        return self._future.result()

    def exception(self):
        return self._future.exception()

    def cancelled(self):
        return self._future.cancelled()

    def add_done_callback(self, fn):
        return self._future.add_done_callback(fn)

    def remove_done_callback(self, fn):
        return self._future.remove_done_callback(fn)

    def cancel(self):
        return self._future.cancel()

    def set_result(self, result):
        self._future.set_result(result)

    def set_exception(self, exception):
        self._future.set_exception(exception)
