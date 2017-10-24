import abc
from collections import namedtuple
import threading
import re

from past.builtins import basestring

_WilcardEntry = namedtuple("_WildcardEntry", ['re', 'listeners'])


def _contains_wildcard(term):
    """
    Does the term contain one or more wildcard characters

    :param term: The event string
    :type term: basestring
    :return: True if it does, False otherwise
    """
    return term.find('*') != -1 or term.find('#') != -1


class Matcher(object):
    def __init__(self, term):
        self._term = term

    def __hash__(self):
        return self._term.__hash__()

    def __eq__(self, other):
        return self._term == other._term

    @abc.abstractmethod
    def match(self, query):
        pass


class ExactMatch(Matcher):
    def match(self, query):
        return query == self._term


class WildcardMatch(Matcher):
    def __init__(self, term):
        if not _contains_wildcard(term):
            ValueError("The term '{}' does not contain a wildcard character".format(term))
        super(WildcardMatch, self).__init__(term)
        regex = term.replace('.', '\.').replace('*', '.*').replace('#', '.+')
        self._regex = re.compile(regex)

    def match(self, query):
        return self._regex.match(query) is not None


def _create_matcher(term):
    if _contains_wildcard(term):
        return WildcardMatch(term)
    else:
        return ExactMatch(term)


class Mailman(object):
    """
    A class to send messages to listeners

    Messages send by this class:
    * mailman.listener_added.[subject]
    * mailman.listener_removed.[subject]

    where subject is the subject the listener is listening for
    """

    @staticmethod
    def contains_wildcard(event):
        """
        Does the event string contain a wildcard.

        :param event: The event string
        :type event: basestring
        :return: True if it does, False otherwise
        """
        return event.find('*') != -1 or event.find('#') != -1

    def __init__(self, loop):
        """

        :param loop: The event loop
        :type loop: :class:`apricotpy.AbstractEventLoop`
        """
        self.__loop = loop
        self._listeners = {}

    def add_listener(self, listener, subject_filter='*', sender_filter='*'):
        """
        Start listening to a particular event or a group of events.

        :param listener: The callback callable to call when the event happens
        :param subject_filter: A filter on the subhect
        :type subject_filter: basestring
        :param sender_filter: A filter on the sender
        """
        if subject_filter is None:
            raise ValueError("Invalid event '{}'".format(subject_filter))

        subject_matcher = _create_matcher(subject_filter)
        sender_matcher = _create_matcher(sender_filter)

        self._check_listener(listener)
        self._listeners.setdefault(
            (sender_matcher, subject_matcher), set()
        ).add(listener)

    def remove_listener(self, listener, subject_filter=None, sender_filter=None):
        """
        Stop listening for events.  If event is not specified it is assumed
        that the listener wants to stop listening to all events.

        :param listener: The listener that is currently listening
        :param subject_filter: (optional) subject to stop listening for
        :type subject_filter: basestring
        :param sender_filter: (optional) subject to stop listening for
        :type subject_filter: basestring
        """
        for matchers, listeners in self._listeners.items():
            if sender_filter is None:
                sender_match = True
            else:
                sender_match = matchers[0].match(sender_filter)
            if subject_filter is None:
                subject_match = True
            else:
                subject_match = matchers[1].match(subject_filter)
            if sender_match and subject_match:
                listeners.discard(listener)

    def clear_all_listeners(self):
        self._listeners.clear()

    def send(self, subject, body=None, recipient=None, sender_id=None):
        """
        Send a message

        :param subject: The message subject
        :type subject: basestring
        :param body: The body of the message
        :param recipient: The recipient of the message (None unspecified)
        :type recipient: basestring
        :param sender_id: An identifier for the sender
        :type sender_id: basestring
        """
        # These loops need to use copies because, e.g., the recipient may
        # add or remove listeners during the delivery
        for matchers, listeners in self._listeners.items():
            if recipient is None:
                recipient_match = True
            else:
                recipient_match = matchers[0].match(recipient)

            subject_match = matchers[1].match(subject)
            if recipient_match and subject_match:
                for listener in listeners:
                    self._deliver_msg(listener, subject, body, recipient, sender_id)

    def _deliver_msg(self, listener, subject, body, recipient, sender_id):
        """
        :param listener: The listener callable
        :param subject: The subject of the message
        :type subject: basestring
        :param body: The body of the message
        :param recipient: The targeted recipient of the message (could be None)
        :type recipient: basestring or None
        :param sender_id: An identifier for the sender
        :type sender_id: basestring
        :return: 
        """
        self.__loop.call_soon(listener, self.__loop, subject, recipient, body, sender_id)

    @staticmethod
    def _check_listener(listener):
        if not callable(listener):
            raise ValueError("Listener must be callable, got '{}".format(type(listener)))
            # Can do more sophisticated checks here, but it's a pain (to check both
            # classes that are callable having the right signature and plain functions)
