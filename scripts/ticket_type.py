from typing import List, NamedTuple


class Ticket(NamedTuple):
    summary: str
    priority: str
    component: str
    original_name: str
    milestone: str
    description: str
    dependencies: List[int]
