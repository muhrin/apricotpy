import unittest
import apricotpy


class StringObj(apricotpy.LoopObject):
    @staticmethod
    def create(loop, value):
        return StringObj(loop, value)

    def __init__(self, loop, value):
        super(StringObj, self).__init__(loop)
        self.value = value


class TestEventLoop(unittest.TestCase):
    def setUp(self):
        super(TestEventLoop, self).setUp()
        self.loop = apricotpy.BaseEventLoop()

    def tearDown(self):
        super(TestEventLoop, self).tearDown()
        self.loop.close()
        self.loop = None

    def test_object_factory(self):
        value_string = "'sup yo"

        self.loop.set_object_factory(StringObj.create)
        a = self.loop.create(value_string)
        self.assertEqual(a.value, value_string)

    def test_create_remove(self):
        obj = self.loop.create(StringObj, 'mmmm...apricot pie')
        uuid = obj.uuid
        result = ~self.loop.remove(obj)

        self.assertEqual(result, uuid)
