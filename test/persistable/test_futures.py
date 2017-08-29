import apricotpy
from . import utils
import apricotpy.persistable as persistable


def futures_equal(f1, f2):
    """ Check that two futures are the same in terms of state """
    if f1._state != f2._state:
        return False

    if f1._result != f2._result:
        return False

    if f1._exception != f2._exception:
        return False

    if f1._callbacks != f2._callbacks:
        return False

    return True


def fut_done(fut):
    pass


class TestFuture(utils.TestCaseWithLoop):
    def test_create(self):
        self.loop.create_future()

    def test_result(self):
        fut = self.loop.create_future()
        fut.set_result('done yo')
        self.assertEqual(fut.result(), 'done yo')

    def test_no_result(self):
        fut = self.loop.create_future()
        self.assertRaises(apricotpy.InvalidStateError, fut.result)

    def test_saving_state_no_result(self):
        fut = self.loop.create_future()

        # Bundle up the future
        saved_state = persistable.Bundle(fut)

        # Now unbundle it
        fut2 = saved_state.unbundle(saved_state)

        self.assertTrue(futures_equal(fut, fut2))

    def test_saving_state_with_result(self):
        fut = self.loop.create_future()
        fut.set_result('done')

        # Bundle up the future
        saved_state = persistable.Bundle(fut)

        # Now unbundle it
        fut2 = saved_state.unbundle(saved_state)

        self.assertTrue(futures_equal(fut, fut2))

    def test_saving_state_with_exception(self):
        fut = self.loop.create_future()
        fut.set_exception(ValueError())

        # Bundle up the future
        saved_state = persistable.Bundle(fut)

        # Now unbundle it
        fut2 = saved_state.unbundle(saved_state)

        self.assertTrue(futures_equal(fut, fut2))

    def test_saving_state_with_callbacks(self):
        fut = self.loop.create_future()
        fut.add_done_callback(fut_done)

        # Bundle up the future
        saved_state = persistable.Bundle(fut)

        # Now unbundle it
        fut2 = saved_state.unbundle(saved_state)

        self.assertTrue(futures_equal(fut, fut2))
