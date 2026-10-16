from datetime import datetime, timedelta


def parse_duration(duration_str):
    # ISO 8601 duration, e.g. "P1DT2H30M45S" -> remove the P and T markers -> "1D2H30M45S"
    duration_str = duration_str.replace("P", "").replace("T", "")

    # Order matters: each split uses the remainder of the previous one
    components = ["D", "H", "M", "S"]
    values = {"D": 0, "H": 0, "M": 0, "S": 0}

    for component in components:
        if component in duration_str:
            value, duration_str = duration_str.split(component)
            values[component] = int(value)

    duration = timedelta(
        days=values["D"],
        hours=values["H"],
        minutes=values["M"],
        seconds=values["S"],
    )

    return duration


def transform_data(row):
    duration_td = parse_duration(row["Duration"])

    # datetime.min is 0001-01-01 00:00:00; adding the duration and taking .time()
    # gives a time object like 00:57:59 for the TIME column
    row["Duration"] = (datetime.min + duration_td).time()

    # Videos of 1 minute or less are classified as Shorts
    row["Video_Type"] = "Shorts" if duration_td.total_seconds() <= 60 else "Normal"

    return row