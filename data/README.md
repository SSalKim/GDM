# Weather Lab ATCF archive

Canonical paths: `forecast_files/YYYY/MM/DD/<MODEL>_YYYY_MM_DDTHH_00_atcf_a_deck.txt`
from the repository root, with MODEL equal to GENC, FNV3 or WNV3.
Each text file preserves the upstream header and ATCF body. Its adjacent JSON
records the upstream model version, exact cycle, SHA-256 and row count.
`latest.json` points to the latest validated cycle independently for each model.

Historical `forecast_files/YYYY_MM_DD/` entries move into the nested date paths
without changing their content or filenames. Update consumers to the new URLs.
