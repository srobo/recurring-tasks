#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Union

import yaml
from import_backends import FakeTracBackend, GitHubBackend, RealTracBackend
from ticket_type import Ticket

if TYPE_CHECKING:
    from import_backends import Backend


ROOT = Path(__file__).parent.parent


COMPONENTS = (
    'Arena',
    'Competition',
    'Docs',
    'Kit',
    'Media',
    'pyenv',
    'Rules',
    'sysadmin',
    'Tall Ship',
    'Website',
)


def process(element_name: str, *, year: str, handle_dep: Callable[[str], int]) -> Ticket:
    """
    Load the data for a given element, fully expanding its dependencies using
    the given `handle_dep` callback.
    """

    path = (ROOT / element_name).with_suffix('.yaml')

    with path.open('r') as f:
        data = f.read()
    data = data.replace('$YYYY', str(year))
    data = data.replace('$SRYYYY', f'SR{year}')

    raw_elements = yaml.safe_load(data)
    if 'summary' not in raw_elements and 'description' not in raw_elements:
        raise RuntimeError(f"{path} contains neither a summary nor a description")

    description = raw_elements.get('description', '')

    if not len(description.splitlines()) == 0:
        summary = raw_elements.get('summary', description.splitlines()[0])
    else:
        summary = raw_elements["summary"]

    component = raw_elements.get('component')

    priority = raw_elements.get('priority', 'major')
    if priority not in ('trivial', 'minor', 'major', 'critical', 'blocker'):
        raise RuntimeError(f"{path} has an invalid priority: {priority}")

    if component not in COMPONENTS:
        raise RuntimeError(f"{path} has an unknown component: {component}")

    milestone = raw_elements.get('milestone')
    dependencies = raw_elements.get('dependencies', ())

    computed_dependencies = [handle_dep(element) for element in dependencies]

    ticket = Ticket(
        summary=summary,
        component=component,
        priority=priority,
        milestone=milestone,
        original_name=element_name,
        description=description,
        dependencies=computed_dependencies,
    )
    return ticket


def add(element: str, backend: 'Backend', year: str) -> int:
    """
    Add 'element' into the task tracker, along with all its dependencies.

    We recurse into all the dependencies of the task we're adding, working to
    add the leaves first so that the higher level tasks can be created with the
    links to their dependencies in place from the start.

    We keep a track of the tasks we've imported so far in order that we can
    detect (an reject) cycles, as well as to ensure that we cross-link any
    dependencies which have already been imported at the point they are
    depended upon by a new parent.
    """
    CYCLE = object()
    elements: Dict[str, Union[int, object]] = {}

    def _add(element: str) -> int:
        if element in elements:
            previous = elements[element]
            if previous is CYCLE:
                raise RuntimeError(f"cyclic dependency on {element}")
            assert isinstance(previous, int)
            return previous
        else:
            elements[element] = CYCLE
            generated = process(element, year=year, handle_dep=_add)
            ticket_id = backend.submit(generated)
            elements[element] = ticket_id
            return ticket_id

    return _add(element)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('base', help="Root ticket to generate")
    parser.add_argument(
        'year',
        help="SR year to generate for (specify as just the number part)",
    )

    backends_group = parser.add_mutually_exclusive_group()
    backends_group.add_argument(
        '-t', '--trac-root',
        help="Base URL for the Trac installation",
        default=None,
    )
    backends_group.add_argument(
        '-g', '--github-repo',
        help="GitHub repository name (e.g: srobo/tasks)",
        default=None,
    )

    return parser.parse_args()


def main(arguments: argparse.Namespace) -> None:
    if arguments.trac_root is not None:
        backend: 'Backend' = RealTracBackend(arguments.trac_root)
    elif arguments.github_repo is not None:
        backend = GitHubBackend(arguments.github_repo)
    else:
        backend = FakeTracBackend()

    add(arguments.base, backend, arguments.year)


if __name__ == '__main__':
    main(parse_args())
