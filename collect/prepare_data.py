"""Create upload-ready CSV copies while removing sensitive email/password columns."""

import argparse
import csv
import os
import tempfile
from pathlib import Path


SENSITIVE_MARKERS = ("email", "password", "_idx")


def prepare_csvs(input_dir: Path, output_dir: Path) -> int:
    source_dir = input_dir.resolve()
    destination_dir = output_dir.resolve()
    if source_dir == destination_dir:
        raise ValueError("Input and output directories must be different.")
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {source_dir}")

    files = sorted(source_dir.rglob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {source_dir}")

    destination_dir.mkdir(parents=True, exist_ok=True)
    total_rows = 0

    for source in files:
        temporary_path: Path | None = None
        try:
            with source.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                header = next(reader, None)
                if not header:
                    raise ValueError(f"CSV has an empty or invalid header: {source.name}")

                has_exported_index = not header[0].strip()
                header_start = 1 if has_exported_index else 0
                if any(not column.strip() for column in header[header_start:]):
                    raise ValueError(f"CSV has an empty or invalid header: {source.name}")

                keep_indexes = [
                    index
                    for index, column in enumerate(header)
                    if index >= header_start
                    and not any(marker in column.casefold() for marker in SENSITIVE_MARKERS)
                ]
                safe_header = [header[index] for index in keep_indexes]
                if not safe_header:
                    raise ValueError(f"CSV has no usable columns: {source.name}")
                row_count = 0

                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="",
                    dir=destination_dir,
                    prefix=f".{source.stem}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    writer = csv.writer(temporary)
                    writer.writerow(safe_header)
                    for line_number, row in enumerate(reader, start=2):
                        if len(row) != len(header):
                            raise ValueError(
                                f"{source.name}: malformed CSV row at line {line_number}"
                            )
                        if has_exported_index and row[0] != str(row_count):
                            raise ValueError(
                                f"{source.name}: first column is blank in the header but "
                                f"not a sequential row index at line {line_number}"
                            )
                        writer.writerow([row[index] for index in keep_indexes])
                        row_count += 1

            os.replace(temporary_path, destination_dir / source.name)
            temporary_path = None
            total_rows += row_count
            print(
                f"Prepared {source.name}: {row_count:,} rows, "
                f"{len(header) - len(safe_header)} columns removed"
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    return total_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/sample"))
    parser.add_argument("--output", type=Path, default=Path("data/ready"))
    args = parser.parse_args()
    total_rows = prepare_csvs(args.input, args.output)
    print(f"Prepared {total_rows:,} rows across CSV files in {args.output}")


if __name__ == "__main__":
    main()
