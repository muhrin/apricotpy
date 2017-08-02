import apricotpy
from . import utils


class DummyObject(apricotpy.LoopObject):
    pass


class AwaitableObject(apricotpy.AwaitableMixin, apricotpy.LoopObject):
    pass


class TestLoopObject(utils.TestCaseWithLoop):
    def test_messages(self):
        messages = []

        def got_message(loop, subject, body, sender):
            messages.append(subject)

        self.loop.messages().add_listener(got_message, "loop.object.*.*")

        # Create and remove
        obj = self.loop.create(DummyObject)
        self.loop.run_until_complete(self.loop.remove(obj))

        for evt in ['created', 'inserting', 'inserted', 'removed']:
            self.assertIn('loop.object.{}.{}'.format(obj.uuid, evt), messages)


class TestAwaitableLoopObject(utils.TestCaseWithLoop):
    def test_result(self):
        result = "I'm walkin 'ere!"

        awaitable = ~self.loop.create_inserted(AwaitableObject)

        awaitable.set_result(result)
        self.assertEqual(awaitable.result(), result)

    def test_cancel(self):
        awaitable = ~self.loop.create_inserted(AwaitableObject)

        self.loop.call_soon(awaitable.cancel)
        with self.assertRaises(apricotpy.CancelledError):
            self.loop.run_until_complete(awaitable)
