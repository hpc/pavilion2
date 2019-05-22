
from pavilion import config
import argparse
import sys

parser = argparse.ArgumentParser(
    description="Finds the pavilion configuration, and prints the asked for "
                "config value.")
parser.add_argument('key', nargs=1, action="store",
                    help="The config key to look up.")

args = parser.parse_args()
key = args.key[0]

try:
    pav_cfg = config.find(warn=False)
except Exception as err:
    print(err, file=sys.stderr)
    sys.exit(1)

if key in pav_cfg:
    value = pav_cfg[key]
    if value is not None:
        print(pav_cfg[key])
else:
    print("No such config key: '{}'".format(key), file=sys.stderr)
    sys.exit(1)
