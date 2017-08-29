import apricotpy.persistable as persistable
import unittest


class TestCaseWithLoop(unittest.TestCase):
    def setUp(self):
        super(TestCaseWithLoop, self).setUp()
        self.loop = persistable.BaseEventLoop()

    def tearDown(self):
        super(TestCaseWithLoop, self).tearDown()
        self.loop.close()
        self.loop = None
