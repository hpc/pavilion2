from pavilion.test_config import parsers

expr_parser = parsers.get_expr_parser(debug=True)

expressions = [
    'sys.sys_name.0.blargl + foo.0 * 37 * -blarg(berries, chickens)',
    '',
    'sys.sys_name.blarg',
    'sys.sys_name.0',
    'sys.sys_name',
    'sys_name.0.blarg',
    'sys_name.blarg',
    'sys_name.0',
    'sys_name',
    'sys_name.*',
    'sys_name.*.blarg == 3',
    'flargl + flargl(blargl.3 + 3/margl, 7.3)',
    'e == 7 != 8 < 12 > b <= m >= 10',
]   

strings = [
    '',
    'hello world',
    'hello\nworld',
    'hello \\{ world',
    'hello {{this is an expr 1234.3}} world',
]

# Add "hello {{<expr>}} world" for each of the above expressions.
for expr in expressions:
    strings.append("hello {{{{{}}}}} world".format(expr))


for expr in expressions:
    print("Checking expr: '{}'".format(expr))
    print(expr_parser.parse(expr).pretty())

#for string in strings:
#    print(string_parser.parse(string).pretty())

# It's also important to come up with strings that should fail.
# Strings that should fail.
bad_strings = [
	'hello {{ foo',    # hanging expression
	'hello [~ foo',    # hanging sub-string
	'{{ expr {{ nope }} }}', # Expressions can't contain expressions.
]

# Bad expressions.

bad_expressions = [
	'a ++ b',
	'a == > c',
]

for bad in bad_strings:
    continue
    try:
        string_parser.parse(bad)
    except:
        pass
    else:
        print("Bad string '{}' failed to fail.")

for bad in bad_expressions:
    try:
        expr_parser.parse(bad)
    except:
        pass
    else:
        print("Bad expr '{}' failed to fail.")
print(tree)
