"""
Analytics service — real aggregations over the conversation, message, feedback,
and escalation tables (PRD Section 12 Analytics Dashboard).

Every metric is derived from actual data and scoped to a restaurant via its
conversations, so tenant isolation holds. Returns include the keys the
dashboards already consume (total_tickets, csat, resolution_rate, escalations,
sentiment_trend) plus richer fields (escalation_rate, avg_response_time_ms,
top_intents, feedback_count).
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.services.auth_service import AuthService
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.core.tenant import verify_restaurant_active
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.customer_feedback import CustomerFeedback
from backend.models.escalation_event import EscalationEvent
from backend.models.order import Order

_DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _utcnow():
    """Naive UTC 'now' to match SQLite CURRENT_TIMESTAMP storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt):
    """Strip tzinfo so tz-aware and naive datetimes can be compared without a
    TypeError (Conversation.created_at is tz-aware; Order.placed_at may be naive)."""
    if dt is not None and getattr(dt, "tzinfo", None) is not None:
        return dt.replace(tzinfo=None)
    return dt


def _empty_trend() -> List[Dict[str, Any]]:
    today = _utcnow().date()
    return [
        {"day": _DAY_ABBR[(today - timedelta(days=6 - i)).weekday()], "score": 0.0}
        for i in range(7)
    ]


class AnalyticsService:

    @staticmethod
    def _compute_restaurant_analytics(db: Session, restaurant_id: str, restaurant_name: str) -> Dict[str, Any]:
        """Aggregate real metrics for one restaurant from its conversations."""
        conv_q = db.query(Conversation).filter(Conversation.restaurant_id == restaurant_id)
        total_conversations = conv_q.count()

        # Count DISTINCT escalated conversations, not raw event rows — otherwise a
        # conversation with 2+ escalation events would push escalations above the
        # conversation total (negative resolution_rate, escalation_rate > 100%).
        escalations = (
            db.query(func.count(func.distinct(EscalationEvent.conversation_id)))
            .join(Conversation, EscalationEvent.conversation_id == Conversation.id)
            .filter(Conversation.restaurant_id == restaurant_id)
            .scalar()
        ) or 0

        # Resolution rate = share of conversations handled without escalation.
        resolution_rate = round(((total_conversations - escalations) / total_conversations) * 100, 1) if total_conversations else 0.0
        escalation_rate = round((escalations / total_conversations) * 100, 1) if total_conversations else 0.0

        # CSAT from customer feedback (1–5).
        csat_avg = (
            db.query(func.avg(CustomerFeedback.rating))
            .join(Conversation, CustomerFeedback.conversation_id == Conversation.id)
            .filter(Conversation.restaurant_id == restaurant_id)
            .scalar()
        )
        feedback_count = (
            db.query(CustomerFeedback)
            .join(Conversation, CustomerFeedback.conversation_id == Conversation.id)
            .filter(Conversation.restaurant_id == restaurant_id)
            .count()
        )

        # Average assistant response latency (ms).
        avg_latency = (
            db.query(func.avg(Message.latency_ms))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Conversation.restaurant_id == restaurant_id,
                Message.role == "assistant",
                Message.latency_ms.isnot(None),
            )
            .scalar()
        )

        # Most-asked intents (from user messages).
        intent_rows = (
            db.query(Message.intent, func.count().label("c"))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Conversation.restaurant_id == restaurant_id,
                Message.role == "user",
                Message.intent.isnot(None),
            )
            .group_by(Message.intent)
            .order_by(func.count().desc())
            .limit(5)
            .all()
        )
        top_intents = [{"intent": r[0], "count": r[1]} for r in intent_rows]

        # Conversion impact (PRD Section 12): of the customers who engaged the
        # assistant, what share placed an order at this restaurant AT OR AFTER
        # their first conversation — a genuine post-engagement signal (not orders
        # that predate any chat). See _conversion_stats.
        conversing_customers, converted = AnalyticsService._conversion_stats(db, [restaurant_id])
        conversion_impact = round((converted / conversing_customers) * 100, 1) if conversing_customers else 0.0

        return {
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant_name,
            "total_tickets": total_conversations,
            "total_conversations": total_conversations,
            "csat": round(float(csat_avg), 2) if csat_avg else 0.0,
            "feedback_count": feedback_count,
            "resolution_rate": resolution_rate,
            "escalations": escalations,
            "escalation_rate": escalation_rate,
            "avg_response_time_ms": int(round(avg_latency)) if avg_latency else 0,
            "top_intents": top_intents,
            "conversion_impact": conversion_impact,
            "converting_customers": converted,
            "conversing_customers": conversing_customers,
            "sentiment_trend": AnalyticsService._sentiment_trend(db, restaurant_id),
        }

    @staticmethod
    def _sentiment_trend(db: Session, restaurant_id: str) -> List[Dict[str, Any]]:
        """7-day positivity score per day: (positive + 0.5*neutral) / total user
        messages that day, in [0,1]. Empty days score 0."""
        since = _utcnow() - timedelta(days=7)
        rows = (
            db.query(
                func.date(Message.timestamp).label("d"),
                Message.sentiment,
                func.count().label("c"),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Conversation.restaurant_id == restaurant_id,
                Message.role == "user",
                Message.timestamp >= since,
            )
            .group_by("d", Message.sentiment)
            .all()
        )
        # date_str -> {sentiment: count}
        by_day: Dict[str, Dict[str, int]] = {}
        for d, sentiment, c in rows:
            by_day.setdefault(str(d), {})[(sentiment or "Neutral")] = c

        today = _utcnow().date()
        trend = []
        for i in range(7):
            day = today - timedelta(days=6 - i)
            counts = by_day.get(day.isoformat(), {})
            pos = counts.get("Positive", 0)
            neu = counts.get("Neutral", 0)
            neg = counts.get("Negative", 0)
            total = pos + neu + neg
            score = round((pos + 0.5 * neu) / total, 2) if total else 0.0
            trend.append({"day": _DAY_ABBR[day.weekday()], "score": score})
        return trend

    @staticmethod
    def _conversion_stats(db: Session, restaurant_ids: List[str]) -> tuple:
        """Return (conversing_customers, converted_customers) as DISTINCT customer
        counts across the given restaurants. A customer is 'converted' if they
        placed an order at a restaurant AT OR AFTER their first conversation there.
        Distinct at the customer level, so a customer active at several
        restaurants is counted once (correct for platform-wide rollups)."""
        if not restaurant_ids:
            return 0, 0
        # Earliest conversation per (customer, restaurant).
        conv_pairs = (
            db.query(
                Conversation.customer_id,
                Conversation.restaurant_id,
                func.min(Conversation.created_at),
            )
            .filter(
                Conversation.restaurant_id.in_(restaurant_ids),
                Conversation.customer_id.isnot(None),
            )
            .group_by(Conversation.customer_id, Conversation.restaurant_id)
            .all()
        )
        if not conv_pairs:
            return 0, 0
        order_rows = (
            db.query(Order.customer_id, Order.restaurant_id, Order.placed_at)
            .filter(
                Order.restaurant_id.in_(restaurant_ids),
                Order.customer_id.isnot(None),
            )
            .all()
        )
        orders_by_pair: Dict[tuple, List] = {}
        for cid, rid, placed_at in order_rows:
            if placed_at is not None:
                orders_by_pair.setdefault((cid, rid), []).append(_naive(placed_at))

        conversing, converted = set(), set()
        for cid, rid, first_conv in conv_pairs:
            conversing.add(cid)
            first = _naive(first_conv)
            if any(pa >= first for pa in orders_by_pair.get((cid, rid), ())):
                converted.add(cid)
        return len(conversing), len(converted)

    @staticmethod
    def get_restaurant_analytics(db: Session, token: str, restaurant_id: str) -> Dict[str, Any]:
        """Analytics for a specific restaurant (tenant-isolated)."""
        AuthService.validate_tenant_access(db, token, restaurant_id)
        restaurant = RestaurantRepository.get_by_id(db, restaurant_id)
        name = restaurant.name if restaurant else "Unknown Restaurant"
        return AnalyticsService._compute_restaurant_analytics(db, restaurant_id, name)

    @staticmethod
    def get_global_analytics(db: Session, token: str) -> Dict[str, Any]:
        """Platform-wide analytics across all active restaurants (admin only)."""
        AuthService.authorize_role(token, "admin")
        active_restaurants = RestaurantRepository.list_active(db)
        if not active_restaurants:
            return {
                "total_tickets": 0, "csat": 0.0, "resolution_rate": 0.0,
                "escalations": 0, "escalation_rate": 0.0, "avg_response_time_ms": 0,
                "restaurant_count": 0, "conversion_impact": 0.0, "sentiment_trend": _empty_trend(),
            }

        per = [AnalyticsService._compute_restaurant_analytics(db, r.id, r.name) for r in active_restaurants]
        n = len(per)
        total_tickets = sum(a["total_tickets"] for a in per)
        escalations = sum(a["escalations"] for a in per)
        # CSAT / latency averaged only over restaurants that actually have data.
        csat_vals = [a["csat"] for a in per if a["feedback_count"] > 0]
        lat_vals = [a["avg_response_time_ms"] for a in per if a["avg_response_time_ms"] > 0]

        # True platform-wide, distinct-customer conversion (dedupes customers
        # active at several restaurants) — computed directly, not by summing
        # per-restaurant counts.
        active_ids = [r.id for r in active_restaurants]
        g_conversing, g_converting = AnalyticsService._conversion_stats(db, active_ids)

        # Sentiment trend: average per day over restaurants that actually have
        # activity (mirrors the csat/latency filtering); empty restaurants would
        # otherwise drag the platform score toward 0.
        active_per = [a for a in per if a["total_conversations"] > 0]
        sentiment_trend = []
        if active_per:
            for i in range(7):
                daily = [a["sentiment_trend"][i]["score"] for a in active_per]
                label = active_per[0]["sentiment_trend"][i]["day"]
                sentiment_trend.append({"day": label, "score": round(sum(daily) / len(active_per), 2)})
        else:
            sentiment_trend = _empty_trend()

        return {
            "total_tickets": total_tickets,
            "csat": round(sum(csat_vals) / len(csat_vals), 2) if csat_vals else 0.0,
            "resolution_rate": round(((total_tickets - escalations) / total_tickets) * 100, 1) if total_tickets else 0.0,
            "escalations": escalations,
            "escalation_rate": round((escalations / total_tickets) * 100, 1) if total_tickets else 0.0,
            "avg_response_time_ms": int(round(sum(lat_vals) / len(lat_vals))) if lat_vals else 0,
            "restaurant_count": n,
            "conversion_impact": round((g_converting / g_conversing) * 100, 1) if g_conversing else 0.0,
            "sentiment_trend": sentiment_trend,
        }

    @staticmethod
    def compare_restaurant_analytics(db: Session, token: str, restaurant_ids: List[str]) -> Dict[str, Any]:
        """Side-by-side analytics for multiple restaurants (admin only)."""
        AuthService.authorize_role(token, "admin")
        comparison = {}
        for r_id in restaurant_ids:
            verify_restaurant_active(db, r_id)
            restaurant = RestaurantRepository.get_by_id(db, r_id)
            name = restaurant.name if restaurant else "Unknown Restaurant"
            comparison[r_id] = AnalyticsService._compute_restaurant_analytics(db, r_id, name)
        return comparison
