#Pavilion Result Parser Plugins

This page is an overview of result parser plugins and how to write them.

## Writing Result Parser Plugins

Like all [Pavilion plugins](basics.md), a result parser in Pavilion is made up of 
the [source code](#writing-the-source) and 
the [yapsy-plugin](basics.md#plugin_nameyapsy-plugin).

#### Writing the Source

You begin writing the source with the command class definition. We have been 
using the CamelCase naming convention to 
keep everything the same. It is simply:
```python
class ResultParserName(result_parsers.ResultParser):
```

At the minimum each command will require four methods: 
`__init__`, `get_config_items`, `_check_args`, and `__call__`. 

##### Writing `__init__()`:
The `__init__` method should only take one argument, that one argument being 
`self`, as this will be used to initialize the new command. 

In this method, you will call `super().__init__()` and
pass the following arguments: 

* `name`: the name of the result parser (required)
* `description`: a short description of what the result parser does (required)
* `priority`: priorities are explained [here](basics.md#plugin-priorities) 
(optional) (default: `PRIO_COMMON`)
* `open_mode`: how to open each file handed to paresr (optional) (deault: `'r'`)

Below is the constant result parser's `__init__` method:
```python
def __init__(self):
    super().__init__(
        name='constant'
        descrption='Insert a constant into the results.')
```

##### Writing `get_config_items`:

The `get_config_items` method also takes in only one argument, self. 
This method gets the config of this particular result parser and returns 
the items in a list. The user can extend the possible configuration items for 
the specific result parser. For example, the constant result parser needs 
a user-defined constant in the configuration file. 

Below the constant result parser's `get_config_items` method:
```python
def get_config_items(self):
    config_items = super().get_config_items()
    config_items.extend([
        yc.StrElem(
            'const', required=True,
            help_text="Constant that will be placed in result"
        )
    ])
    
    return config_items
```

##### Writing `_check_args()`:

The `_check_args` is an optional method takes in `self` as an argument as well 
as every config key (see [get_config_items](#get_config_items)). The values 
of each config key is passed as a keyword argument. Here is an
example of a `_check_args` method that checks the list `row_names` from a config
 is at least the expected size:

```python
def _check_args(self, row_names=None):
    if len(row_names) is not 4:
        raise result_parsers.ResultParserError(
            "row_names list size needs to be at least 4"
        )
```

##### Writing `__call__`:

The `__call__` method is where the result parser is actually implemented. 
The method takes in the same arguments as `_check_args` 
as well as `test`, and `file` as positional arguments.

It is not necessary to return anything but if you need to have something 
recorded in the `results.json`, the return value will be stored in 
whatever key you specified.

One simple use of the `__call__` method that does not 
have any elements is the following:
```python
def __call__(self, test, file):
    return 0
```dbg_print(str(tests_only))

