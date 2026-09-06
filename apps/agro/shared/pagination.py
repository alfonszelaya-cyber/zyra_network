
def paginate(items, page=1, page_size=50):
    if page < 1 or page_size < 1:
        raise ValueError("Invalid pagination")

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": items[start:end],
        "page": page,
        "page_size": page_size,
        "total": len(items)
    }

