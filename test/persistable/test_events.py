import apricotpy.utils
from . import utils
import apricotpy.persistable as persistable

result = apricotpy.utils.SimpleNamespace


def callback():
    global result
    result.called = True


class TestCallback(utils.TestCaseWithLoop):
    def test_save_callback(self):
        global result

        result.called = False

        handle = self.loop.call_soon(callback)

        saved_state = persistable.Bundle(handle)
        handle.cancel()
        self.loop.tick()

        self.assertFalse(result.called)

        handle = saved_state.unbundle(self.loop)
        self.loop.tick()

        self.assertTrue(result)

    def test_cancel_callback(self):
        global result

        result.called = False

        handle = self.loop.call_soon(callback)
        handle.cancel()

        saved_state = persistable.Bundle(handle)
        self.loop.tick()

        self.assertFalse(result.called)

        handle = saved_state.unbundle(self.loop)
        self.loop.tick()

        self.assertFalse(result.called)

    def test_completed_callback(self):
        global result

        result.called = False

        handle = self.loop.call_soon(callback)
        self.loop.tick()

        self.assertTrue(result.called)
        saved_state = persistable.Bundle(handle)

        result.called = False
        handle = saved_state.unbundle(self.loop)
        self.loop.tick()

        self.assertFalse(result.called)
