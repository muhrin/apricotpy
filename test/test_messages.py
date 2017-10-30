import apricotpy
import functools
from . import utils


class TestFuture(utils.TestCaseWithLoop):
    def test_simple_msg(self):
        received = []
        got_message = utils.get_message_capture_fn(received)

        # Create a message to send
        msg = {
            'subject': 'test subject',
            'body': 'test body',
            'sender_id': 'test sender',
            'recipient': None
        }
        self.loop.messages().add_listener(got_message, subject_filter=msg['subject'])
        self.loop.messages().send(**msg)
        self.loop.tick()
        self.assertTrue(received)
        self.assertEqual(received[0], msg)

    def test_wildcard_sender(self):
        received = []
        got_message = utils.get_message_capture_fn(received)

        # Create a messages to send
        msgs = [
            {
                'subject': 'test subject',
                'body': 'test body',
                'sender_id': 'test sender 1',
                'recipient': None
            },
            {
                'subject': 'test subject',
                'body': 'test body',
                'sender_id': 'test sender 2',
                'recipient': None
            },
        ]

        # Try the two types of wildcard
        for wildcard in ['*', '#']:
            self.loop.messages().add_listener(
                got_message, sender_filter='test sender {}'.format(wildcard))
            for msg in msgs:
                self.loop.messages().send(**msg)
            self.loop.tick()
            self.assertTrue(len(received), len(msgs))
            for i in range(len(msgs)):
                self.assertEqual(received[i], msgs[i])

    def test_wildcard_subject(self):
        received = []
        got_message = utils.get_message_capture_fn(received)

        # Create a messages to send
        msgs = [
            {
                'subject': 'test subject 1',
                'body': 'test body',
                'sender_id': 'test sender',
                'recipient': None
            },
            {
                'subject': 'test subject 20',
                'body': 'test body',
                'sender_id': 'test sender',
                'recipient': None
            },
        ]
        # Try the two types of wildcard
        for wildcard in ['*', '#']:
            self.loop.messages().add_listener(
                got_message, sender_filter='test subject {}'.format(wildcard))
            for msg in msgs:
                self.loop.messages().send(**msg)
            self.loop.tick()
            self.assertTrue(len(received), len(msgs))
            for i in range(len(msgs)):
                self.assertEqual(received[i], msgs[i])

