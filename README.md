# Recurring Tasks

[![CircleCI](https://circleci.com/gh/srobo/recurring-tasks.svg?style=svg)](https://circleci.com/gh/srobo/recurring-tasks)

A collection of recurring tasks associated with Student Robotics' events.

## Task representation

Each file represents a single task, and will become a single ticket in a task
tracking system.

Each task can be uniquely referred to through use of its task name. This
is the path to the file relative to the root of the repo and without the
`.yaml` extension. For example: `comp/main`.

Attributes on the tickets are represented by top level keys within the files,
with the addition of a `dependencies` key. Dependencies are specified using the
name of the task as described above.

Dependencies are allowed to overlap (i.e: several things can depend on some
common task) and in such cases only a single instance of the common task will be
created in the tracker. Dependencies are *not* allowed to be circular.

### Adding tasks

Tasks can either be created by hand, or by using the script at `scripts/add`.
The script will guide you through specifying the required attributes for a task.

When adding a task you should ensure the resulting hierarchy is still valid (see
below). If adding many tasks or otherwise working on the hierarchy for a while,
`scripts/watch` can be used to watch for changes and automatically run the
validation checks when changes appear.

### Validation

Tasks are expected to either be root tasks or be depended upon by other tasks
(all the way up to a root). This can be checked using `scripts/validate-reachability.py`.

The set of possible priorities and components are primarily limited by support
in the backend, though all are expected to support the same sets. The default
backend (which prints to the console) can be used to do a dry-run of an import
and thus detect any issues which might occur, either from circular dependencies
or from unsupported components.

Both of these checks are combined by the `scripts/validate` script which can be
used to safely validate that a given tree of tasks meets expectations.
This check is performed on CI for each of the main task roots.

## Importing tasks

Tasks can be imported into a tracker using the Python 3.13+ script at
`scripts/import.py`. The dependencies for this script are recorded in
`scripts/requirements.txt`

By default the import will simply output information to the console, however it
also supports creating tasks in either a Trac instance (though this is
deprecated) or as issues on a GitHub repository.

For importing into a Trac instance, the instance will need to have the XML-RPC
plugin available and you will need an account with permissions to read and write
tickets through that API.

For importing into issues on a GitHub repo, their [REST API v3][github-rest-api]
is used so you will need a [Personal Access Token][api-tokens] with permissions
to create issues on that repo. For public repositories, this is covered by the
`repo:public_repo` scope.

[github-rest-api]: https://developer.github.com/v3/issues/
[api-tokens]: https://blog.github.com/2013-05-16-personal-api-tokens/
