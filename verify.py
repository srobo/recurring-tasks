from pathlib import Path
import argparse
import yaml
from collections import namedtuple
from termcolor import cprint
import textwrap

ROOT = Path(__file__).parent

parser = argparse.ArgumentParser()
parser.add_argument('base', help='Root ticket to generate')
parser.add_argument('year', help='SR year to generate for')
parser.add_argument('-t', '--trac-root',
                    help='Base URL for the Trac installation',
                    default=None)
arguments = parser.parse_args()
BASE = arguments.base
YEAR = arguments.year

CYCLE = object()
elements = {}

Ticket = namedtuple('Ticket',
                    ['summary', 'priority', 'component',
                     'milestone', 'description', 'dependencies'])

def trac_description_text(ticket):
    text = textwrap.fill(ticket.description, width=72)
    if ticket.dependencies:
        text += '\n\nDependencies:\n\n'
        for dep in sorted(ticket.dependencies):
            text += ' * #{}\n'.format(dep)
    return text.strip()

class FakeTrac(object):
    def __init__(self):
        self.next_ticket = 2501

    def submit(self, ticket):
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
        desc = trac_description_text(ticket)
        cprint(textwrap.indent(desc, '  '))
        return ticket_number

TRAC = FakeTrac()

def add(element):
    if element in elements:
        previous = elements[element]
        if previous is CYCLE:
            raise RuntimeError('cyclic dependency on {}'.format(element))
        return previous
    else:
        elements[element] = CYCLE
        generated = process(ROOT / '{}.yaml'.format(element))
        ticket_id = TRAC.submit(generated)
        elements[element] = ticket_id
        return ticket_id

def handle_dep(key):
    if isinstance(key, int):
        return key
    return add(key)

def process(path):
    with path.open('r') as f:
        data = f.read()
    data = data.replace('$YYYY', str(YEAR))
    data = data.replace('$SRYYYY', 'SR{}'.format(YEAR))
    raw_elements = yaml.load(data)
    if 'summary' not in raw_elements and 'description' not in raw_elements:
        raise RuntimeError('{} contains neither a summary nor a description'.format(path))
    description = raw_elements.get('description', '')
    summary = raw_elements.get('summary', description.splitlines()[0])
    component = raw_elements.get('component')
    priority = raw_elements.get('priority', 'major')
    if priority not in ('trivial', 'minor', 'major', 'critical', 'blocker'):
        raise RuntimeError('{} has an invalid priority: {}'.format(path, priority))
    if component not in ('Arena', 'Competition', 'Website', 'sysadmin', 'Rules'):
        raise RuntimeError('{} has an unknown component: {}'.format(path, component))
    milestone = raw_elements.get('milestone')
    dependencies = raw_elements.get('dependencies', ())
    computed_dependencies = [handle_dep(element) for element in dependencies]
    data = Ticket(summary=summary,
                  component=component,
                  priority=priority,
                  milestone=milestone,
                  description=description,
                  dependencies=computed_dependencies)
    return data

add(BASE)

