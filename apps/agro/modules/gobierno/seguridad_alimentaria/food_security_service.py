
class FoodSecurityService:
    def calculate_balance(self, production, demand):
        return {
            "production": production,
            "demand": demand,
            "balance": production - demand
        }

