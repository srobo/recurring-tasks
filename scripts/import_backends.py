import textwrap
import urllib.parse
from getpass import getpass
from typing import TYPE_CHECKING, Dict

from termcolor import cprint
from ticket_type import Ticket

if TYPE_CHECKING:
    from typing_extensions import Protocol

    class Backend(Protocol):
        def submit(self, ticket: Ticket) -> int:
            ...

        def title(self, ticket_number: int) -> str:
            ...


def trac_description_text(ticket: Ticket, backend: 'Backend') -> str:
    text = ticket.description
    text += f"\n\nOriginal: [recurring-task:{ticket.original_name}]"
    if ticket.dependencies:
        text += "\n\nDependencies:\n\n"
        for dep in sorted(ticket.dependencies):
            text += f" * #{dep} {backend.title(dep)}".rstrip() + "\n"
    return text.strip()


class FakeTracBackend:
    def __init__(self) -> None:
        self.next_ticket = 2673
        self._known_titles: Dict[int, str] = {}

    def submit(self, ticket: Ticket) -> int:
        ticket_number = self.next_ticket
        self.next_ticket += 1
        PRIORITY_COLOURS = {
            'trivial': 'cyan',
            'minor': 'blue',
            'major': 'green',
            'critical': 'yellow',
            'blocker': 'red',
        }
        cprint(
            f"#{ticket_number}: {ticket.summary}",
            PRIORITY_COLOURS[ticket.priority],
            attrs=['bold'],
        )
        desc = trac_description_text(ticket, self)
        cprint(textwrap.indent(desc, '  '))
        self._known_titles[ticket_number] = ticket.summary
        return ticket_number

    def title(self, ticket_number: int) -> str:
        return self._known_titles.get(ticket_number, '')


class RealTracBackend:
    def __init__(self, root: str):
        self.root = root
        import xmlrpc.client as xml  # type:ignore  # no stubs available

        attrs = urllib.parse.urlsplit(root)
        username = attrs.username or input("SR username: ")
        password = attrs.password or getpass("SR password: ")
        port = f':{attrs.port}' if attrs.port is not None else ''
        generated_netloc = '{}:{}@{}{}'.format(
            urllib.parse.quote(username),
            urllib.parse.quote(password),
            attrs.hostname,
            port,
        )
        generated_parts = (
            attrs.scheme,
            generated_netloc,
            attrs.path.rstrip('/') + '/login/xmlrpc',
            '',
            '',
        )
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

        ticket_number: int = self._xml.ticket.create(
            ticket.summary,
            desc,
            attrs,
            False,
        )

        print(f"Created ticket #{ticket_number}: {ticket.summary}")
        return ticket_number

    def title(self, ticket_number: int) -> str:
        ticket_data = self._xml.ticket.get(ticket_number)
        return ticket_data[3]['summary']  # type: ignore
