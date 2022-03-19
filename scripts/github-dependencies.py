import argparse
import itertools
import re
import subprocess
import sys
from pathlib import Path
from typing import Collection, Dict, Iterable, List, Optional

import github
from import_backends import get_github_credential


def dropuntil(iterable: List[str], key: str) -> Iterable[str]:
    found = False
    for x in iterable:
        if found and x:
            yield x
        found = found or x == key


def parse_issue_id(text: str) -> Optional[int]:
    match = re.search(r'#(\d+) ', text)
    if match is not None:
        return int(match.group(1))
    return None


class GitHubBackend:
    def __init__(self, repo_name: str, milestones: Collection[str]) -> None:
        self.github = github.Github(get_github_credential())
        self.repo = self.github.get_repo(repo_name)

        self.milestones: Dict[str, github.Milestone.Milestone] = {
            x.title: x for x in self.repo.get_milestones()
        }

        self.labels: Dict[str, github.Label.Label] = {
            x.name: x for x in self.repo.get_labels()
        }

        self.issues: Dict[int, github.Issue.Issue] = {
            x.number: x for x in itertools.chain.from_iterable(
                self.repo.get_issues(
                    state='all',
                    milestone=self.milestones[m],
                )
                for m in milestones
            )
        }

        self.dependencies: Dict[int, List[int]] = {
            x: self.get_dependencies(x) for x in self.issues.keys()
        }

    def get_issue(self, number: int) -> Optional[github.Issue.Issue]:
        try:
            return self.issues[number]
        except KeyError:
            print(f"Warning: unknown issue {number}", file=sys.stderr)
            return None

    def get_dependencies(self, number: int) -> List[int]:
        issue = self.get_issue(number)
        if not issue:
            return []

        lines = dropuntil(issue.body.splitlines(), key='### Dependencies')
        parsed = [parse_issue_id(y) for y in lines]
        return [x for x in parsed if x is not None]

    def as_dot(self) -> str:
        def issue_as_dot(number: int, deps: List[int]) -> str:
            issue = self.get_issue(number)
            if issue is None:
                raise ValueError(number)

            deps_str = ' '.join(str(y) for y in deps)
            title = issue.title.replace('"', '\\"')
            colour = "black"

            if issue.state == 'closed':
                title = f"{title} (closed)"
                colour = "grey"

            return "\n".join((
                f'    {number} [ label="{title}" fontcolor={colour} color={colour} ]',
                f'    {number} -> {{ {deps_str} }}',
            ))

        body = "\n".join(
            issue_as_dot(number, deps)
            for number, deps in self.dependencies.items()
        )
        return f"digraph {{ {body} }}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--github-repo',
        help="GitHub repository name (default: %(default)s)",
        default='srobo/tasks',
    )
    parser.add_argument(
        'milestones',
        nargs=argparse.ONE_OR_MORE,
        help="The milestones to pull tasks from",
    )
    parser.add_argument(
        '--output',
        type=Path,
        help="The milestones to pull tasks from",
    )

    return parser.parse_args()


def main(arguments: argparse.Namespace) -> None:
    backend = GitHubBackend(
        arguments.github_repo,
        arguments.milestones,
    )

    dot = backend.as_dot()

    with arguments.output.open(mode='wb') as f:
        subprocess.run(
            ['dot', '-Grankdir=LR', '-Tpdf'],
            input=dot.encode(),
            stdout=f,
            check=True,
        )


if __name__ == '__main__':
    main(parse_args())
