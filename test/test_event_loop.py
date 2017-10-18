import unittest
import apricotpy


class StringObj(apricotpy.LoopObject):
    @staticmethod
    def create(loop, value):
        return StringObj(value)

    def __init__(self, value):
        super(StringObj, self).__init__()
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

    def test_create_message(self):
        result = {}

        def created(loop, subject, body, sender_id):
            result['subject'] = subject
            result['body'] = body

        self.loop.messages().add_listener(created, 'loop.object.*.created')
        obj = self.loop.create(StringObj, 'created')
        self.loop.run_until_complete(self.loop.remove(obj))

        self.assertEqual(result['subject'], 'loop.object.{}.created'.format(obj.uuid))
        self.assertEqual(result['body'], obj.uuid)

    def test_default_error_handler(self):
        # Now try a context with a traceback
        try:
            raise RuntimeError('Test error!')
        except RuntimeError as e:
            context = {
                'message': str(e),
                'exception': e,
            }
            self.loop.default_exception_handler(context)

    def test_default_error_handler_with_traceback(self):
        try:
            raise RuntimeError('Test error!')
        except RuntimeError as e:
            e.__traceback__ = None
            context = {
                'message': str(e),
                'exception': e,
            }
            self.loop.default_exception_handler(context)
