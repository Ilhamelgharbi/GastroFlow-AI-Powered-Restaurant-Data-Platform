# `restaurants.csv`

Rows: **148,541**. The first exported index column was removed during
sanitization.

| Field | Description / audit note |
|---|---|
| `id` | Restaurant identifier; unique in the audited file. |
| `name` | Restaurant name; 86 null or blank values. |
| `city` | Restaurant location; 101,712 values contain a comma. Confirm the source's area/city convention before splitting. |
| `rating` | Source rating; 86 null or blank values and 87,014 values equal `--`. |
| `rating_count` | Source rating-count field; 86 null or blank values. The audit's integer cast check returned 148,541 non-castable values; investigate the source representation before defining a type. |
| `cost` | Source cost field; 131 null or blank values and 148,410 values contain `₹`. |
| `cuisine` | Cuisine information; 99 null or blank values. |
| `lic_no` | Source license-number field; 229 null or blank values. |
| `link` | Source link or URL field. |
| `address` | Address; 86 null or blank values. |
| `menu` | Source menu field; inspect its representation before transformation. |
