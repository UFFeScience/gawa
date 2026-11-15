import ast
import math
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock


class FilterInvocationTests(unittest.TestCase):
    def test_long_paths_use_short_arguments_and_original_thresholds(self):
        source = Path(__file__).resolve().parents[1] / 'lib/gawa.py'
        function = next(node for node in ast.parse(source.read_text()).body if isinstance(node, ast.FunctionDef) and node.name == 'run_mr_filter')
        process = Mock(PIPE=subprocess.PIPE)
        scope = {'math': math, 'os': os, 'subprocess': process}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), scope)
        directory = '/tmp/' + 'a' * 180 + '/tile 000'
        for scale in range(4):
            config = {'path_mr_filter': '', 'map_resolution': 1, 'detection_mode': 'test', 'wavelet_specs': {'test': {'scale_min_arcmin': 2 ** scale, 'scale_max_arcmin': 16}}}
            scope['run_mr_filter'](directory + '/input.fits', directory + '/output.fits', config)
            args, kwargs = process.run.call_args
            self.assertEqual(args[0][-2:], ['input.fits', 'output.fits'])
            self.assertEqual(args[0][args[0].index('-s') + 1], ','.join(['10.'] * scale + ['3.', '3.']))
            self.assertEqual(kwargs['cwd'], directory)
            self.assertTrue(kwargs['check'])
            self.assertNotIn('shell', kwargs)


if __name__ == '__main__':
    unittest.main()
