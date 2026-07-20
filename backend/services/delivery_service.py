"""
Delivery-zone workflow (PRD Section 10).

Validates whether a customer's location is deliverable using the restaurant's
structured `delivery_zones` config, returning the zone, fee, free-delivery
threshold, and ETA. Given a distance ("I'm 4 km away"), it deterministically
resolves the zone. When no distance is provided, it returns None so the caller
falls back to RAG over the free-text delivery docs.
"""
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.repositories.restaurant_repository import RestaurantRepository

_KM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:km|kms|kilometres?|kilometers?)\b', re.IGNORECASE)


def extract_distance_km(text: str) -> Optional[float]:
    """Pull a distance in km out of free text, e.g. '4.5 km' -> 4.5."""
    m = _KM_RE.search(text or "")
    return float(m.group(1)) if m else None


class DeliveryService:

    @staticmethod
    def check(db: Session, restaurant_id: str, distance_km: Optional[float]) -> Optional[Dict[str, Any]]:
        """Resolve a distance to a delivery zone. Returns None if there are no
        structured zones or no distance was given (defer to RAG)."""
        rest = RestaurantRepository.get_by_id(db, restaurant_id)
        zones = (rest.delivery_zones if rest else None) or []
        if not zones or distance_km is None:
            return None

        zones_sorted = sorted(zones, key=lambda z: z.get("max_km", 1e9))
        max_radius = max((z.get("max_km", 0) for z in zones_sorted), default=0)

        if distance_km > max_radius:
            return {
                "deliverable": False,
                "summary": (
                    f"Sorry, {distance_km:g} km is outside our {max_radius:g} km delivery radius. "
                    "You may still be able to order through a partner delivery app."
                ),
            }

        for z in zones_sorted:
            if distance_km <= z.get("max_km", 1e9):
                fee = z.get("fee")
                free_over = z.get("free_over")
                eta = z.get("eta_min")
                name = z.get("name", "your area")
                parts = [f"Yes — we deliver to your area ({name})."]
                if fee is not None:
                    fee_txt = f"The delivery fee is ₹{int(fee)}"
                    if free_over:
                        fee_txt += f" (free over ₹{int(free_over)})"
                    parts.append(fee_txt + ".")
                if eta is not None:
                    parts.append(f"Estimated delivery is about {int(eta)} minutes.")
                return {
                    "deliverable": True, "zone": name, "fee": fee, "eta_min": eta,
                    "summary": " ".join(parts),
                }
        return None
