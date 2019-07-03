# Test Results

Every successful test run generates a set of results in JSON. These are saved 
with the test, but are also logged to a central `results.log` file that is 
formatted in a Splunk compatible manner. 

These results contain several useful values, but that's just the beginning. 
[Result Parsers](#result-parsers) are little parsing scripts that can configured
 to parse data from your test's output files. They're designed to be simple 
 enough to pull out small bits of data, but can be combined to extract a 
 complex set of results from each test run. Each result parser is also a 
[plugin](../plugins/result_parsers.md), so you can easily add custom parsers
for tests with particularly complex results.

 - [Basic Result Keys](#basic-result-keys)
 - [Using Result Parsers](#using-result-parsers)

## Basic Result Keys
These keys are present in the results for every test, whether the test passed
 or failed. 
 
 - __name__ - The name of the test.
 - __id__ - The test's run id.
 - __created__ - When the test run was created. 
 - __started__ - When the test run actually started running in a scheduled 
 allocation.
 - __finished__ - When the test run finished.
 - __duration__ - How long the test ran. Examples: `0:01:04.304421` or 
 `2 days, 10:05:12.833312`
 - __result__ - The PASS/FAIL result of the test.
 
All time fields are in ISO8601 format, with timezone offsets.
 
#### result
The 'result' key denotes the final test result, and will always be either 
'__PASS__' or '__FAIL__'.  

By default a test passes if it's run script returns a zero result, which 
generally means the last command in the test's `run.cmds` list also returned 
zero.

Result Parsers may override this value, but they must be configured to return
a single True or False result. Anything else results in a __FAIL__. 

When using the result key the 'store_true' and 'store_false' 
[actions](#actions) are the only valid choices. Any other action will be 
changed to 'store_true', and the change will be noted in the result errors. 
Similarly, [per_file](#per_file) can only have a setting that produces a 
single result ('store_first' is forced by default).

## Using Result Parsers

The `results` section of each test config lets us configure additional result
 parsers that can pull data out of test output files. By default each parser 
 reads from the run log, which contains the stdout and stderr from the run 
 script and your test.
 
```yaml
mytest:
  scheduler: raw
  run:
    cmds:
      - ping -c 10 google.com
   
  results:
    # The results section is comprised of configs for result parsers,
    # identified by name. In this case, we'll use the 'regex' parser.
    regex: 
      # Each result parser can have multiple configs.
      - {
        # The value matched will be stored in this key
        key: loss
        # This tells the regex parser what regular expression to use.
        # Single quotes are recommended, as they are literal in yaml.
        regex: '\d+% packet loss'
      }
      - {
        # We're storing this value in the result key. If it's found 
        # (and has a value of 'True', then the test will 'PASS'.
        key: result
        regex: '10 received'
        # The action denotes how to handle the parser's data. In this case
        # a successful match will give a 'True' value.
        action: store_true
      }
``` 

The results for this test run might look like:
```json
{
  "name": "mytest",
  "id": 51,
  "created": "2019-06-18 16:00:35.692878-06:00",
  "started": "2019-06-18 16:00:36.744221-06:00",
  "finished": "2019-06-18 16:01:39.997299-06:00",
  "duration": "0:01:04.304421",
  "result": "PASS",
  "loss": "0% packet loss"
}
```

### Actions

We saw in the above example that we can use an __action__ to change how the 
results are stored. There are several additional __actions__ that can be
selected:

  - __store__ - (Default) Simply store the result parser's output.
  - __store_true__ - Any result that evaluates to `True` in python is True, 
    otherwise this is `False`. Generally this means the result is true if the
    parser found one or more things.
  - __store_false__ - The opposite of __store_true__
  - __count__ - Count the number of items matched.

### Files

By default, each result parser reads through the test's `run.log` file. You 
can specify a different file, a file glob, or even multiple file globs to 
match an assortment of files. 

If you need to reference the run log in addition to other files, it is one 
directory up from the test's run directory, in `../run.log`.

This test runs across a bunch of nodes, and produces an output file for each.

```yaml
mytest2: 
    scheduler: slurm
    slurm: 
      num_nodes: 5
    
    run:
      cmds:
        - srun "hostname > 
        
```

