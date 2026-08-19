from app.data_access import (
    count_tags,
    get_annotations,
    get_c2c_tags,
    get_cell_series,
    get_latest_metrics,
    get_metric_series,
    get_page_tags,
    get_readings,
    parse_range,
)


def main():
    print(f"count_tags: {count_tags()}")

    tags = get_page_tags("overview")
    print(f"get_page_tags('overview'): {len(tags)} rows")

    start, end = parse_range("48h")
    tag_ids = tags.loc[tags["signal_class"] == "analog", "tag_id"].head(3).tolist()
    readings = get_readings(tag_ids, start, end)
    print(f"get_readings({tag_ids}, 48h): {len(readings)} rows")

    series = get_metric_series("ce", start, end)
    print(f"get_metric_series('ce', 48h, daily): {len(series)} rows")

    latest = get_latest_metrics()
    print(f"get_latest_metrics(): {len(latest)} rows")

    annotations = get_annotations(start, end)
    print(f"get_annotations(48h): {len(annotations)} rows")

    c2c_tags = get_c2c_tags()
    print(f"get_c2c_tags(): {len(c2c_tags)} rows, {c2c_tags['stack_group'].nunique()} stack groups")

    c2c_tag_ids = c2c_tags["tag_id"].head(3).tolist()
    cell_series = get_cell_series(c2c_tag_ids, start, end)
    print(f"get_cell_series({c2c_tag_ids}, 48h): {len(cell_series)} rows")


if __name__ == "__main__":
    main()
