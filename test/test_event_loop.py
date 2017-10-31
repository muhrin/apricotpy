import apricotpy
from . import utils


class StringObj(apricotpy.LoopObject):
    @staticmethod
    def create(value, loop=None):
        return StringObj(value, loop)

    def __init__(self, value, loop=None):
        super(StringObj, self).__init__(loop=loop)
        self.value = value


class TestEventLoop(utils.TestCaseWithLoop):
    def test_object_factory(self):
        value_string = "'sup yo"

        self.loop.set_object_factory(StringObj.create)
        a = self.loop.create(value_string)
        self.assertEqual(a.value, value_string)

    def test_create(self):
        obj = self.loop.create(StringObj, 'mmmm...apricot pie')

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
