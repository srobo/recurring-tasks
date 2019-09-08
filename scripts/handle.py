import argparse
import textwrap
import urllib.parse
from getpass import getpass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, NamedTuple, Union

import yaml
from termcolor import cprint

ROOT = Path(__file__).parent.parent


class Ticket(NamedTuple):
    summary: str
    priority: str
    component: str
    original_name: str
    milestone: str
    description: str
    dependencies: List[int]


if TYPE_CHECKING:
    from typing_extensions import Protocol

    class Backend(Protocol):
        def submit(self, ticket: Ticket) -> int:
            ...

        def title(self, ticket_number: int) -> str:
            ...


def trac_description_text(ticket: Ticket, backend: 'Backend') -> str:
    text = ticket.description
    text += '\n\nOriginal: [recurring-task:{}]'.format(ticket.original_name)
    if ticket.dependencies:
        text += '\n\nDependencies:\n\n'
        for dep in sorted(ticket.dependencies):
            text += (' * #{} {}'.format(dep, backend.title(dep)).rstrip()) + '\n'
    return text.strip()


class FakeTrac(object):
    def __init__(self) -> None:
        self.next_ticket = 2673
        self._known_titles: Dict[int, str] = {}

    def submit(self, ticket: Ticket) -> int:
        ticket_number = self.next_ticket
        self.next_ticket += 1
        PRIORITY_COLOURS = {'trivial': 'cyan',
                            'minor': 'blue',
                            'major': 'green',
                            'critical': 'yellow',
                            'blocker': 'red'}
        cprint('#{}: {}'.format(ticket_number, ticket.summary),
               PRIORITY_COLOURS[ticket.priority],
               attrs=['bold'])
        desc = trac_description_text(ticket, self)
        cprint(textwrap.indent(desc, '  '))
        self._known_titles[ticket_number] = ticket.summary
        return ticket_number

    def title(self, ticket_number: int) -> str:
        return self._known_titles.get(ticket_number, '')


class RealTrac(object):
    def __init__(self, root: str):
        self.root = root
        import xmlrpc.client as xml  # type:ignore  # no stubs available
        attrs = urllib.parse.urlsplit(root)
        username = attrs.username or input('SR username: ')
        password = attrs.password or getpass('SR password: ')
        port = ':{}'.format(attrs.port) if attrs.port is not None else ''
        generated_netloc = '{}:{}@{}{}'.format(urllib.parse.quote(username),
                                               urllib.parse.quote(password),
                                               attrs.hostname,
                                               port)
        generated_parts = (attrs.scheme,
                           generated_netloc,
                           attrs.path.rstrip('/') + '/login/xmlrpc',
                           '', '')
        target_url = urllib.parse.urlunsplit(generated_parts)
        self._xml = xml.ServerProxy(target_url)
        print(self._xml.system.methodHelp('ticket.create'))

    def submit(self, ticket: Ticket) -> int:
        desc = trac_description_text(ticket, self)
        attrs = {}
        if ticket.component is not None:
            attrs['component'] = ticket.component
        if ticket.milestone is not None:
            attrs['milestone'] = ticket.milestone
        attrs['priority'] = ticket.priority
        ticket_number = self._xml.ticket.create(ticket.summary,
                                                desc,
                                                attrs,
                                                False)
        print('Created ticket #{}: {}'.format(ticket_number,
                                              ticket.summary))
        return ticket_number  # type: ignore

    def title(self, ticket_number: int) -> str:
        ticket_data = self._xml.ticket.get(ticket_number)
        return ticket_data[3]['summary']  # type: ignore


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
    data = data.replace('$SRYYYY', 'SR{}'.format(year))
    raw_elements = yaml.load(data)
    if 'summary' not in raw_elements and 'description' not in raw_elements:
        raise RuntimeError('{} contains neither a summary nor a description'.format(path))
    description = raw_elements.get('description', '')

    if not len(description.splitlines()) == 0:
        summary = raw_elements.get('summary', description.splitlines()[0])
    else:
        summary = raw_elements["summary"]

    component = raw_elements.get('component')
    priority = raw_elements.get('priority', 'major')
    if priority not in ('trivial', 'minor', 'major', 'critical', 'blocker'):
        raise RuntimeError('{} has an invalid priority: {}'.format(path, priority))
    if component not in COMPONENTS:
        raise RuntimeError('{} has an unknown component: {}'.format(path, component))
    milestone = raw_elements.get('milestone')
    dependencies = raw_elements.get('dependencies', ())
    computed_dependencies = [handle_dep(element) for element in dependencies]
    ticket = Ticket(summary=summary,
                    component=component,
                    priority=priority,
                    milestone=milestone,
                    original_name=element_name,
                    description=description,
                    dependencies=computed_dependencies)
    return ticket


def add(element: str, backend: 'Backend', year: str) -> int:
    CYCLE = object()
    elements: Dict[str, Union[int, object]] = {}

    if element in elements:
        previous = elements[element]
        if previous is CYCLE:
            raise RuntimeError('cyclic dependency on {}'.format(element))
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


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('base', help='Root ticket to generate')
    parser.add_argument('year', help='SR year to generate for')
    parser.add_argument('-t', '--trac-root',
                        help='Base URL for the Trac installation',
                        default=None)
    return parser.parse_args()


def main(arguments: argparse.Namespace) -> None:
    if arguments.trac_root is not None:
        backend: 'Backend' = RealTrac(arguments.trac_root)
    else:
        backend = FakeTrac()

    add(arguments.base, backend, arguments.year)


if __name__ == '__main__':
    main(parse_args())
