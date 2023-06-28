from pavilion import unittest
from pavilion import errors

from lark import Token

import pickle


class ErrorTests(unittest.PavTestCase):
	"""Test functionaility of Pavilion specific errors."""

	def test_error_pickling(self):
		"""Check that all of the Pavilon errors pickle and unpickle correctly."""


		prior_error = ValueError("hiya")

		base_args = (["foo"], )
		base_kwargs = {'prior_error':prior_error, 'data': {"foo": "bar"}}

		spec_args = {
			'VariableError': (('hello',),
							  {'var_set': 'var', 'var': 'foo',
							   'index': 3, 'sub_var': 'ok', 'prior_error': prior_error}),
			'DeferredError': (('hello',),
							  {'var_set': 'var', 'var': 'foo',
							   'index': 3, 'sub_var': 'ok', 'prior_error': prior_error}),
			'ParserValueError': ((Token('oh_no', 'terrible_things'), 'hello'), {})
		}

		base_attrs = dir(errors.PavilionError("foo"))

		exc_classes = []
		for name in dir(errors):
			obj = getattr(errors, name)
			if (type(obj) == type(errors.PavilionError)
					and issubclass(obj, errors.PavilionError)):
				exc_classes.append(obj)

		for exc_class in exc_classes:
			exc_name = exc_class.__name__

			args, kwargs = spec_args.get(exc_name, (base_args, base_kwargs))

			inst = exc_class(*args, **kwargs)

			p_str = pickle.dumps(inst)

			try:
				new_inst = pickle.loads(p_str)
			except TypeError:
				self.fail("Failed to reconstitute exception '{}'".format(exc_name))

			self.assertEqual(inst, new_inst)
