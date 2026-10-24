import pandas as pd
import pytest

# Importing airflow in conftest adds the dags folder to the path
from ml.features import (
    add_features,
    add_success_label,
    build_topics,
    find_similar_videos,
    normalize_text,
    train_success_model,
)


@pytest.fixture
def sample_videos():
    # Two clear topics (gold / dollar) with 10 videos each
    titles = (
        [f"سعر الذهب اليوم وتوقعات الذهب {i}" for i in range(10)]
        + [f"الدولار والجنيه المصري وسعر الدولار {i}" for i in range(10)]
    )
    n = len(titles)
    return pd.DataFrame({
        "video_id": [f"vid{i:08d}" for i in range(n)],
        "title": titles,
        "upload_date": pd.date_range("2024-01-01", periods=n, freq="15D"),
        "duration_minutes": [5 + i for i in range(n)],
        "video_type": ["Shorts" if i % 5 == 0 else "Normal" for i in range(n)],
        "views": [1000 * (i + 1) for i in range(n)],
    })


def test_normalize_text():
    # Hamza forms, ta marbuta, alef maqsura and diacritics are unified
    assert normalize_text("إقتصادُ مصرَ؟") == "اقتصاد مصر"
    assert normalize_text("الأزمة") == "الازمه"
    assert normalize_text("على") == "علي"


def test_build_topics(sample_videos):
    topic_ids, topics = build_topics(sample_videos["title"], k_range=range(2, 4))

    assert len(topic_ids) == len(sample_videos)
    assert set(topics.columns) == {"topic_id", "topic_label", "top_terms"}
    # Gold videos and dollar videos must not be in the same topic
    assert topic_ids[0] != topic_ids[-1]


def test_add_features(sample_videos):
    df = add_features(sample_videos)

    assert df.loc[0, "is_short"] == 1
    assert df.loc[1, "is_short"] == 0
    assert df["weekday"].between(0, 6).all()
    assert df["title_has_number"].all()


def test_add_success_label(sample_videos):
    df = add_success_label(sample_videos)

    # Inside every year, about half of the videos beat the median
    assert set(df["is_success"].unique()) == {0, 1}


def test_train_success_model(sample_videos):
    df = add_success_label(add_features(sample_videos))
    df["topic_id"] = [0] * 10 + [1] * 10

    predictions, importance, metrics = train_success_model(df)

    assert len(predictions) == len(df)
    assert predictions["success_probability"].between(0, 1).all()
    assert "topic" in importance["feature"].values
    assert set(metrics) == {"roc_auc", "videos", "success_rate"}


def test_find_similar_videos(sample_videos):
    similar = find_similar_videos(sample_videos, top_n=3)

    assert len(similar) == len(sample_videos) * 3
    # A video is never similar to itself
    assert (similar["video_id"] != similar["similar_video_id"]).all()
    # The closest video to a gold video is another gold video
    first = similar[(similar["video_id"] == "vid00000000") & (similar["similar_rank"] == 1)]
    assert first["similar_video_id"].iloc[0] in set(sample_videos["video_id"][:10])
