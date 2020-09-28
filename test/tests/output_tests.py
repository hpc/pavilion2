from pavilion.unittest import PavTestCase
from pavilion import output
import time
import random


class OutputTests(PavTestCase):
    """Test all the various functions in our output library."""

    def test_draw_table(self):
        """Exercise draw_table in many ways."""

        # We can't actually check that the output looks ok, but we
        # can at make sure it doesn't throw errors by testing a wide combination
        # of things.

        # Dump all the output here.
        dev_null = open('/dev/null', 'w')

        words = [word.strip() for word in
                 (self.TEST_DATA_ROOT/'words').open().readlines()]

        # Choose random column header names
        columns = [random.choice(words) for i in range(20)]

        field_info = {
            # Column 0-2 have a max width. We put this one first to test the
            # case where all columns have hit their max width.
            columns[0]: {'max_width': 10},
            columns[1]: {'max_width': 10},
            columns[2]: {'max_width': 10},
            # Column 3 is capitalized (test transforms)
            columns[3]: {'transform': lambda s: s.capitalize()},
            # Column 1 is specially formatted
            columns[4]: {'format': '"{}"'},
            # Column 2 has a title
            columns[5]: {'title': columns[2].capitalize()},
            # Column 4 has a min width.
            columns[6]: {'min_width': 10},
        }

        count = 0
        timer = 0
        for col_count in range(1, 11, 3):
            table_width = 20

            while table_width < 200:
                data_sizes = {
                    col: random.randint(1, 100) for col in columns[:col_count]
                }

                rows = []
                for i in range(5):
                    row = {}
                    for col in columns[:col_count]:
                        data = [random.choice(words)
                                for i in range(data_sizes[col])]
                        row[col] = ' '.join(data)
                    rows.append(row)

                # Randomly assign a title.
                title = None if random.randint(0, 1) == 0 else 'Title'
                pad = random.randint(0, 1) == 0
                border = random.randint(0, 1) == 0
                args = (dev_null, columns[:col_count], rows)
                kwargs = {
                    'field_info': field_info,
                    'table_width': table_width,
                    'title': title,
                    'pad': pad,
                    'border': border}
                start = time.time()
                output.draw_table(*args, **kwargs)
                timer += time.time() - start
                count += 1

                try:
                    table_width += random.randint(10, 50)
                except:
                    import traceback
                    traceback.print_exc()
                    self.fail("Raised an error while rendering a table. "
                              "args: {}, kwargs: {}".format(args, kwargs))

        self.assertLess(timer/count, .3, "Per table draw speed exceed 30 ms")
