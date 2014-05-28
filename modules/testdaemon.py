#!python

''' a test  '''

import daemon
import time
import sys,os

def do_something():
    print sys.argv
    while True:
        with open("/tmp/td.txt", "w") as f:
            f.write("The time is now " + time.ctime())
        time.sleep(5)


def main():
    # set up log file
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        log = open('td.log', 'w+')
    except:
        print "Error, can't open log file td.log"
    #print dir(daemon)
    with daemon.DaemonContext(working_directory=here, pidfile='/tmp/td.pid', stdout=log, stderr=log):
        do_something()

if __name__ == "__main__":
    main()
    #sys.exit(main(sys.argv[1:]))
