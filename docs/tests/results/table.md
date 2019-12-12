# Table Result Parser

The table result parser attempts to convert tables found in the output into 
either a dictionary of lists or dictionary of dictionaries (depending on
whether or not there is a column that labels rows). 

| Config Item | Description | Required? | Notes
| ----------- | ----------- | --------- | ------|
| delimiter| Delimiter that splits the data | no, default=' ' | regex form
| col_num | Number of columns, including row label if there is one | yes
| has_header | Set True if there is a column of row_names | no, default=False
| col_names | Column names if you know what they are | no | useful if output doesn't include column names

## Example Tables

### Table without row label column
The following table will be converted into a dictionary of lists
```bash
Col 1 | Col2 | Col3 
--------------------
data1 |  3   | data2
data3 |  8   | data4
data5 |      | data6
```

The config should have the following set:
```yaml
results:
    table:
        key: table
        delimiter: '\\|'
        col_num: 3
```

Result:
```python
{ 'Col1': ['data1', 'data3', 'data5'],
 'Col2': ['3', '8', ' '],
 'Col3': ['data2', 'data4', 'data6']
```

### Table with row label column
The following table will be converted into a dictionary of dictionaries.

```bash
      | Col1  | Col2 | Col3
==============================
row1  | data1 | 3    | data2
row2  | data3 | 8    | data4
row3  | data5 |      | 9 
```


The config should have the following set:
```yaml
results:
    table:
        key: table
            delimiter: '\\|'
            col_num: 4
            has_header: True
```

Result:
```python
{ 
 'Col1': {'row1': 'data1', 'row2': 'data3', 'row3': 'data5'},
 'Col2': {'row1': '3', 'row2': '8', 'row3': ' '},
 'Col3': {'row1': 'data2', 'row2': 'data4', 'row3': '9'}
 }
```