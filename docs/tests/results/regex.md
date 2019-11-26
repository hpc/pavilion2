# Regex Result Parser (regex)

Finds matches to the given regex in the results file. The matched string/s is/are
returned as the result. 

| Additional Key | Description | Required/Optional | Notes                    |
| -------------- | ------------| ----------------- | -------------------------|
| regex          | Python regex to use to search file | Required | |
|threshold | Looks at the number of instances of the regex | Optional, default: 0
| expected | Expected value or range(s) | Optional | 


Example:
```
results:
    regex:
        key: result
        regex: "<results> PASSED"
        action: "store_true"
```