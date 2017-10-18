import apricotpy
import unittest


class TestCaseWithLoop(unittest.TestCase):
    def setUp(self):
        super(TestCaseWithLoop, self).setUp()
        self.loop = apricotpy.BaseEventLoop()
        apricotpy.set_event_loop(self.loop)

    def tearDown(self):
        super(TestCaseWithLoop, self).tearDown()
        apricotpy.set_event_loop(None)
        self.loop.close()
        self.loop = None
