
from pavilion import config
import argparse
import sys

parser = argparse.ArgumentParser(
    description="Finds the pavilion configuration, and prints the asked for "
                "config value.")
parser.add_argument('keys', nargs='+', action="store",
                    help="The config key to look up.")

args = parser.parse_args()

try:
    pav_cfg = config.find_pavilion_config(warn=False)
except Exception as err:
    print(err, file=sys.stderr)
    sys.exit(1)

values = {}
for key in args.keys:
    if key in pav_cfg:
        value = pav_cfg.get(key)
        if value is None:
            value = ''
        values[key] = value

    else:
        print("No such config key: '{}'".format(key), file=sys.stderr)
        sys.exit(1)

for key, value in values.items():
    print('{}:{}'.format(key, value))
