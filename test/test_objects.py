import apricotpy
from . import utils


class AwaitableObject(apricotpy.AwaitableMixin, apricotpy.LoopObject):
    pass


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
