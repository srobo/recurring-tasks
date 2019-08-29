recurring-tasks
===============

[![CircleCI](https://circleci.com/gh/srobo/recurring-tasks.svg?style=svg)](https://circleci.com/gh/srobo/recurring-tasks)

A collection of recurring tasks associated with Student Robotics' events

Each file represents a single task, and will become a single trac ticket.

Each task can be uniquely referred to through use of its task name. This
is the path to the file relative to the root of the repo and without the
`.yaml` extension. For example: `comp/main`.

Attributes on the tickets are represented by top level keys within the files,
with the addition of a `dependencies` key.
This allows the listing of task dependencies in the following ways:
 * By the name of the task
 * By a glob on the name of some tasks
 * By existing ticket number within the target trac instance, prefixed
   with an underscore rather than a hash so that it doesn't get treated
   as a comment by the yaml loader. For example: `_545`.
