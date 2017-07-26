import unittest
import apricotpy


class TestFuture(unittest.TestCase):
    def setUp(self):
        self.loop = apricotpy.BaseEventLoop()

    def tearDown(self):
        self.loop.close()
        self.loop = None

    def test_create(self):
        self.loop.create_future()

    def test_result(self):
        fut = self.loop.create_future()
        fut.set_result('done yo')
        self.assertEqual(fut.result(), 'done yo')

    def test_no_result(self):
        fut = self.loop.create_future()
        self.assertRaises(apricotpy.InvalidStateError, fut.result)
