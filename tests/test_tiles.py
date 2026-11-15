import ast
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class WorkflowTests(unittest.TestCase):
    def test_graph_concurrency_and_completeness(self):
        generator = module('generator', BASE / 'akoflow/generate_tiles.py')
        for cap in (1, 2, 4, 8, 14):
            with self.subTest(cap=cap):
                graph = {}
                for line in generator.generate(14, cap).splitlines():
                    if line.startswith('    - name: '):
                        name = line.split(': ', 1)[1]
                        graph[name] = []
                    elif line.startswith('        - "'):
                        graph[name].append(line.strip()[3:-1])
                self.assertEqual(len(graph), 16)
                self.assertEqual(set(graph['merge']), {f'tile-{i:03d}' for i in range(14)})
                done = set()
                widths = []
                while len(done) < len(graph):
                    ready = {n for n, deps in graph.items() if n not in done and set(deps) <= done}
                    self.assertTrue(ready, 'cyclic graph')
                    widths.append(len(ready))
                    done |= ready
                self.assertEqual(max(widths), cap)

    def test_rejects_invalid_parallelism(self):
        generator = module('generator', BASE / 'akoflow/generate_tiles.py')
        for count, cap in ((0, 1), (14, 0), (14, 15)):
            with self.assertRaises(ValueError):
                generator.generate(count, cap)

    def test_scientific_worker_has_no_parsl_dependency(self):
        tree = ast.parse((BASE / 'lib/tile_tasks.py').read_text())
        self.assertFalse(any(isinstance(n, ast.ImportFrom) and n.module == 'parsl' for n in ast.walk(tree)))
        self.assertFalse(any(isinstance(n, ast.FunctionDef) and n.decorator_list for n in tree.body))


class TileTests(unittest.TestCase):
    def setUp(self):
        self.runner = module('runner', BASE / 'gawa_tasks.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runner.ROOT = Path(self.temp.name)
        self.params = {'out_paths': {'gawa': {'results': 'gawa_results'}}}
        self.runner.load = lambda: self.params
        self.runner.tiles = lambda params: [{'id': 0}, {'id': 1}]

    def test_processes_only_requested_tile(self):
        def worker(args):
            tile, config = args
            self.assertEqual(tile['id'], 1)
            output = self.runner.ROOT / 'results/tiles/tile_001/gawa_results/tile_info.fits'
            output.parent.mkdir(parents=True)
            output.touch()
        worker = Mock(side_effect=worker)
        fake = types.ModuleType('lib.tile_tasks')
        fake.run_gawa_tile_job = worker
        with patch.dict(sys.modules, {'lib.tile_tasks': fake}):
            self.runner.process(1)
        worker.assert_called_once()

    def test_unknown_tile_fails_without_running_worker(self):
        fake = types.ModuleType('lib.tile_tasks')
        fake.run_gawa_tile_job = Mock()
        with patch.dict(sys.modules, {'lib.tile_tasks': fake}):
            with self.assertRaisesRegex(RuntimeError, 'exactly one tile'):
                self.runner.process(9)
        fake.run_gawa_tile_job.assert_not_called()

    def test_missing_completion_fails(self):
        fake = types.ModuleType('lib.tile_tasks')
        fake.run_gawa_tile_job = Mock()
        with patch.dict(sys.modules, {'lib.tile_tasks': fake}):
            with self.assertRaisesRegex(RuntimeError, 'completion metadata'):
                self.runner.process(0)

    def test_merge_rejects_partial_results(self):
        fake = types.ModuleType('lib.gawa')
        fake.tiles_with_clusters = Mock()
        fake.gawa_concatenate = Mock()
        with patch.dict(sys.modules, {'lib.gawa': fake}):
            with self.assertRaisesRegex(RuntimeError, 'Missing tile completion'):
                self.runner.merge()
        fake.gawa_concatenate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
