# Paths Follow Identity and Content Type, Not Category

Status: Accepted

Source Location is taken only from the Product Definition, Normalized Input paths are derived canonically from language and resource identity, pricing outputs always use `pricing/`, and Support Article outputs use their Support Article Type. Catalog Category remains a validated metadata view and never supplies or changes a physical path. Missing, case-mismatched, escaping, or colliding paths and undeclared source reuse are blocking consistency errors; reuse is allowed only through an explicit Source Alias, because inferring paths from categories or filenames would create a second, ambiguous source of identity.
