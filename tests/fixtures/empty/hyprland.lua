-- A single rule whose match and props are both empty tables, to prove
-- collect.lua serializes them as JSON objects ({}), not arrays ([]).
hl.window_rule({})
