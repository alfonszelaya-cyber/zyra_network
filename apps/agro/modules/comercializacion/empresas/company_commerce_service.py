
class CompanyCommerceService:
    def register_operation(self, company_id, product, quantity):
        return {
            "company_id": company_id,
            "product": product,
            "quantity": quantity
        }

