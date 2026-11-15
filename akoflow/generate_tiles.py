"""Generate the same legacy YAML dialect as the supplied GAWA workflow."""
import argparse
from pathlib import Path


def generate(count=14, parallel=14):
    if count < 1 or not 1 <= parallel <= count:
        raise ValueError('Require 1 <= parallel <= tiles')
    lines = [f'name: akf-wf-gawa-tiles-{parallel}way', 'spec:',
             '  image: "ghcr.io/uffescience/gawa:tiles-v1"',
             '  namespace: "akoflow"', '  storageClassName: "hostpath"', '  storageSize: "10Gi"',
             '  storagePolicy:', '    type: distributed', '  mountPath: "/data-akoflow"', '  activities:']

    def activity(name, command, dependencies=(), memory='4Gi'):
        lines.extend([f'    - name: {name}', '      run: |', '        set -eu',
                      '        export PYTHONPATH=/data${PYTHONPATH:+:$PYTHONPATH}',
                      '        export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1'])
        lines.extend('        ' + line for line in command.splitlines())
        lines.extend([f'      memoryLimit: {memory}', '      cpuLimit: 1'])
        if dependencies:
            lines.append('      dependsOn:')
            lines.extend(f'        - "{dep}"' for dep in dependencies)

    runner = '/data/gawa_tasks.py'
    python = 'conda run --no-capture-output -n gawa python -W ignore'
    activity('prepare', f'{python} {runner} prepare --count {count}')
    names = [f'tile-{i:03d}' for i in range(count)]
    for i, name in enumerate(names):
        dependencies = ['prepare'] if i < parallel else [names[i - parallel]]
        activity(name, f'{python} {runner} tile --id {i}', dependencies)
    activity('merge', f'{python} {runner} merge', names)
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tiles', type=int, default=14)
    parser.add_argument('--parallel', type=int, default=14)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(generate(args.tiles, args.parallel))
    print(args.output)
