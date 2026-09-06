
class ServiceQuality:
    def score(self, ratings):
        if not ratings:
            return 0

        return sum(ratings) / len(ratings)

