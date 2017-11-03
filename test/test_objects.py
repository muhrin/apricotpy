import apricotpy
from . import utils


class DummyObject(apricotpy.LoopObject):
    pass


class AwaitableObject(apricotpy.AwaitableMixin, apricotpy.LoopObject):
    pass


class TestLoopObject(utils.TestCaseWithLoop):
    def test_send_message(self):
        class Obj(apricotpy.LoopObject):
            def __init__(self, loop):
                super(Obj, self).__init__(loop=loop)
                self.send_message("greetings", body="'sup yo")

        messages = []
        got_message = utils.get_message_capture_fn(messages)

        self.loop.messages().add_listener(got_message, subject_filter='greetings')

        obj = self.loop.create(Obj)
        # Tick so the message gets sent out
        self.loop.tick()

        message = messages[0]
        self.assertEqual(message['subject'], "greetings")
        self.assertEqual(message['body'], "'sup yo")
        self.assertEqual(message['sender_id'], obj.uuid)


class TestAwaitableLoopObject(utils.TestCaseWithLoop):
    def test_result(self):
        result = "I'm walkin 'ere!"

        awaitable = self.loop.create(AwaitableObject)

        awaitable.set_result(result)
        self.assertEqual(awaitable.result(), result)

    def test_cancel(self):
        awaitable = AwaitableObject()

        self.loop.call_soon(awaitable.cancel)
        with self.assertRaises(apricotpy.CancelledError):
            self.loop.run_until_complete(awaitable)
