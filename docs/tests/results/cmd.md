# Command Result Parser (cmd)

The command result parser runs a given command and puts the result of the
command into the results. The result of the command can either be the output or
the return value. 

| Additional Key  | Description | Required/Optional | Notes | 
| ------------- | ------------- | ------------- | ----------|
| command | command that will be run  | Required | 
| success | what the result parser looks at | Optional, default:`return_value` | Can either be `output` or `return_value`
|stderr_out | where stderr will be redirected | Optional, default: `stdout` | Can either be `null` or `stdout`


Example:
```
results:
    command: 
        key: cmd
        command: "abc"
        success: "return_value"
```

The `results.json` will look something like this:
`{"cmd": "127", "result": "PASS",  "name": "cmd_rp_test"}`. The key `cmd` has a 
value of `127` because `abc` is not a real command and therefore returned the 
error code 127.
