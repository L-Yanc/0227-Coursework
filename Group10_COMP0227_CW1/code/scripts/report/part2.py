"""Render the Part 2 tables used in the report."""
from _cli import CODE,arguments
from _tables import part2
a=arguments(__doc__)
part2(CODE,a.out)
print('Rendered Part 2 tables in',a.out)
