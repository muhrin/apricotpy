import apricotpy
from . import utils


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

    def test_default_loop(self):
        fut = apricotpy.Future()
        self.assertIsNotNone(fut._loop)
