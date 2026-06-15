import hashlib
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.services.auth_service import AuthService
from backend.repositories.restaurant_repository import RestaurantRepository

class AnalyticsService:
    @staticmethod
    def _generate_mock_restaurant_analytics(restaurant_id: str, restaurant_name: str) -> Dict[str, Any]:
        """
        Generates deterministic, stable mock analytics metrics for a given restaurant
        using hashlib.sha256(restaurant_id.encode()) to prevent change between interpreter sessions.
        """
        digest = hashlib.sha256(restaurant_id.encode()).hexdigest()
        
        # total_tickets range [100, 500]
        total_tickets = int(digest[0:4], 16) % 401 + 100
        # csat range [3.5, 4.9]
        csat = round((int(digest[4:8], 16) % 15) / 10.0 + 3.5, 2)
        # resolution_rate range [75.0, 98.0]
        resolution_rate = round((int(digest[8:12], 16) % 24) + 75.0, 2)
        # escalations range [5, 45]
        escalations = int(digest[12:16], 16) % 41 + 5
        
        # 7-day sentiment trend window (positive sentiment score out of 1.0)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        sentiment_trend = []
        for i, day in enumerate(days):
            day_digest = hashlib.sha256(f"{restaurant_id}_day_{i}".encode()).hexdigest()
            # range [0.50, 0.90]
            val_sent = round(0.5 + (int(day_digest[0:4], 16) % 41) / 100.0, 2)
            sentiment_trend.append({"day": day, "score": val_sent})
            
        return {
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant_name,
            "total_tickets": total_tickets,
            "csat": csat,
            "resolution_rate": resolution_rate,
            "escalations": escalations,
            "sentiment_trend": sentiment_trend
        }

    @staticmethod
    def get_restaurant_analytics(db: Session, token: str, restaurant_id: str) -> Dict[str, Any]:
        """
        Retrieves analytics metrics for a specific restaurant.
        Enforces tenant isolation using AuthService.validate_tenant_access.
        """
        # Exposes tenant context, verifies active status, and checks role-based tenant constraints
        AuthService.validate_tenant_access(db, token, restaurant_id)
        
        # Get restaurant details (we already validated it is active and exists)
        restaurant = RestaurantRepository.get_by_id(db, restaurant_id)
        name = restaurant.name if restaurant else "Unknown Restaurant"
        
        return AnalyticsService._generate_mock_restaurant_analytics(restaurant_id, name)

    @staticmethod
    def get_global_analytics(db: Session, token: str) -> Dict[str, Any]:
        """
        Retrieves global aggregated analytics across all active restaurants.
        Enforces that the user has admin role by reusing existing authorization helper.
        """
        # Reuse existing authorization helpers to prevent architecture drift
        AuthService.authorize_role(token, "admin")
        
        active_restaurants = RestaurantRepository.list_active(db)
        if not active_restaurants:
            return {
                "total_tickets": 0,
                "csat": 0.0,
                "resolution_rate": 0.0,
                "escalations": 0,
                "sentiment_trend": [{"day": day, "score": 0.0} for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]]
            }
            
        all_analytics = [
            AnalyticsService._generate_mock_restaurant_analytics(r.id, r.name)
            for r in active_restaurants
        ]
        
        total_tickets = sum(a["total_tickets"] for a in all_analytics)
        csat = round(sum(a["csat"] for a in all_analytics) / len(all_analytics), 2)
        resolution_rate = round(sum(a["resolution_rate"] for a in all_analytics) / len(all_analytics), 2)
        escalations = sum(a["escalations"] for a in all_analytics)
        
        # Sentiment trend: daily average across all restaurants
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        sentiment_trend = []
        for i, day in enumerate(days):
            daily_avg = sum(a["sentiment_trend"][i]["score"] for a in all_analytics) / len(all_analytics)
            sentiment_trend.append({"day": day, "score": round(daily_avg, 2)})
            
        return {
            "total_tickets": total_tickets,
            "csat": csat,
            "resolution_rate": resolution_rate,
            "escalations": escalations,
            "sentiment_trend": sentiment_trend
        }

    @staticmethod
    def compare_restaurant_analytics(db: Session, token: str, restaurant_ids: List[str]) -> Dict[str, Any]:
        """
        Compares analytics metrics across multiple restaurants.
        Enforces that the user has admin role by reusing existing authorization helper.
        """
        # Reuse existing authorization helpers to prevent architecture drift
        AuthService.authorize_role(token, "admin")
        
        comparison = {}
        for r_id in restaurant_ids:
            # Verify restaurant exists, is active, and not soft-deleted
            # Reuses verify_restaurant_active from tenant validation layer
            from backend.core.tenant import verify_restaurant_active
            verify_restaurant_active(db, r_id)
            
            restaurant = RestaurantRepository.get_by_id(db, r_id)
            name = restaurant.name if restaurant else "Unknown Restaurant"
            
            comparison[r_id] = AnalyticsService._generate_mock_restaurant_analytics(r_id, name)
            
        return comparison
