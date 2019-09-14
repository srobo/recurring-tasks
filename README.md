recurring-tasks
===============

[![CircleCI](https://circleci.com/gh/srobo/recurring-tasks.svg?style=svg)](https://circleci.com/gh/srobo/recurring-tasks)

A collection of recurring tasks associated with Student Robotics' events.

Each file represents a single task, and will become a single ticket in a task
tracking system.

Each task can be uniquely referred to through use of its task name. This
is the path to the file relative to the root of the repo and without the
`.yaml` extension. For example: `comp/main`.

Attributes on the tickets are represented by top level keys within the files,
with the addition of a `dependencies` key. Dependencies are specified using the
name of the task as described above.

By default the import will simply output information to the console, however it
also supports creating tasks in either a Trac instance (though this is
deprecated) or as issues on a GitHub repository.
