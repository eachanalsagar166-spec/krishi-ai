"""
Buyer Network: connects farmers with local dealers and agro-industries.

Buyers (role "buyer") keep a business profile and post quotations: crop,
grade, price per kg, accepted quantity range, payment terms and pickup.
Farmers describe a lot and get buyers ranked by what they would actually
take home: quote price x sellable quantity, minus transport when the farmer
delivers, checked against fair mandi parity. Farmers send connect requests;
buyers accept or decline, and contact details are shared only on acceptance.

Tables live in the same SQLite database as accounts (data/krishi_ai.db).
Demo buyers are seeded once and flagged is_demo = 1 so the UI can label them.
"""
import datetime
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import bcrypt

from modules import auth_db
from modules.geo_ors import estimate_road_distance_demo
from modules.transport_engine import calculate_transport_cost
from modules.fraud_detector import evaluate_buyer_offer

BUYER_TYPES = ["Local Dealer", "Commission Agent", "Food Processor", "Exporter", "Retail Chain", "Cold Storage Operator"]
PAYMENT_TERMS = ["Immediate Cash / UPI at Weighbridge", "Payment after 7 days", "Payment after 15 days", "Unspecified Credit"]
PICKUP_OPTIONS = ["Buyer collects from farm", "Farmer delivers"]
GRADES = ["Any grade", "FAQ", "Grade A (Premium)"]
FARMER_GRADES = ["FAQ", "Grade A (Premium)"]
REQUEST_STATUSES = ["pending", "accepted", "declined", "withdrawn"]
LOCAL_RADIUS_KM = 60.0

_COORDS_PATH = os.path.join(auth_db.PROJECT_ROOT, "data", "coordinates_cache.json")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def location_options() -> Dict[str, Tuple[float, float]]:
    """Known 'District, State' locations with coordinates (from the routing cache)."""
    try:
        with open(_COORDS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return {k: (float(v["lat"]), float(v["lon"])) for k, v in raw.items() if "lat" in v and "lon" in v}
    except (OSError, ValueError, KeyError):
        return {}


# ------------------------------------------------------------------------------
# Schema & demo seed
# ------------------------------------------------------------------------------
def init_buyer_tables():
    conn = auth_db.get_db_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS buyer_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        business_name TEXT NOT NULL,
        buyer_type TEXT NOT NULL,
        location_label TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        phone TEXT,
        description TEXT,
        is_demo INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS buyer_quotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        commodity TEXT NOT NULL,
        grade TEXT NOT NULL DEFAULT 'Any grade',
        price_per_kg REAL NOT NULL,
        min_qty_kg REAL NOT NULL DEFAULT 0,
        max_qty_kg REAL NOT NULL,
        payment_terms TEXT NOT NULL,
        pickup TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        valid_until TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (buyer_id) REFERENCES buyer_profiles (id) ON DELETE CASCADE
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS connection_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quotation_id INTEGER NOT NULL,
        farmer_user_id INTEGER NOT NULL,
        quantity_kg REAL NOT NULL,
        asking_price_kg REAL NOT NULL,
        message TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (quotation_id) REFERENCES buyer_quotations (id) ON DELETE CASCADE,
        FOREIGN KEY (farmer_user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    conn.close()


# Demo buyers: clearly labelled sample listings so the network can be tried
# before real dealers sign up. Coordinates are real town centres.
DEMO_BUYERS = [
    {
        "email": "buyer@krishiai.com", "full_name": "Suresh Kumar", "phone": "+91 98451 20001",
        "business_name": "Ramanagara Vegetable Traders (Demo)", "buyer_type": "Local Dealer",
        "location_label": "Ramanagara, Karnataka", "lat": 12.7159, "lon": 77.2810,
        "description": "Wholesale vegetable dealer supplying Bengaluru retail markets.",
        "quotes": [
            ("Tomato", "FAQ", 15.5, 200, 3000, PAYMENT_TERMS[0], PICKUP_OPTIONS[0], "Daily pickup before 10 AM."),
            ("Banana", "Any grade", 22.0, 300, 4000, PAYMENT_TERMS[1], PICKUP_OPTIONS[0], ""),
        ],
    },
    {
        "email": "buyer.processor@krishiai.com", "full_name": "Anitha Rao", "phone": "+91 98451 20002",
        "business_name": "Bengaluru Tomato Processing Unit (Demo)", "buyer_type": "Food Processor",
        "location_label": "Bangalore, Karnataka", "lat": 12.9716, "lon": 77.5946,
        "description": "Pulp and ketchup processing; buys in bulk all season.",
        "quotes": [
            ("Tomato", "Any grade", 12.5, 2000, 20000, PAYMENT_TERMS[1], PICKUP_OPTIONS[1], "Processing grade accepted."),
        ],
    },
    {
        "email": "buyer.agent@krishiai.com", "full_name": "Mahesh Gowda", "phone": "+91 98451 20003",
        "business_name": "Channapatna Commission Agency (Demo)", "buyer_type": "Commission Agent",
        "location_label": "Channapatna, Karnataka", "lat": 12.6518, "lon": 77.2089,
        "description": "APMC commission agent; settles after auction.",
        "quotes": [
            ("Tomato", "Any grade", 11.0, 100, 2500, PAYMENT_TERMS[2], PICKUP_OPTIONS[1], "Settlement after auction."),
            ("Maize", "Any grade", 21.0, 1000, 15000, PAYMENT_TERMS[1], PICKUP_OPTIONS[1], ""),
        ],
    },
    {
        "email": "buyer.export@krishiai.com", "full_name": "Farah Khan", "phone": "+91 98451 20004",
        "business_name": "Mysuru Fresh Exports (Demo)", "buyer_type": "Exporter",
        "location_label": "Mysuru, Karnataka", "lat": 12.2958, "lon": 76.6394,
        "description": "Export packhouse; sorted and graded produce only.",
        "quotes": [
            ("Tomato", "Grade A (Premium)", 19.0, 1000, 8000, PAYMENT_TERMS[0], PICKUP_OPTIONS[0], "Firm, uniform red fruit."),
            ("Banana", "Grade A (Premium)", 27.0, 1000, 10000, PAYMENT_TERMS[0], PICKUP_OPTIONS[0], ""),
        ],
    },
    {
        "email": "buyer.retail@krishiai.com", "full_name": "Pradeep Shetty", "phone": "+91 98451 20005",
        "business_name": "Kolar Fresh Retail Sourcing (Demo)", "buyer_type": "Retail Chain",
        "location_label": "Kolar, Karnataka", "lat": 13.1367, "lon": 78.1291,
        "description": "Sources for supermarket shelves; weekly contracts.",
        "quotes": [
            ("Tomato", "FAQ", 17.0, 500, 5000, PAYMENT_TERMS[1], PICKUP_OPTIONS[1], "Crated delivery to DC."),
            ("Onion", "Any grade", 18.0, 500, 6000, PAYMENT_TERMS[1], PICKUP_OPTIONS[1], ""),
        ],
    },
    {
        "email": "buyer.feed@krishiai.com", "full_name": "Ravi Prasad", "phone": "+91 98451 20006",
        "business_name": "Tumakuru Feed Mills (Demo)", "buyer_type": "Food Processor",
        "location_label": "Tumakuru, Karnataka", "lat": 13.3409, "lon": 77.1010,
        "description": "Poultry feed manufacturer; buys dried maize.",
        "quotes": [
            ("Maize", "FAQ", 23.5, 2000, 30000, PAYMENT_TERMS[0], PICKUP_OPTIONS[0], "Moisture below 14%."),
        ],
    },
]
DEMO_BUYER_PASSWORD = "Buyer@123"


def seed_demo_buyers():
    """Creates the demo buyer accounts, profiles and quotations once."""
    conn = auth_db.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM buyer_profiles WHERE is_demo = 1")
    if c.fetchone()[0] > 0:
        conn.close()
        return
    now = _now()
    pwd_hash = bcrypt.hashpw(DEMO_BUYER_PASSWORD.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
    for b in DEMO_BUYERS:
        c.execute("SELECT id FROM users WHERE email = ?", (b["email"],))
        row = c.fetchone()
        if row:
            user_id = row["id"]
        else:
            c.execute("""
            INSERT INTO users (email, password_hash, full_name, phone, role, created_at, is_active)
            VALUES (?, ?, ?, ?, 'buyer', ?, 1)
            """, (b["email"], pwd_hash, b["full_name"], b["phone"], now))
            user_id = c.lastrowid
        c.execute("""
        INSERT INTO buyer_profiles (user_id, business_name, buyer_type, location_label, latitude, longitude,
                                    phone, description, is_demo, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (user_id, b["business_name"], b["buyer_type"], b["location_label"], b["lat"], b["lon"],
              b["phone"], b["description"], now))
        buyer_id = c.lastrowid
        for commodity, grade, price, qmin, qmax, terms, pickup, notes in b["quotes"]:
            c.execute("""
            INSERT INTO buyer_quotations (buyer_id, commodity, grade, price_per_kg, min_qty_kg, max_qty_kg,
                                          payment_terms, pickup, notes, status, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', NULL, ?)
            """, (buyer_id, commodity, grade, price, qmin, qmax, terms, pickup, notes, now))
    conn.commit()
    conn.close()


# ------------------------------------------------------------------------------
# Buyer profiles & quotations
# ------------------------------------------------------------------------------
def get_buyer_profile(user_id: int) -> Optional[Dict[str, Any]]:
    conn = auth_db.get_db_connection()
    row = conn.execute("SELECT * FROM buyer_profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_buyer_profile(user_id: int, data: Dict[str, Any]) -> Tuple[bool, str]:
    name = (data.get("business_name") or "").strip()
    if not name:
        return False, "Business name is required."
    if data.get("buyer_type") not in BUYER_TYPES:
        return False, "Choose a buyer type."
    try:
        lat, lon = float(data["latitude"]), float(data["longitude"])
    except (KeyError, TypeError, ValueError):
        return False, "Choose your business location."
    conn = auth_db.get_db_connection()
    existing = conn.execute("SELECT id FROM buyer_profiles WHERE user_id = ?", (user_id,)).fetchone()
    if existing:
        conn.execute("""
        UPDATE buyer_profiles SET business_name = ?, buyer_type = ?, location_label = ?, latitude = ?,
               longitude = ?, phone = ?, description = ? WHERE user_id = ?
        """, (name, data["buyer_type"], data.get("location_label", ""), lat, lon,
              (data.get("phone") or "").strip() or None, (data.get("description") or "").strip(), user_id))
    else:
        conn.execute("""
        INSERT INTO buyer_profiles (user_id, business_name, buyer_type, location_label, latitude, longitude,
                                    phone, description, is_demo, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (user_id, name, data["buyer_type"], data.get("location_label", ""), lat, lon,
              (data.get("phone") or "").strip() or None, (data.get("description") or "").strip(), _now()))
    conn.commit()
    conn.close()
    return True, "Business profile saved."


def create_quotation(buyer_id: int, data: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        price = float(data["price_per_kg"])
        qmin = float(data.get("min_qty_kg") or 0)
        qmax = float(data["max_qty_kg"])
    except (KeyError, TypeError, ValueError):
        return False, "Price and quantities must be numbers."
    if not (data.get("commodity") or "").strip():
        return False, "Choose a crop."
    if price <= 0:
        return False, "Price must be above zero."
    if qmax <= 0 or qmin < 0 or qmin > qmax:
        return False, "Minimum quantity must be between 0 and the maximum quantity."
    if data.get("grade") not in GRADES or data.get("payment_terms") not in PAYMENT_TERMS or data.get("pickup") not in PICKUP_OPTIONS:
        return False, "Choose grade, payment terms and pickup."
    conn = auth_db.get_db_connection()
    conn.execute("""
    INSERT INTO buyer_quotations (buyer_id, commodity, grade, price_per_kg, min_qty_kg, max_qty_kg,
                                  payment_terms, pickup, notes, status, valid_until, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
    """, (buyer_id, data["commodity"].strip(), data["grade"], price, qmin, qmax, data["payment_terms"],
          data["pickup"], (data.get("notes") or "").strip(), data.get("valid_until"), _now()))
    conn.commit()
    conn.close()
    return True, "Quotation published."


def set_quotation_status(quotation_id: int, buyer_id: int, status: str) -> bool:
    if status not in ("open", "closed"):
        return False
    conn = auth_db.get_db_connection()
    cur = conn.execute("UPDATE buyer_quotations SET status = ? WHERE id = ? AND buyer_id = ?",
                       (status, quotation_id, buyer_id))
    conn.commit()
    conn.close()
    return cur.rowcount == 1


def list_buyer_quotations(buyer_id: int) -> List[Dict[str, Any]]:
    conn = auth_db.get_db_connection()
    rows = conn.execute("""
    SELECT q.*,
           (SELECT COUNT(*) FROM connection_requests r WHERE r.quotation_id = q.id AND r.status = 'pending') AS pending_requests
    FROM buyer_quotations q WHERE q.buyer_id = ? ORDER BY q.status DESC, q.created_at DESC
    """, (buyer_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_open_quotations(commodity: Optional[str] = None) -> List[Dict[str, Any]]:
    """Open, unexpired quotations joined with their buyer profile."""
    today = datetime.date.today().isoformat()
    sql = """
    SELECT q.*, b.business_name, b.buyer_type, b.location_label, b.latitude, b.longitude,
           b.is_demo, b.user_id AS buyer_user_id
    FROM buyer_quotations q JOIN buyer_profiles b ON q.buyer_id = b.id
    WHERE q.status = 'open' AND (q.valid_until IS NULL OR q.valid_until >= ?)
    """
    params: List[Any] = [today]
    if commodity:
        sql += " AND LOWER(q.commodity) = LOWER(?)"
        params.append(commodity)
    conn = auth_db.get_db_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def quoted_commodities() -> List[str]:
    return sorted({q["commodity"] for q in list_open_quotations()})


# ------------------------------------------------------------------------------
# Matching engine
# ------------------------------------------------------------------------------
def grade_accepts(quote_grade: str, farmer_grade: str) -> bool:
    if quote_grade == "Any grade":
        return True
    if quote_grade == "FAQ":
        return farmer_grade in ("FAQ", "Grade A (Premium)")
    return farmer_grade == quote_grade


def match_buyers(
    quotations: List[Dict[str, Any]],
    quantity_kg: float,
    farmer_grade: str,
    farm_lat: float,
    farm_lon: float,
    vehicle_config: Dict[str, Any],
    fair_price_kg: Optional[float] = None,
    max_distance_km: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Scores each quotation for a farmer's lot. Eligible matches (grade accepted,
    quantity at or above the buyer's minimum, within range) rank first by net
    take-home per kg, then by how much of the lot the buyer can absorb.
    """
    results = []
    for q in quotations:
        distance_km, duration_sec = estimate_road_distance_demo(farm_lat, farm_lon, q["latitude"], q["longitude"])
        sellable = min(float(quantity_kg), float(q["max_qty_kg"]))
        reasons = []
        if not grade_accepts(q["grade"], farmer_grade):
            reasons.append(f"Buys {q['grade']} only")
        if quantity_kg < q["min_qty_kg"]:
            reasons.append(f"Minimum {q['min_qty_kg']:,.0f} kg")
        if max_distance_km is not None and distance_km > max_distance_km:
            reasons.append(f"{distance_km:,.0f} km away")

        buyer_collects = q["pickup"] == PICKUP_OPTIONS[0]
        transport = 0.0
        if not buyer_collects and sellable > 0:
            transport = calculate_transport_cost(sellable, distance_km, duration_sec, vehicle_config)["total_transport_cost"]
        gross = q["price_per_kg"] * sellable
        net = gross - transport
        net_per_kg = net / sellable if sellable > 0 else 0.0

        fairness = None
        if fair_price_kg:
            audit = evaluate_buyer_offer(q["price_per_kg"], max(sellable, 1.0), fair_price_kg,
                                         fair_price_kg * 0.88, payment_terms=q["payment_terms"])
            fairness = {"status": audit["status"], "color": audit["badge_color"],
                        "delta_pct": audit["delta_pct"], "risk_flags": audit["risk_flags"]}

        results.append({
            **q,
            "distance_km": round(distance_km, 1),
            "is_local": distance_km <= LOCAL_RADIUS_KM,
            "buyer_collects": buyer_collects,
            "sellable_kg": round(sellable, 1),
            "fill_pct": round(sellable / quantity_kg * 100, 1) if quantity_kg else 0.0,
            "transport_cost": round(transport, 2),
            "gross_value": round(gross, 2),
            "net_value": round(net, 2),
            "net_per_kg": round(net_per_kg, 2),
            "eligible": not reasons,
            "reasons": reasons,
            "fairness": fairness,
        })
    results.sort(key=lambda r: (not r["eligible"], -r["net_per_kg"], -r["fill_pct"], r["distance_km"]))
    return results


# ------------------------------------------------------------------------------
# Connection requests
# ------------------------------------------------------------------------------
def create_connection_request(quotation_id: int, farmer_user_id: int, quantity_kg: float,
                              asking_price_kg: float, message: str = "") -> Tuple[bool, str]:
    if quantity_kg <= 0 or asking_price_kg <= 0:
        return False, "Quantity and price must be above zero."
    conn = auth_db.get_db_connection()
    q = conn.execute("SELECT status FROM buyer_quotations WHERE id = ?", (quotation_id,)).fetchone()
    if not q or q["status"] != "open":
        conn.close()
        return False, "This quotation is no longer open."
    dup = conn.execute("""
    SELECT id FROM connection_requests WHERE quotation_id = ? AND farmer_user_id = ? AND status = 'pending'
    """, (quotation_id, farmer_user_id)).fetchone()
    if dup:
        conn.close()
        return False, "You already have a pending request for this quotation."
    now = _now()
    conn.execute("""
    INSERT INTO connection_requests (quotation_id, farmer_user_id, quantity_kg, asking_price_kg, message,
                                     status, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (quotation_id, farmer_user_id, float(quantity_kg), float(asking_price_kg), (message or "").strip(), now, now))
    conn.commit()
    conn.close()
    return True, "Request sent. The buyer will see it in their desk."


def list_farmer_requests(farmer_user_id: int) -> List[Dict[str, Any]]:
    conn = auth_db.get_db_connection()
    rows = conn.execute("""
    SELECT r.*, q.commodity, q.grade, q.price_per_kg, q.pickup, q.payment_terms,
           b.business_name, b.buyer_type, b.location_label, b.is_demo,
           CASE WHEN r.status = 'accepted' THEN COALESCE(b.phone, u.phone) END AS buyer_phone
    FROM connection_requests r
    JOIN buyer_quotations q ON r.quotation_id = q.id
    JOIN buyer_profiles b ON q.buyer_id = b.id
    JOIN users u ON b.user_id = u.id
    WHERE r.farmer_user_id = ?
    ORDER BY r.created_at DESC
    """, (farmer_user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_buyer_requests(buyer_id: int) -> List[Dict[str, Any]]:
    conn = auth_db.get_db_connection()
    rows = conn.execute("""
    SELECT r.*, q.commodity, q.grade, q.price_per_kg, q.pickup,
           u.full_name AS farmer_name,
           f.farm_name, f.village, f.district, f.state, f.latitude AS farm_lat, f.longitude AS farm_lon,
           CASE WHEN r.status = 'accepted' THEN u.phone END AS farmer_phone
    FROM connection_requests r
    JOIN buyer_quotations q ON r.quotation_id = q.id
    JOIN users u ON r.farmer_user_id = u.id
    LEFT JOIN farm_profiles f ON f.user_id = u.id
    WHERE q.buyer_id = ?
    ORDER BY CASE r.status WHEN 'pending' THEN 0 ELSE 1 END, r.created_at DESC
    """, (buyer_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def respond_to_request(request_id: int, buyer_id: int, accept: bool) -> bool:
    """Buyer accepts or declines a pending request on one of their own quotations."""
    conn = auth_db.get_db_connection()
    cur = conn.execute("""
    UPDATE connection_requests SET status = ?, updated_at = ?
    WHERE id = ? AND status = 'pending'
      AND quotation_id IN (SELECT id FROM buyer_quotations WHERE buyer_id = ?)
    """, ("accepted" if accept else "declined", _now(), request_id, buyer_id))
    conn.commit()
    conn.close()
    return cur.rowcount == 1


def withdraw_request(request_id: int, farmer_user_id: int) -> bool:
    conn = auth_db.get_db_connection()
    cur = conn.execute("""
    UPDATE connection_requests SET status = 'withdrawn', updated_at = ?
    WHERE id = ? AND farmer_user_id = ? AND status = 'pending'
    """, (_now(), request_id, farmer_user_id))
    conn.commit()
    conn.close()
    return cur.rowcount == 1


# Ensure tables and demo listings exist on import (mirrors auth_db.init_db)
init_buyer_tables()
seed_demo_buyers()
