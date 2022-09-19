# Flux Framework Tutorial

This is a demo that will show how to use pavilion with [Flux Framework](https://github.com/flux-framework/).
First, build the container here from the root of pavilion2.

```bash
$ docker build -f examples/flux/Dockerfile -t flux-pavilion .
```

Then shell inside, optionally binding the present working directory if you want to develop.

```bash
$ docker run -it -v $PWD:/code flux-pavilion
$ docker run -it flux-pavilion
```

You should find the pav executable on your path.

```bash
$ which pav
/code/bin/pav
```

And run the activate script:

```bash
./activate.sh
```

And then show tests available:

```bash
# pav show tests
 Available Tests                          
-------------------------------+---------
 Name                          | Summary 
-------------------------------+---------
 flux-example.variable-formats |         
 vars-example.variable-formats |  
```

Run the test vars-example (non-flux scheduler) test:

```bash
# pav run vars-example
Creating Test Runs: 100%
Building 1 tests for test set cmd_line.
BUILD_SUCCESS: 1                                                                
Kicked off test 1 for test set 'cmd_line' in series s7.
```

We can now see schedulers! Notice that flux is one of them.

```bash
n# pav show sched
 Available Scheduler Plugins                                
-------+---------------------------------------------------
 Name  | Description                                       
-------+---------------------------------------------------
 raw   | Schedules tests as local processes.               
 slurm | Schedules tests via the Slurm scheduler.          
 flux  | Schedules tests via the Flux Framework scheduler. 
```

Now let's run the test with flux!

```bash
# pav run flux-example
```

