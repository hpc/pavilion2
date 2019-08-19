# Pavilion Command Plugins

This page is an overview of command plugins and how to write them.

#### Contents


## Writing Command Plugins

A command in Pavilion is made up of two seperate parts, the [source code](#writing-the-source) and the [yapsy-plugin](#writing-the-yapsy-plugin).

#### Writing the Source

You begin writing the source with the command class definition. We have been using the CamelCase naming convention to keep everything the same. It is simply:
```python
from pavilion import commands

class NameCommand(commands.Command):
    """A basic command class."""

```

At the minimum each command will require three methods: `__init__`, `_setup_arguments`, and `run`. 

##### Writing `__init__()`:
The `__init__` method should only take one argument, that one argument being self, as this will be used to initialize the new command. 

In this method you will call `super().__init__()` and pass in the following arguments in this order: name, help string, and short_help = help string.  Below is an example of a command's `__init__` method:
```python
def __init__(self):
	super().__init__(
		'cancel',
		'Cancel a test, tests, or test series.',
		short_help = 'Cancel a test, tests, or series."
	)
```

Note, that the name you pass in this function will be the name used to run the command, and the help strings will be displayed when a user runs `pav --help` or `pav -h`.

##### Writing `_setup_arguments()`:

The `_setup_arguments()` method take only two arguments: self and parser. Parser is initialized in the super class (during the `super()__init__()` call), so you should not worry about creating your own parser.

In this method we add the valid arguments that can be used when calling your command. Each argument will need to have an action (I have only ever used store and store_true) and help text. Each argument also has the potential to have a nargs field, or default field. These would allow you to specify the number of arguments allowed and the default value of an argument, repsectively. More information about this can be found in the official [argparse](https://docs.python.org/3.5/library/argparse.html) documentation.

To add a parser argument we use the following syntax:
```python
    parser.add_argument(myarg)
```

Again, you can provide a ton of different arguments to this call, so I have provided two examples below. If there isn't enough here or you can't find something you're looking for give `show.py` a look or checkout the [argparse](https://docs.python.org/3.5/library/argparse.html) documentation. 
```python
    parser.add_argument(
        '-s', '--status', action='store_true', default=False,
        help = 'Prints status of cancelled jobs.'
    )
    parser.add_argument(
        'tests', nargs='*', action='store',
        help = 'The name(s) of the tests to cancel. These may be any mix of '
               ' test IDs and series IDs. If no value is provided, the most '
               ' recent sereis submitted by the user is cancelled. '
    )
```

##### Writing `run()`:

The `run` method should only take three arguments: self, pav_cfg, args. Pav_cfg is the pavilion configuration file which holds all of the information about pavilion, and args is the list of arguments given when the command was run.

Args is the parsed argument object from argparse, and will contain all your arguments as attributes `args.myarg.` For example, if you wanted to get the list of tests provided when the command was run you would reference the list by `args.tests`. Note, for flags like `-s` you get the name of the argument from the long name, i.e. `--status` specifies that `args.status` will hold the information required for the status argument (in this case it will be a bool value).

When working with tests (I believe just about every command will be), you need to remember that the arguments are strings. Because of this you will need to import additional libraries, most importantly `from pavilion.pav_test import PavTest`, to allow yourself the ability to access the actual test object. If you anticipate using series as well it will also be important to add `from pavilion import series`. Below is some sample code used to generate the lists of tests provided by `args.tests` including the ability to extract those in a test series.
```python
for test_id in args.tests:
    if test_id.startswith('s'):
        test_list.extend(series.TestSeries.from_id(pav_cfg,int(test_id[1:])).tests)
    else:
        test_list.append(test_id)
```
This code will populate a list of all test IDs, but they are still strings so you will need to do one of the following to get each test object.
```python
# Using Imported Series Module
test_object_list, test_failed_list = series.test_obj_from_id(pav_cfg, test_list)
```
Note, when using `series.test_obj_from_id` error handling is handled for you, as it will return a tuple made up of a list of test objects, and a list of test IDs that couldn't be found. Because of this, `series.test_obj_from_id` is the preferred way of accessing test objects.

Now that you have a test object you can get valuable information out of it. A test object has quite a few attributes, here are some of the more important ones:

| Attribute | Detail |
| ------ | ------ |
| `test.name` | This will hold the name of the test provided it was specified in the test config. |
| `test.scheduler` | This will hold the scheduler specified in the test config. | 
| `test.id` | This is the pavilion test ID. |
| `test.status` | This will return a status object for the given test. |

You can access the most recent status object of the test by calling `status = test.status.current()`. This also has a few attributes that allow you to extract relevant status information, like:

| Attribute | Detail |
| ------ | ------ |
| `status.state` | Returns the state of the test object. |
| `status.when` | Returns the time stamp of this status object. | 
| `status.note` | Returns any additional collected information on the test. |

An example of using the different attributes and methods can be seen below, this is a simplified version of what is being done in the pavilion cancel command. 
```python
test_object_list, test_failed_list = series.test_obj_from_id(pav_Cfg, test_list)
for test in test_object_list:
    # Requires that the schedulers module be loaded
    scheduler = schedulers.get_scheduler_plugin(test.scheduler)
    status = test.status.current()
    if status.state != STATES.COMPLETE:
        sched.cancel_job(test)
```
