"""
Test Suite for the Buyer Network (modules/buyer_network.py).
Runs against a temporary SQLite database, so data/krishi_ai.db is never modified.
"""
import os
import sys
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Point the account database at a temp file BEFORE the buyer module initialises its tables
from modules import auth_db  # noqa: E402

_tmp_dir = tempfile.mkdtemp(prefix="krishi_test_")
auth_db.DB_PATH = os.path.join(_tmp_dir, "test.db")
auth_db.init_db()

from modules import buyer_network as bn  # noqa: E402  (seeds demo buyers into the temp DB)
from modules.transport_engine import DEFAULT_VEHICLE_CONFIGS  # noqa: E402

FARM_LAT, FARM_LON = 12.7209, 77.2799  # Ramanagara
MINI_TRUCK = DEFAULT_VEHICLE_CONFIGS["Mini Truck (Normal)"]


def quote(**overrides):
    base = {
        "id": 1, "commodity": "Tomato", "grade": "Any grade", "price_per_kg": 15.0,
        "min_qty_kg": 100.0, "max_qty_kg": 5000.0, "payment_terms": bn.PAYMENT_TERMS[0],
        "pickup": bn.PICKUP_OPTIONS[0], "notes": "", "latitude": 12.7159, "longitude": 77.2810,
        "business_name": "Test Buyer", "buyer_type": "Local Dealer", "location_label": "Ramanagara, Karnataka",
        "is_demo": 0,
    }
    base.update(overrides)
    return base


def run_tests():
    print("=" * 65)
    print("RUNNING BUYER NETWORK VERIFICATION (temporary database)")
    print("=" * 65)

    # 1. Demo seed is labelled and idempotent
    print("\n[Test 1] Demo buyers are seeded once and flagged...")
    n_before = len(bn.list_open_quotations())
    bn.seed_demo_buyers()
    assert len(bn.list_open_quotations()) == n_before > 0
    assert all(q["is_demo"] == 1 for q in bn.list_open_quotations())
    assert "Tomato" in bn.quoted_commodities()
    print(f"  -> PASS: {n_before} demo quotations, re-seeding adds none.")

    # 2. Buyer who collects at the farm beats a higher quote that needs delivery far away
    print("\n[Test 2] Ranking uses take-home after freight, not headline price...")
    near = quote(id=1, price_per_kg=15.0, pickup=bn.PICKUP_OPTIONS[0])
    far = quote(id=2, price_per_kg=16.0, pickup=bn.PICKUP_OPTIONS[1], latitude=13.1367, longitude=78.1291)
    res = bn.match_buyers([far, near], 500, "FAQ", FARM_LAT, FARM_LON, MINI_TRUCK)
    assert res[0]["id"] == 1, res
    assert res[1]["transport_cost"] > 0 and res[0]["transport_cost"] == 0
    assert res[0]["net_per_kg"] == 15.0
    print(f"  -> PASS: collect-at-farm ₹{res[0]['net_per_kg']:.2f}/kg beats delivered ₹{res[1]['net_per_kg']:.2f}/kg")

    # 3. Eligibility: grade, minimum quantity, radius
    print("\n[Test 3] Grade, minimum quantity and radius rules...")
    premium_only = quote(id=3, grade="Grade A (Premium)")
    big_min = quote(id=4, min_qty_kg=2000)
    distant = quote(id=5, latitude=12.2958, longitude=76.6394)
    res = {r["id"]: r for r in bn.match_buyers([premium_only, big_min, distant], 500, "FAQ",
                                               FARM_LAT, FARM_LON, MINI_TRUCK, max_distance_km=60)}
    assert not res[3]["eligible"] and "Grade A" in res[3]["reasons"][0]
    assert not res[4]["eligible"] and "Minimum" in res[4]["reasons"][0]
    assert not res[5]["eligible"] and "km away" in res[5]["reasons"][0]
    assert bn.grade_accepts("FAQ", "Grade A (Premium)") and not bn.grade_accepts("Grade A (Premium)", "FAQ")
    print("  -> PASS: ineligible buyers carry a reason and rank last.")

    # 4. Partial fill when the lot exceeds the buyer's maximum
    print("\n[Test 4] Lot larger than buyer maximum is partially filled...")
    res = bn.match_buyers([quote(id=6, max_qty_kg=300)], 1000, "FAQ", FARM_LAT, FARM_LON, MINI_TRUCK)
    assert res[0]["sellable_kg"] == 300 and res[0]["fill_pct"] == 30.0
    print("  -> PASS: 300 of 1,000 kg (30%).")

    # 5. Fairness audit against the mandi benchmark
    print("\n[Test 5] Quotes are rated against fair mandi parity...")
    res = bn.match_buyers([quote(id=7, price_per_kg=6.0), quote(id=8, price_per_kg=18.0)], 500, "FAQ",
                          FARM_LAT, FARM_LON, MINI_TRUCK, fair_price_kg=15.0)
    by_id = {r["id"]: r for r in res}
    assert "PREDATORY" in by_id[7]["fairness"]["status"]
    assert "PREMIUM" in by_id[8]["fairness"]["status"]
    print(f"  -> PASS: ₹6 rated '{by_id[7]['fairness']['status']}', ₹18 rated '{by_id[8]['fairness']['status']}'")

    # 6. Request lifecycle with data isolation and contact reveal
    print("\n[Test 6] Connect, duplicate guard, buyer isolation, accept, contact reveal...")
    ok, _, _, farmer = auth_db.authenticate_user("farmer@krishiai.com", "Password@123")
    assert ok
    tomato = [q for q in bn.list_open_quotations("Tomato") if q["business_name"].startswith("Ramanagara")][0]
    other = [q for q in bn.list_open_quotations("Tomato") if q["buyer_id"] != tomato["buyer_id"]][0]
    ok, msg = bn.create_connection_request(tomato["id"], farmer["id"], 700, 16.0, "Harvest Friday")
    assert ok, msg
    dup_ok, dup_msg = bn.create_connection_request(tomato["id"], farmer["id"], 700, 16.0)
    assert not dup_ok and "pending" in dup_msg
    req = bn.list_farmer_requests(farmer["id"])[0]
    assert req["status"] == "pending" and req["buyer_phone"] is None
    assert not bn.respond_to_request(req["id"], other["buyer_id"], True), "Another buyer must not answer"
    assert bn.respond_to_request(req["id"], tomato["buyer_id"], True)
    req = bn.list_farmer_requests(farmer["id"])[0]
    assert req["status"] == "accepted" and req["buyer_phone"]
    seen = bn.list_buyer_requests(tomato["buyer_id"])[0]
    assert seen["farmer_phone"] and seen["farmer_name"] == "Ramesh Gowda"
    assert bn.list_buyer_requests(other["buyer_id"]) == []
    print("  -> PASS: request accepted only by its own buyer; phones shared after acceptance.")

    # 7. Withdraw only pending requests, only your own
    print("\n[Test 7] Withdrawal rules...")
    ok, _ = bn.create_connection_request(other["id"], farmer["id"], 500, other["price_per_kg"])
    pending = [r for r in bn.list_farmer_requests(farmer["id"]) if r["status"] == "pending"][0]
    assert not bn.withdraw_request(pending["id"], farmer["id"] + 999)
    assert bn.withdraw_request(pending["id"], farmer["id"])
    assert not bn.withdraw_request(pending["id"], farmer["id"]), "Already withdrawn"
    print("  -> PASS")

    # 8. Quotation validation and close/reopen
    print("\n[Test 8] Quotation validation and status changes...")
    bad, msg = bn.create_quotation(tomato["buyer_id"], {"commodity": "Onion", "grade": "FAQ", "price_per_kg": 10,
                                                         "min_qty_kg": 900, "max_qty_kg": 100,
                                                         "payment_terms": bn.PAYMENT_TERMS[0], "pickup": bn.PICKUP_OPTIONS[0]})
    assert not bad
    ok, msg = bn.create_quotation(tomato["buyer_id"], {"commodity": "Onion", "grade": "FAQ", "price_per_kg": 10,
                                                        "min_qty_kg": 100, "max_qty_kg": 900,
                                                        "payment_terms": bn.PAYMENT_TERMS[0], "pickup": bn.PICKUP_OPTIONS[0]})
    assert ok, msg
    onion = [q for q in bn.list_buyer_quotations(tomato["buyer_id"]) if q["commodity"] == "Onion"][0]
    assert not bn.set_quotation_status(onion["id"], other["buyer_id"], "closed"), "Only the owner can close"
    assert bn.set_quotation_status(onion["id"], tomato["buyer_id"], "closed")
    assert all(q["id"] != onion["id"] for q in bn.list_open_quotations("Onion"))
    print("  -> PASS: invalid ranges rejected; only the owner can close; closed quotes are hidden.")

    print("\n" + "=" * 65)
    print("ALL 8 BUYER NETWORK TESTS PASSED")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
