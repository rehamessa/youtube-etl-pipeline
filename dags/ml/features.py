import re

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score

# Common Arabic (MSA + Egyptian) and English words that say nothing about the topic.
# Written in the normalized form produced by normalize_text()
STOPWORDS = {
    "من", "في", "علي", "الي", "عن", "مع", "هل", "كيف", "لماذا", "ماذا", "ما", "متي",
    "و", "او", "ثم", "ان", "هذا", "هذه", "ذلك", "تلك", "التي", "الذي", "الذين",
    "بعد", "قبل", "كل", "بين", "لا", "لم", "لن", "قد", "هو", "هي", "هم", "انت",
    "انا", "نحن", "عند", "حتي", "اذا", "بس", "ايه", "ازاي", "يعني", "مش", "ليه",
    "اللي", "علشان", "عشان", "ده", "دي", "دا", "يا", "بقي", "كان", "كانت", "يكون",
    "the", "a", "an", "of", "to", "and", "in", "on", "for", "with", "is", "vs",
    "you", "your", "my", "we", "it", "this", "that", "how", "why", "what", "do",
    "can", "would", "are", "be", "at", "by", "from", "or",
}

# Words of 2+ letters only (Arabic or Latin), no digits
TOKEN_PATTERN = r"(?u)\b[^\W\d_]{2,}\b"

# Numeric features used by the success model (topic is added as one-hot columns)
FEATURE_COLUMNS = [
    "duration_minutes",
    "is_short",
    "weekday",
    "upload_hour",
    "upload_month",
    "title_words",
    "title_has_question",
    "title_has_number",
]


def normalize_text(text):
    # Remove Arabic diacritics and tatweel
    text = re.sub(r"[ً-ْـ]", "", str(text))
    # Unify letter variants so the same word is always spelled the same way
    text = re.sub(r"[إأآ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    # Punctuation becomes a space
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def build_topics(titles, k_range=range(5, 11), random_state=42):
    """Group titles into topics with TF-IDF + KMeans.

    The number of topics is the k with the best silhouette score.
    Returns (topic_id per title, DataFrame with one row per topic).
    """
    clean = [normalize_text(t) for t in titles]

    vectorizer = TfidfVectorizer(
        token_pattern=TOKEN_PATTERN,
        stop_words=list(STOPWORDS),
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.5,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(clean)

    best_k, best_score, best_model = None, -1.0, None
    for k in k_range:
        # Need more titles than clusters for the silhouette score
        if k >= X.shape[0]:
            continue
        model = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(X)
        if len(set(model.labels_)) < 2:
            continue
        score = silhouette_score(X, model.labels_, metric="cosine")
        if score > best_score:
            best_k, best_score, best_model = k, score, model

    if best_model is None:
        raise ValueError("Not enough titles to build topics")

    # Topic label = the words closest to the centre of each cluster
    terms = vectorizer.get_feature_names_out()
    topics = []
    for topic_id in range(best_k):
        top_idx = np.argsort(best_model.cluster_centers_[topic_id])[::-1]
        top_terms = [terms[i] for i in top_idx[:5]]
        topics.append({
            "topic_id": topic_id,
            "topic_label": " / ".join(top_terms[:3]),
            "top_terms": ", ".join(top_terms),
        })

    return best_model.labels_.astype(int), pd.DataFrame(topics)


def add_features(df):
    """Add the model features computed from the upload date, type and title."""
    out = df.copy()
    upload = pd.to_datetime(out["upload_date"])

    out["weekday"] = upload.dt.dayofweek
    out["upload_hour"] = upload.dt.hour
    out["upload_month"] = upload.dt.month
    out["is_short"] = (out["video_type"] == "Shorts").astype(int)
    out["title_words"] = out["title"].astype(str).str.split().str.len()
    out["title_has_question"] = out["title"].astype(str).str.contains(r"[?؟]").astype(int)
    out["title_has_number"] = out["title"].astype(str).str.contains(r"[0-9٠-٩]").astype(int)

    return out


def add_success_label(df):
    """A video is a success when it beats the median views of its upload year.

    Comparing inside the same year removes most of the age effect:
    older videos had more time to collect views.
    """
    out = df.copy()
    year = pd.to_datetime(out["upload_date"]).dt.year
    year_median = out.groupby(year)["views"].transform("median")
    out["is_success"] = (out["views"] > year_median).astype(int)
    return out


def train_success_model(df, random_state=42):
    """Train a random forest that predicts is_success.

    Returns (predictions DataFrame, feature importance DataFrame, metrics dict).
    The probabilities are out-of-fold, so each video is scored by a model
    that never saw it during training.
    """
    X = pd.get_dummies(
        df[FEATURE_COLUMNS + ["topic_id"]].astype({"topic_id": str}),
        columns=["topic_id"],
        prefix="topic",
    ).astype(float)
    y = df["is_success"].astype(int)

    if y.nunique() < 2:
        raise ValueError("is_success has only one class, cannot train the model")

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=random_state,
    )

    n_splits = int(min(5, y.value_counts().min()))
    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        roc_auc = float(cross_val_score(model, X, y, cv=cv, scoring="roc_auc").mean())
        proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    else:
        # Too few videos in one class for cross validation
        roc_auc = float("nan")
        proba = model.fit(X, y).predict_proba(X)[:, 1]

    # Final model on all videos, used for the feature importance
    model.fit(X, y)

    importance = pd.Series(model.feature_importances_, index=X.columns)
    # The one-hot topic columns are summed into a single "topic" feature
    importance = (
        importance.groupby(lambda col: "topic" if col.startswith("topic_") else col)
        .sum()
        .sort_values(ascending=False)
    )

    predictions = pd.DataFrame({
        "video_id": df["video_id"].values,
        "success_probability": np.round(proba, 4),
        "is_success": y.values,
    })
    importance_df = pd.DataFrame({
        "feature": importance.index,
        "importance": np.round(importance.values, 4),
    })
    metrics = {
        "roc_auc": round(roc_auc, 4),
        "videos": float(len(df)),
        "success_rate": round(float(y.mean()), 4),
    }

    return predictions, importance_df, metrics


def find_similar_videos(df, top_n=5):
    """For each video, the top_n videos with the most similar title.

    Character n-grams work better than words for Arabic, because the same
    word appears with different prefixes and suffixes.
    """
    clean = [normalize_text(t) for t in df["title"]]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    X = vectorizer.fit_transform(clean)

    sim = cosine_similarity(X)
    # A video must not be similar to itself
    np.fill_diagonal(sim, -1)

    ids = df["video_id"].tolist()
    top_n = min(top_n, len(ids) - 1)
    out = []
    for i, video_id in enumerate(ids):
        nearest = np.argsort(sim[i])[::-1][:top_n]
        for pos, j in enumerate(nearest, start=1):
            out.append({
                "video_id": video_id,
                "similar_video_id": ids[j],
                "similarity": round(float(sim[i, j]), 4),
                "similar_rank": pos,
            })

    return pd.DataFrame(out)
