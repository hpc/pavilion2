Table Result Parser
===================

The table result parser attempts to convert tables found in the output
into either a dictionary of lists or dictionary of dictionaries
(depending on whether or not there is a column that labels rows).

+--------------+--------------------+--------------------+------------------+
| Config Item  | Description        | Required?          | Notes            |
+--------------+--------------------+--------------------+------------------+
| start_re     | Partial regex      | No                 | regex            |
|              | near start of      |                    |                  |
|              | table.             |                    |                  |
+--------------+--------------------+--------------------+------------------+
| nth_start_re | Nth `start_re`     | No.                | '0' is first     |
|              | Pavilion           |                    | occurrence       |
|              | needs to           | Default is         |                  |
|              | consider           | first occurrence.  |                  |
+--------------+--------------------+--------------------+------------------+
| line_num     | Number of lines    | No                 | Recommendation:  |
|              | after `start_re`   |                    | if exact         |
|              | that Pavilion      |                    | number of        |
|              | should look at.    |                    | lines after      |
|              |                    |                    | `start_re`       |
|              |                    |                    | is unknown, try  |
|              |                    |                    | to overestimate. |
+--------------+--------------------+--------------------+------------------+
| row_ignore   | Indices of rows    | No                 | The row with     |
|              | to ignore.         |                    | column names     |
|              |                    |                    | count            |
|              |                    |                    | as part of       |
|              |                    |                    | the table        |
|              |                    |                    | (0th row).       |
+--------------+--------------------+--------------------+------------------+
| delimiter    | Delimiter that     | No.                | regex            |
|              |                    | Default is ' '     |                  |
|              | splits the data.   |                    |                  |
+--------------+--------------------+--------------------+------------------+
| col_num      | Number of columns  | Yes                | If a column for  |
|              | in table.          |                    | row names exist, |
|              |                    |                    | include that.    |
+--------------+--------------------+--------------------+------------------+
| has_header   | Set True if there  | No.                | True:            |
|              | is a column        | Default is 'False' | dictionary of    |
|              | for row names.     |                    |                  |
|              |                    |                    | dictionaries     |
|              |                    |                    |                  |
|              |                    |                    | False:           |
|              |                    |                    | dictionary of    |
|              |                    |                    |                  |
|              |                    |                    | lists            |
+--------------+--------------------+--------------------+------------------+
| col_names    | List of column     | No                 | Length of list   |
|              | names, if any.     |                    | must match       |
|              |                    |                    | col_num          |
+--------------+--------------------+--------------------+------------------+
| by_column    | Set True if user   | No.                |                  |
|              | wants to           | Default is 'False' |                  |
|              | organize           |                    |                  |
|              | dictionaries       |                    |                  |
|              | by column.         |                    |                  |
+--------------+--------------------+--------------------+------------------+

Example Tables
--------------

Table without row label column
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following table will be converted into a dictionary of lists

.. code:: bash

   Col 1 | Col2 | Col3
   --------------------
   data1 |  3   | data2
   data3 |  8   | data4
   data5 |      | data6

The config should have the following set:

.. code:: yaml

   result_parse:
       table:
            table_key1:
              delimiter: '\|'
              col_num: 3

Result:

.. code:: python

   { 'Col1': ['data1', 'data3', 'data5'],
    'Col2': ['3', '8', ' '],
    'Col3': ['data2', 'data4', 'data6']

Table with row label column
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following table will be converted into a dictionary of dictionaries.

.. code:: bash

         | Col1  | Col2 | Col3
   ==============================
   row1  | data1 | 3    | data2
   row2  | data3 | 8    | data4
   row3  | data5 |      | 9

The config should have the following set:

.. code:: yaml

   result_parse:
       table:
           table_key2:
               delimiter: '\|'
               col_num: 4
               has_header: True

Result:

.. code:: python

   {
    'Col1': {'row1': 'data1', 'row2': 'data3', 'row3': 'data5'},
    'Col2': {'row1': '3', 'row2': '8', 'row3': ' '},
    'Col3': {'row1': 'data2', 'row2': 'data4', 'row3': '9'}
    }

Long output with multiple tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some tests will output multiple tables that have similar formats. Telling
Pavilion how to parse these tables may be a little more involved.

Consider a test with the following output:

.. code:: bash

  Benchmark: Description of test and explanation of tables found in output.

  #---------------------------------------------------
  # TableTitle Z4321
  #---------------------------------------------------
  column1   column2   column3   column4
  -------   -------   -------   -------
  0           A         1.11      0
  2           B         2.22      0
  4           C         3.33      0
  8           D         4.44      0
  16          E         5.55      1
  Not       part         of      table

  < more output >

  #---------------------------------------------------
  # TableTitle Y8765
  #---------------------------------------------------
  column1   column2   column3   column4
  -------   -------   -------   -------
  0           J         0.11      0
  2           I         4.22      0
  4           H         8.33      1
  8           G         12.44     0
  16          F         16.55     0
  Not       part         of      table

  < more output >

  #---------------------------------------------------
  # TableTitle M1001
  #---------------------------------------------------
  column1   column2   column3   column4
  -------   -------   -------   -------
  0           K         1.10      0
  2           M         2.02      1
  4           O         0.33      0
  8           P         4.04      0
  16          R         5.50      0
  Not      part         of      table

  < more output >

The config might look something like:

.. code:: yaml

  result_parse:
      table:
          y_table:

              # STEP 1: we have to tell Pavilion where the table is in the
              # output.

              # We want Pavilion to look for lines that have the following regex
              start_re: '^# TableTitle*'

              # We want the second occurrence
              nth_start_re: 1

              # The actual table (including row with column names) actually
              # starts 1 line after `start_re`
              start_skip: 1

              # The table (including the row with column names) is 7 lines long.
              # This is so that Pavilion knows that the line containing
              # 'Not part of table' isn't actually part of the table.
              line_num: 7

              # STEP 2: Now that Pavilion has an idea of where the table is in
              # the output, we can tell Pavilion which rows we want to ignore.

              # We want Pavilion to ignore the second row (the row after the
              # row with column names) since it doesn't have any useful
              # information.
              row_ignore: 1

              # STEP 3: Now we can tell Pavilion how to parse the table
              delimiter: '\s+'
              col_num: 4
              has_header: True
              col_names:
                - column1
                - column2
                - column3
                - column4

The resulting dictionary will look like:

.. code:: python

    {
    '0': {'column2': 'J', 'column3': '0.11', 'column4': '0'},
    '16': {'column2': 'F', 'column3': '16.55', 'column4': '0'},
    '2': {'column2': 'I', 'column3': '4.22', 'column4': '0'},
    '4': {'column2': 'H', 'column3': '8.33', 'column4': '1'},
    '8': {'column2': 'G', 'column3': '12.44', 'column4': '0'}
    }
