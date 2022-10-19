
import yc_yaml as yaml
from . import test_appliance
from . import test_yaml

def main(args=None):
    collections = []
    collections.append(test_yaml)
    return test_appliance.run(collections, args)

if __name__ == '__main__':
    main()

