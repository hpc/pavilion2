from pavilion.test_config import parsers

parser = parsers.get_expr_parser(debug=True)

tree = parser.parse('a*b+c == d < 7 - -e')
print(tree)
