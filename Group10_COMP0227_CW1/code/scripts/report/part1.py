"""Render the Part 1 tables used in the report."""
from _cli import CODE,arguments
from _tables import part1
a=arguments(__doc__)
part1(CODE,a.out)
print('Rendered Part 1 tables in',a.out)
