import apricotpy
from . import utils


class AwaitableObject(apricotpy.AwaitableMixin, apricotpy.LoopObject):
    pass


class TestAwaitableLoopObject(utils.TestCaseWithLoop):
    def test_result(self):
        result = "I'm walkin 'ere!"

        awaitable = self.loop.run_until_complete(self.loop.create_inserted(AwaitableObject))

        awaitable.set_result(result)
        self.assertEqual(awaitable.result(), result)

    def test_removed_on_done(self):
        """Test that a done awaitable is also removed from the loop"""
        awaitable = self.loop.run_until_complete(self.loop.create_inserted(AwaitableObject))

        awaitable.set_result(None)
        self.loop.run_until_complete(awaitable)
        self.assertFalse(awaitable.in_loop())
        self.assertIsNone(awaitable.loop())
