from app.data_access import (
    count_tags,
    get_annotations,
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


if __name__ == "__main__":
    main()
