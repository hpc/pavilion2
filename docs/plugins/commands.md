# Pavilion Command Plugins

This page is an overview of command plugins and how to write them.

#### Contents


## Writing Command Plugins

A command in Pavilion is made up of two seperate parts, the [source code](#writing-the-source) and the [yapsy-plugin](#writing-the-yapsy-plugin).

#### Writing the Source

The first thing to worry about when writing a command would be what to import. This is rather easy to answer since the only meaningful required import be `from pavilion import commands`, since this will allow a new command to inherit from the commands class. After importing this, you can really import anything else
that would be necessary for a new command.

After this you start the command class definition. We have been using a simple naming convention to keep everything the same. It is simply:
```python
class NameCommand(commands.Command):
```

At the minimum each command will require three methods: `__init__`, `_setup_arguments`, and `run`. 

##### Writing `__init__()`:
The `__init__` method should only take one argument, that one argument being self, as this will be used to initialize the new command. 

In this method you will call `super().__init__()` and pass in the following arguments in this order: name, help string, and short_help = help string. The `super()` is used to tell the `__init__` method to inherit the `__init__` method from the super class, in this case the commands.Command class. Below is an example of a command's `__init__` method:
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

In this method we add the valid arguments that can be used when calling your command. Each argument will need to have an action (I have only ever used store and store_true) and help text. Each argument also has the potential to have a nargs field, or default field. These would allow you to specify the number of arguments allowed and the default value of an argument, repsectively. 

To add a parser argument we use the following syntax:
```python
    parser.add_argument(<ARGUMENTS>)
```

Again, you can provide a bunch of different arguments to this call, so I have provided two examples below. If there isn't enough here or you can't find something you're looking for give `show.py` a look.
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

You can access specific arguments using the `args` object. Each argument added to the parser will have its own section and therefore can be accessed simply by, `args.argument`. For example, if you wanted to get the list of tests provided when the command was run you would reference the list by `args.tests`. Note, for flags like `-s` you get the name of the argument from the long name, i.e. `--status` specifies that `args.status` will hold the information required for the status argument (in this case it will be a bool value).

When working with tests (I believe just about every command will be), you need to remember that the arguments are strings. Because of this you will need to import additional libraries, most importantly `from pavilion.pav_test import PavTest`, to allow yourself the ability to access the actual test object. If you anticipate using series as well it will also be important to add `from pavilion import series`. Below is some sample code used to generate the lists of tests provided by `args.tests` including the ability to extract those in a test series.
```python
for test_id in args.tests:
    if test_id.startswith('s'):
        test_list.extend(series.TestSeries.from_id(pav_cfg,int(test_id[1:])).tests)
    else:
        test_list.append(test_id)
```
This code will populate a list of all test IDs, but they are still strings so you will need to do the following to get each test object.
```python
test_list = map(int, test_list) # Used to map strings to integers
for test_id in test_list:
    test = PavTest.load(pav_cfg, test_id)
```

Keep in mind that it may be neccesary to wrap everything in `try except` blocks to catch any errors that may occur, i.e. a test or test series doesn't exist. There are some good examples of this in both the `status.py` as well as the `cancel.py` files.

#### Writing the yapsy-plugin

To initialize the command in the list of available commands to run with Pavilion, Pavilion requires it has an accompanying `.yapsy-plugin` file. Without this the new command will not work. 

The yapsy-plugin file is rather straightforward though. It should be named the exact same way as the source `.py` file (I am not sure if this is required for it to work or if it's a Pavilion naming convention thing). It should also contain the following information in this format:
```
[Core]
Name = Command Name
Module = the name of the source or how you'll call the command

[Documentation]
Description = What the command does
Author = 
Version = 
Website = 
```
