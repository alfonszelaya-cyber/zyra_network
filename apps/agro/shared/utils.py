
def normalize_text(value):
    return " ".join(str(value).strip().split())

def is_positive_number(value):
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False

