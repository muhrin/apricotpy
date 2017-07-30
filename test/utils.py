import apricotpy
import unittest


class TestCaseWithLoop(unittest.TestCase):
    def setUp(self):
        super(TestCaseWithLoop, self).setUp()
        self.loop = apricotpy.BaseEventLoop()

    def tearDown(self):
        super(TestCaseWithLoop, self).tearDown()
        self.loop.close()
        self.loop = None
