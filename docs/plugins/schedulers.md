# Scheduler Plugins

This page is an overview of scheduler plugins and how to write them.

Scheduler plugins take care of the scheduling part of testing. For this
documentation, we will use the `raw` scheduler plugin for examples. 

## Writing Scheduler Plugins

Scheduler plugins require the [source code](#writing-the-source) and the
[yapsy-plugin](basics.md#plugin_nameyapsy-plugin).

### Writing the Source
At the very least, each scheduler plugin will have a 
[variable class](#the-variables-class) and the actual 
[scheduler class](#the-scheduler-class)

#### The Variables Class

#### The Scheduler Class