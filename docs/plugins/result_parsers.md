# Pavilion Result Parser Plugins

This page is an overview of result parser plugins and how to write them.

## Writing Result Parser Plugins

A result parser in Pavilion is made up of two seperate parts, the [source code](#writing-the-source) and the [yapsy-plugin](#writing-the-yapsy-plugin).

#### Writing the Source

You begin writing the source with the command class definition. We have been using the CamelCase naming convention to keep everything the same. It is simply:
```python
class ResultParserName(result_parsers.ResultParser):
```

At the minimum each command will require four methods: `__init__`, `get_config_items`, `_check_args`, and `__call__`. 

##### Writing `__init__()`:
The `__init__` method should only take one argument, that one argument being self, as this will be used to initialize the new command. 

In this method you will call `super().__init__()` and pass the name of the result parser. It can also take in an `open_mode` and `priority` argument, but these are optional. Below is an example of a command's `__init__` method:
```python
def __init__(self):
    super().__init__(name='resultparsername')
```

##### Writing `get_config_items`:

The `get_config_items` method also takes in only one argument, self. This method gets the config of this particular result parser and returns the items in a list.

```python
def get_config_items(self):
    config_items = super().get_config_items()
    config_items_extend([
        yc.StrElem(
            'result_parser_string'
        ),
        yc.ListElem(
            'result_parser_list'
        )
    ])
    
    return config_items
```

##### Writing `_check_args()`:

The `_check_args` is an optional method takes in `self` as an argument as well as every config key (see [get_config_items](#get_config_items)).

##### Writing `__call__`:

The `__call__` method is where the result parser is actually implemented. The method takes in the same arguments as `_check_args` as well as `test`, and `file`. 

It is not necessary to return anything but if you need to have something recorded in the `results.json`, the return value will be stored in whatever key you specified.

One simple use of the `__call__` method that does not have any elements is the following:
```python
def __cal__(self, test, file):
    return 0
```

#### Writing the yapsy-plugin

Writing the yapsy-plugin is quite simple. Below is an example:
```
[Core]
Name = Result Parser Name
Module = module_name

[Documentation]
Description = <put your description ehre>
Author = 
Version = 1.0
Website
```
