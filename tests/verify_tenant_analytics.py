import os
import sys

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_analytics_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.models.restaurant import Restaurant
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import AuthService
from backend.services.analytics_service import AnalyticsService

def run_tenant_analytics_tests():
    print("=" * 80)
    print("RUNNING TENANT-AWARE ANALYTICS VERIFICATION")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 2. Create test restaurants
        print("\nCreating active and inactive test restaurants...")
        restaurant_a = RestaurantRepository.create(db, name="Restaurant A")
        restaurant_b = RestaurantRepository.create(db, name="Restaurant B")
        
        # Soft-deleted restaurant
        restaurant_deleted = RestaurantRepository.create(db, name="Soft Deleted Restaurant")
        RestaurantRepository.soft_delete(db, restaurant_deleted.id)

        # 3. Create test users
        print("\nCreating test users...")
        admin_user = UserRepository.create(db, "admin@saas.com", "pass1234", UserRole.ADMIN)
        rest_a_user = UserRepository.create(
            db, "rest_a@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_a.id
        )
        rest_b_user = UserRepository.create(
            db, "rest_b@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_b.id
        )
        customer_user = UserRepository.create(db, "customer@saas.com", "pass1234", UserRole.CUSTOMER)

        # 4. Generate tokens
        admin_token = AuthService.create_access_token(admin_user.id, admin_user.email, admin_user.role.value)
        rest_a_token = AuthService.create_access_token(rest_a_user.id, rest_a_user.email, rest_a_user.role.value)
        rest_b_token = AuthService.create_access_token(rest_b_user.id, rest_b_user.email, rest_b_user.role.value)
        customer_token = AuthService.create_access_token(customer_user.id, customer_user.email, customer_user.role.value)

        # 5. Verify Single Restaurant Analytics (Stable Hashing & Containment)
        print("\n1. Testing Single Restaurant Analytics retrieval...")
        
        # Restaurant A accessing their own analytics -> Allowed
        stats_a = AnalyticsService.get_restaurant_analytics(db, rest_a_token, restaurant_a.id)
        assert stats_a["restaurant_id"] == restaurant_a.id
        assert stats_a["restaurant_name"] == "Restaurant A"
        assert "total_tickets" in stats_a
        assert "csat" in stats_a
        assert "resolution_rate" in stats_a
        assert "escalations" in stats_a
        assert "sentiment_trend" in stats_a
        assert len(stats_a["sentiment_trend"]) == 7
        print("✓ Restaurant A user successfully retrieved own analytics.")

        # Stable Hashing check: Run again and verify values are exactly the same
        stats_a_repeat = AnalyticsService.get_restaurant_analytics(db, rest_a_token, restaurant_a.id)
        assert stats_a["total_tickets"] == stats_a_repeat["total_tickets"]
        assert stats_a["csat"] == stats_a_repeat["csat"]
        assert stats_a["resolution_rate"] == stats_a_repeat["resolution_rate"]
        assert stats_a["escalations"] == stats_a_repeat["escalations"]
        assert [d["score"] for d in stats_a["sentiment_trend"]] == [d["score"] for d in stats_a_repeat["sentiment_trend"]]
        print("✓ Hashing stability verified (deterministic outputs are identical).")

        # Restaurant A accessing Restaurant B -> Blocked (raises PermissionError)
        try:
            AnalyticsService.get_restaurant_analytics(db, rest_a_token, restaurant_b.id)
            assert False, "Failed: Allowed cross-tenant analytics access"
        except PermissionError as e:
            print(f"✓ Cross-tenant analytics access rejected correctly: {e}")

        # Customer accessing Restaurant A -> Blocked (raises PermissionError)
        try:
            AnalyticsService.get_restaurant_analytics(db, customer_token, restaurant_a.id)
            assert False, "Failed: Customer was allowed to retrieve analytics"
        except PermissionError as e:
            print(f"✓ Customer analytics access rejected correctly: {e}")

        # Accessing soft-deleted restaurant -> Blocked (raises ValueError)
        try:
            AnalyticsService.get_restaurant_analytics(db, admin_token, restaurant_deleted.id)
            assert False, "Failed: Allowed access to soft-deleted restaurant metrics"
        except ValueError as e:
            print(f"✓ Soft-deleted restaurant validation failed as expected: {e}")

        # 6. Verify Admin Global Aggregation
        print("\n2. Testing Admin Global Aggregations...")
        global_stats = AnalyticsService.get_global_analytics(db, admin_token)
        
        # Calculate expected values manually
        stats_a_mock = AnalyticsService._generate_mock_restaurant_analytics(restaurant_a.id, restaurant_a.name)
        stats_b_mock = AnalyticsService._generate_mock_restaurant_analytics(restaurant_b.id, restaurant_b.name)
        
        expected_total_tickets = stats_a_mock["total_tickets"] + stats_b_mock["total_tickets"]
        expected_csat = round((stats_a_mock["csat"] + stats_b_mock["csat"]) / 2.0, 2)
        expected_resolution_rate = round((stats_a_mock["resolution_rate"] + stats_b_mock["resolution_rate"]) / 2.0, 2)
        expected_escalations = stats_a_mock["escalations"] + stats_b_mock["escalations"]
        
        assert global_stats["total_tickets"] == expected_total_tickets
        assert global_stats["csat"] == expected_csat
        assert global_stats["resolution_rate"] == expected_resolution_rate
        assert global_stats["escalations"] == expected_escalations
        assert len(global_stats["sentiment_trend"]) == 7
        
        # Check daily averages on sentiment trend
        for i in range(7):
            avg_score = round((stats_a_mock["sentiment_trend"][i]["score"] + stats_b_mock["sentiment_trend"][i]["score"]) / 2.0, 2)
            assert global_stats["sentiment_trend"][i]["score"] == avg_score
            
        print("✓ Global overview aggregate values verified (sums and averages computed correctly).")

        # Non-admin retrieving global analytics -> Blocked (raises PermissionError)
        try:
            AnalyticsService.get_global_analytics(db, rest_a_token)
            assert False, "Failed: Allowed restaurant user to query global analytics"
        except PermissionError as e:
            print(f"✓ Global analytics query rejected for restaurant user correctly: {e}")

        # 7. Verify Admin Comparisons
        print("\n3. Testing Admin Comparisons...")
        comparison = AnalyticsService.compare_restaurant_analytics(db, admin_token, [restaurant_a.id, restaurant_b.id])
        assert restaurant_a.id in comparison
        assert restaurant_b.id in comparison
        assert comparison[restaurant_a.id]["total_tickets"] == stats_a_mock["total_tickets"]
        assert comparison[restaurant_b.id]["total_tickets"] == stats_b_mock["total_tickets"]
        print("✓ Comparison dictionary generated and values match correctly.")

        # Non-admin comparing analytics -> Blocked (raises PermissionError)
        try:
            AnalyticsService.compare_restaurant_analytics(db, rest_a_token, [restaurant_a.id, restaurant_b.id])
            assert False, "Failed: Allowed restaurant user to compare analytics"
        except PermissionError as e:
            print(f"✓ Comparison request rejected for restaurant user correctly: {e}")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL TENANT-AWARE ANALYTICS VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_tenant_analytics_tests()
