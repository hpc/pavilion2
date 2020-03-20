import sys

sys.path.append('../../lib')

if len(sys.argv) > 1:
    seed = int(sys.argv[1])
else:
    seed = 0

import random
random.seed(seed)
words = [w.strip() for w in open('/usr/share/dict/american-english').readlines()
         if len(w.strip()) > 2]

import pavilion
from pavilion.output import ANSIString, draw_table


column_widths = [(1,10), (5,20), (10,40), (20,40), (80,200)]
col_names = ['a'*5, 'b'*5, 'c'*20, 'd'*10, 'e'*20]
colors = [33, None, 34, None, 36]
num_rows = 30

rows = []
for row_i in range(num_rows):
    row = {}
    for col_i in range(len(column_widths)):
        col_data = []
        target_width = random.randint(*column_widths[col_i])
        color = colors[col_i]

        text = [random.choice(words)]
        while len(' '.join(text)) < target_width:
            text.append(random.choice(words))
        row[col_names[col_i]] = ANSIString(' '.join(text), code=color)
    rows.append(row)

import cProfile
import pstats
        
cProfile.run('draw_table(sys.stdout, {}, col_names, rows)', 'pav.pstats')
p = pstats.Stats('pav.pstats')
p.sort_stats('cumulative').print_stats(10)
p.sort_stats('tottime').print_stats(10)
