# Constant Result Parser (const)

The constant result parser simply inserts a constant into the results. The 
constant may reference variables.

This result parser can be used to insert a variable or other information into 
the test results that isn't already there. For example, you can specify who ran 
the test (`{{pav.user}}`) or the host name (`{{sys.sys_name}}`) in the results.

The constant result parser requires one other additional configuration item, 
which is the constant. 

| Config Item | Description | Required? | Notes | 
| ----------- | ----------- | --------- | ------|
| const | constant that will be placed in the results | Required | can be a variable|

Example:
```
results:
    constant:
        key: username
        const: "{{pav.user}} ran this test"
```

The `results.json` will look something like this:
`{"name": "const_rp_test", "result": "PASS", 
"username": "lapid ran this test"}`