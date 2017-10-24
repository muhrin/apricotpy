import apricotpy
import unittest
import functools


class TestCaseWithLoop(unittest.TestCase):
    def setUp(self):
        super(TestCaseWithLoop, self).setUp()
        self.loop = apricotpy.BaseEventLoop()
        apricotpy.set_event_loop(self.loop)

    def tearDown(self):
        super(TestCaseWithLoop, self).tearDown()
        apricotpy.set_event_loop(None)
        self.loop.close()
        self.loop = None


def get_message_capture_fn(capture_list):
    return functools.partial(get_message, capture_list)


def get_message(receive_list, loop, subject, recipient, body, sender_id):
    receive_list.append({
        'subject': subject,
        'recipient': recipient,
        'body': body,
        'sender_id': sender_id
    })
