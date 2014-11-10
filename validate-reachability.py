#!/usr/bin/env python3
from pathlib import Path
import argparse
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('root', help='root ticket (eg: comp/main)')
parser.add_argument('dir', help='directory (eg: comp)')
arguments = parser.parse_args()

linked = set()
worklist = set([arguments.root])

errors = False

while worklist:
    element = worklist.pop()
    linked.add(element)
    try:
        with Path(element).with_suffix('.yaml').open() as f:
            data = yaml.load(f)
        for dependency in data.get('dependencies', ()):
            if dependency not in linked:
                worklist.add(dependency)
    except IOError:
        print('Missing ticket: {}'.format(element))
        errors = True

for element in Path(arguments.dir).glob('**/*.yaml'):
    ticket = str(element.with_suffix(''))
    if ticket not in linked:
        print('Unlinked ticket: {}'.format(ticket))
        errors = True

if errors:
    exit(1)

