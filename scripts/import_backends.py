import pathlib
import textwrap
import urllib.parse
from getpass import getpass
from typing import TYPE_CHECKING, Dict, List, Sequence

import github  # type: ignore
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


def get_github_credential() -> str:
    config_file = pathlib.Path(__file__).parent.parent / '.github-auth'

    auth_token = None

    if config_file.exists():
        with config_file.open() as f:
            auth_token = f.read()

    if auth_token is None:
        auth_token = getpass("GitHub Auth Token: ")

        store = input("Store auth token? [y/N]: ")
        if store in ('Y', 'y'):
            with config_file.open(mode='w') as f:
                f.write(auth_token)

    return auth_token


class GitHubBackend:
    COMPONENT_LABEL_MAPPING: Dict[str, Sequence[str]] = {
        'Competition': (),
        'Docs': (),
        'Kit': ['A: Team Kits'],
        'pyenv': ['A: Team Kits', 'A: Software'],
        'Rules': ['A: Game Rules'],
        'sysadmin': ['A: Software'],
        'Website': ['A: Software'],
        # 'Tall Ship': ['Tall Ship'],  # Uncomment this for testing
    }

    COMPONENT_PRIORITY_MAPPING: Dict[str, str] = {
        'trivial': 'I: Could Have',
        'minor': 'I: Could Have',
        'major': 'I: Should Have',
        'critical': 'I: Must Have',
        'blocker': 'I: Must Have',
    }

    def __init__(self, repo_name: str) -> None:
        self.github = github.Github(get_github_credential())
        self.repo = self.github.get_repo(repo_name)
        self.milestones: Dict[str, github.Milestone.Milestone] = {
            x.title: x for x in self.repo.get_milestones()
        }

        labels: Dict[str, github.Label.Label] = {
            x.name: x for x in self.repo.get_labels()
        }

        try:
            self._component_label_mapping = {
                k: [labels[x] for x in v]
                for k, v in self.COMPONENT_LABEL_MAPPING.items()
            }
            self._component_priority_mapping = {
                k: labels[v] for k, v in self.COMPONENT_PRIORITY_MAPPING.items()
            }
        except KeyError as e:
            raise ValueError(
                f"Label {e} does not exist within {repo_name!r}",
            ) from None

        self._known_titles: Dict[int, str] = {}

    @staticmethod
    def _section(heading: str, body: str) -> str:
        return f"\n\n### {heading}\n\n{body}"

    def _original_link(self, ticket: Ticket) -> str:
        url = urllib.parse.urljoin(
            'https://github.com/srobo/recurring-tasks/',
            f'blob/master/{ticket.original_name}.yaml',
        )
        return f"[{ticket.original_name}]({url})"

    def description_text(self, ticket: Ticket) -> str:
        text = ticket.description

        text += self._section("Original", self._original_link(ticket))

        if ticket.dependencies:
            text += self._section("Dependencies", "\n".join(
                f" * #{dep} {self.title(dep)}".rstrip()
                for dep in sorted(ticket.dependencies)
            ))

        return text.strip()

    def get_or_create_milestone(self, title: str) -> github.Milestone:
        try:
            return self.milestones[title]
        except KeyError:
            milestone = self.repo.create_milestone(title)
            print(f"Created Milestone {title}")
            self.milestones[title] = milestone
            return milestone

    def labels(self, ticket: Ticket) -> List[github.Label.Label]:
        labels = [self._component_priority_mapping[ticket.priority]]
        labels += self._component_label_mapping[ticket.component]
        return labels

    def submit(self, ticket: Ticket) -> int:
        issue = self.repo.create_issue(
            ticket.summary,
            self.description_text(ticket),
            milestone=self.get_or_create_milestone(ticket.milestone),
            labels=self.labels(ticket),
        )

        ticket_number: int = issue.number
        self._known_titles[ticket_number] = ticket.summary
        return ticket_number

    def title(self, ticket_number: int) -> str:
        return self._known_titles.get(ticket_number, '')
