"""Shared presentation of stored sentiment; does not perform inference."""

MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"
LABELS = ("positive", "neutral", "negative")


def summarize_sentiment(rows, total):
    summary = {label: {"count": 0, "percentage": None, "average_confidence": None}
               for label in LABELS}
    weighted = {label: [0.0, 0] for label in LABELS}
    for row in rows:
        label = (row["label"] or "").lower()
        if label in summary:
            summary[label]["count"] += row["tweet_count"]
            if row['average_confidence'] is not None:
                weighted[label][0] += row['average_confidence'] * row['tweet_count']
                weighted[label][1] += row['tweet_count']
    for label, (value, count) in weighted.items():
        summary[label]['average_confidence'] = value / count if count else None
    analyzed = sum(item["count"] for item in summary.values())
    for item in summary.values():
        if analyzed:
            item["percentage"] = item["count"] / analyzed * 100
    return {
        "model_name": MODEL_NAME, "total_count": total,
        "analyzed_count": analyzed, "missing_count": total - analyzed,
        "coverage_percentage": analyzed / total * 100 if total else None,
        **summary,
    }
