"""Parse JSON from file."""

import json

import yaml_config as yc
from . import base_classes 


class Json(base_classes.ResultParser):
    """Return a JSON dict parsed from the given file according to
     the given keys."""

    def __init__(self):
        super().__init__(
            name='json',
            description="Return a JSON dict parsed from the given file according to"
                        "the given keys. Includes all keys by default.",
            config_elems=[
                yc.ListElem(
                    'include_only',
                    sub_elem = yc.StrElem(),
                    help_text="Include this key and exclude all others."
                              "Looks like: a, b.c, b.d.e"
                ),
                yc.ListElem(
                    'exclude',
                    sub_elem = yc.StrElem(),
                    help_text="Exclude this key."
                              "Looks like: a, b.c, b.d.e"
                ),
                yc.StrElem(
                    'stop_at',
                    help_text="The line after the final line of JSON to be parsed."
                    "If the results contain more than just pure JSON, use the preceded_by"
                    "option to mark where the JSON begins and this option to mark where"
                    "the JSON ends."
                    "Looks like: \"a string of text\""
                )
            ]
        )

    def __call__(self, file, include_only=None, exclude=None, stop_at=None):

        json_object = self.parse_json(file, stop_at)

        if json_object is None:
            return None

        if exclude is not None:
            json_object = self.exclude_keys(json_object, exclude)
        if include_only is not None:
            json_object = self.include_only_keys(json_object, include_only)

        return json_object
        

    # To-do: Raise exception if this fails.
    def parse_json(self, file, stop_at):

        if stop_at is None:
            json_string = file.read()
        else:
            lines = []
            for line in file:
                if stop_at in line:
                    break
                lines.append(line)
            json_string = ''.join(lines)

        json_object = json.loads(json_string)
        # To-do: Raise exception if this isn't valid JSON.

        return json_object


    # To-do: Raise exception if this fails.
    def exclude_keys(self, dictionary, keys):
        for i, key in enumerate(keys):
            path = keys[i].split(".")
            dictionary = self.remove_key(dictionary, path)
        return dictionary


    # To-do: Raise exception if this fails.
    def remove_key(self, dictionary, path):
        if len(path) == 1:
            del dictionary[path[0]]
            return dictionary
        else:
            dictionary[path[0]] = self.remove_key(dictionary[path[0]], path[1:])
            return dictionary
            

    # To-do: Raise exception if this fails.
    def include_only_keys(self, dictionary, keys):
        key_paths = [key.split(".") for key in keys]
        newdict = {}

        for path in key_paths:
            current_newdict = newdict
            current_dictionary = dictionary

            for index, part in enumerate(path):
                if part not in current_newdict:
                    if index == len(path) - 1:
                        current_newdict[part] = current_dictionary[part]
                    else:
                        current_newdict[part] = {}

                current_newdict = current_newdict[part]
                current_dictionary = current_dictionary[part]

        return newdict