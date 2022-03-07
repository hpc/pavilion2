"""Parse JSON from file."""

import json

import yaml_config as yc
from . import base_classes 


class Json(base_classes.ResultParser):
    """Parse json from file and return as json"""

    def __init__(self):
        super().__init__(
            name='json',
            description="Includes all keys by default",
            config_elems=[
                yc.ListElem(
                    'include_only',
                    sub_elem = yc.StrElem(),
                    help_text="Include this key and exclude all others"
                ),
                yc.ListElem(
                    'exclude',
                    sub_elem = yc.StrElem(),
                    help_text="Exclude this key"
                ),
                yc.StrElem(
                    'stop_at',
                    help_text="The line after the final line of json"
                )
            ]
        )

    def parse_json(self, file, stop_at):
        json_string = file.read()

        if not stop_at is None:
            #throw a heads up here if "stop_at" isn't in json_string
            json_string = json_string.split(stop_at)[0]

        # make this into an actual exception
        try:
            json_object = json.loads(json_string)
        except:
            print("Error: This doesn't appear to be valid JSON. Returning None.")
            json_object = None

        return json_object



    def dict_merge(self, dict1, dict2):
        #From https://stackoverflow.com/questions/7204805/how-to-merge-dictionaries-of-dictionaries
        for k, v in dict1.items():
            if k in dict2:
                if all(isinstance(e, MutableMapping) for e in (v, dict2[k])):
                    dict2[k] = dict_merge(v, dict2[k])
        dict3 = dict1.copy()
        dict3.update(dict2)
        return dict3


    def include_only_keys(self, json_object, include_only):
        #try:
        dict_list = []
        for i, key in enumerate(include_only):
            includeonlypath = include_only[i].split(".")
            dict_list.append(self.get_key(json_object, includeonlypath))
        json_object = {}
        for i, key in enumerate(dict_list):
            json_object = self.dict_merge(json_object, dict_list[i])
        return json_object
#        except: #make this into an actual exception
#            #"either this key doesn't exist, or you excluded it."
#            print("ERROR: You tried to include_only a key that doesn't exist. Returning None.")
#            return('blahblah')

    def get_key(self, json_dict, includeonlypath):
        if len(includeonlypath) == 1:
            return {includeonlypath[0]: json_dict[includeonlypath[0]]}
        else:
            return {includeonlypath[0]: self.get_key(json_dict[includeonlypath[0]], includeonlypath[1:])}




    def exclude_keys(self, json_object, exclude):
        try:
            for i, key in enumerate(exclude):
                exclude_path = exclude[i].split(".")
                json_object = self.remove_key(json_object, exclude_path)
            return json_object
        except: #make this into an actual exception
            print("ERROR: You tried to exclude a key that doesn't exist. Returning None.")
            return None


    def remove_key(self, json_dict, exclude_path):
        if len(exclude_path) == 1:
            del json_dict[exclude_path[0]]
            return json_dict
        else:
            json_dict[exclude_path[0]] = self.remove_key(json_dict[exclude_path[0]], exclude_path[1:])
            if json_dict[exclude_path[0]] is None: #make this into an actual exception
                return None
            else:
                return json_dict


    def __call__(self, file, include_only=None, exclude=None, stop_at=None):

        json_object = self.parse_json(file, stop_at)

        if json_object is None:
            return None

        if not exclude is None:
            json_object = self.exclude_keys(json_object, exclude)
        if not include_only is None:
            json_object = self.include_only_keys(json_object, include_only)

        return json_object