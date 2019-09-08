import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Union

import yaml
from import_backends import FakeTrac, RealTrac
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
    'SRComp suite',
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

    raw_elements = yaml.load(data)
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
    CYCLE = object()
    elements: Dict[str, Union[int, object]] = {}

    if element in elements:
        previous = elements[element]
        if previous is CYCLE:
            raise RuntimeError(f"cyclic dependency on {element}")
        assert isinstance(previous, int)
        return previous
    else:
        elements[element] = CYCLE
        generated = process(
            element,
            year=year,
            handle_dep=lambda x: add(x, backend, year),
        )
        ticket_id = backend.submit(generated)
        elements[element] = ticket_id
        return ticket_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('base', help="Root ticket to generate")
    parser.add_argument('year', help="SR year to generate for")
    parser.add_argument(
        '-t', '--trac-root',
        help="Base URL for the Trac installation",
        default=None,
    )
    return parser.parse_args()


def main(arguments: argparse.Namespace) -> None:
    if arguments.trac_root is not None:
        backend: 'Backend' = RealTrac(arguments.trac_root)
    else:
        backend = FakeTrac()

    add(arguments.base, backend, arguments.year)


if __name__ == '__main__':
    main(parse_args())
