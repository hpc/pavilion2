"""Parse JSON from file."""

import json
import re

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
                              "Example: '[key1, key2.subkey]'"
                ),
                yc.ListElem(
                    'exclude',
                    sub_elem = yc.StrElem(),
                    help_text="Exclude this key."
                              "Example: '[key1, key2.subkey]'"
                ),
                yc.StrElem(
                    'stop_at',
                    help_text="The line after the final line of JSON to be parsed."
                    "If the results contain more than just pure JSON, use the preceded_by"
                    "option to mark where the JSON begins and this option to mark where"
                    "the JSON ends."
                    "Example: \"a string of text\""
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
        

    def parse_json(self, file, stop_at):
        _ = self

        if stop_at is None:
            try:
                return json.load(file)
            except json.JSONDecodeError as err:
                raise ValueError(
                    "Invalid JSON: '{}'"
                    .format(err)
                )
        
        else:
            lines = []
            for line in file:
                if re.search(stop_at, line):
                    break
                lines.append(line)
            json_string = ''.join(lines)

            try:
                json_object = json.loads(json_string)
            except json.JSONDecodeError as err:
                raise ValueError(
                "Invalid JSON: '{}'"
               .format(err)
            )

            return json_object


    def exclude_keys(self, old_dict, keys):
        _ = self

        for key in keys:
            path = key.split(".")
            try:
                old_dict = self.remove_key(old_dict, path)
            except (TypeError, KeyError) as err:
                raise ValueError(
                    "Key {} doesn't exist"
                    .format('.'.join(path))
                )
        
        return old_dict


    def remove_key(self, old_dict, path):
        _ = self

        if len(path) == 1:
            del old_dict[path[0]]
            return old_dict
        else:
            old_dict[path[0]] = self.remove_key(old_dict[path[0]], path[1:])
            return old_dict


    def include_only_keys(self, old_dict, keys):
        _ = self

        key_paths = [key.split(".") for key in keys]
        new_dict = {}
        for path in key_paths:
            current_new = new_dict
            current_old = old_dict
            for index, part in enumerate(path):
                if part not in current_new:
                    if index == len(path) - 1:
                        try:
                            current_new[part] = current_old[part]
                        except (TypeError, KeyError) as err:
                            raise ValueError(
                                "Key {} doesn't exist"
                                .format('.'.join(path))
                            )
                    else:
                        current_new[part] = {}
                current_new = current_new[part]
                current_old = current_old[part]
        
        return new_dict