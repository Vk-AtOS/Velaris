"""Supply-chain agents that used to be stubs: hand-checked numbers, edges and bad input."""
import math

import pytest

from velaris.agents.FLEET_HEALTH_ENGINE.main import FleetHealthEngine, VehicleStatus
from velaris.agents.INVENTORY_DECISION_ENGINE.main import InventoryDecisionEngine, InventoryInput
from velaris.agents.MACHINE_LIFECYCLE_ENGINE.main import MachineLifecycleEngine, MachineLifecycleInput
from velaris.agents.ROUTE_OPTIMIZATION_ENGINE.main import RouteOptimizationEngine, RouteRequest
from velaris.agents.SUPPLY_CHAIN_ENGINE.main import SupplyChainEngine, SupplyChainInput
from velaris.agents.WAREHOUSE_FLOW_ENGINE.main import WarehouseFlowEngine, WarehouseFlowInput


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


# ---- FLEET_HEALTH_ENGINE ---------------------------------------------------------

def vehicle(**over):
    return VehicleStatus(**{"vehicle_id": "TN09-AB-1234", "mileage": 52000, "engine_hours": 2000,
                            "fault_codes": {}, "wear_metrics": {"tire_wear": 40}, "usage_pattern": "city", **over})


def test_fleet_service_due_and_wear_rules():
    r = FleetHealthEngine().assess(vehicle(wear_metrics={"tire_wear": 75, "brake_wear": 85, "battery_health": 90}),
                                   last_service_km=40000, service_interval_km=10000)
    assert r["condition"] == "attention" and r["km_per_engine_hour"] == 26.0
    assert r["service"] == {"status": "ok", "km_since_service": 12000, "interval_km": 10000,
                            "km_until_due": -2000, "due": True}
    rules = {a["rule"]: a["action"] for a in r["actions"]}
    assert rules["wear:brake_wear"].startswith("Replace") and rules["wear:tire_wear"].startswith("Inspect")
    assert "wear:battery_health" not in rules and "overdue by 2000 km" in rules["service:interval"]


def test_fleet_brake_fault_grounds_and_missing_interval_is_needs_data():
    r = FleetHealthEngine().assess(vehicle(fault_codes={"brake_fault": True, "sensor_fault": False}))
    assert r["condition"] == "out_of_service" and r["actions"][0]["rule"] == "fault:brake_fault"
    assert r["service"]["status"] == "needs_data"
    clean = FleetHealthEngine().assess(vehicle(), last_service_km=50000, service_interval_km=10000)
    assert clean["condition"] == "serviceable" and clean["actions"] == []
    weak_battery = FleetHealthEngine().assess(vehicle(wear_metrics={"battery_health": 35}))
    assert weak_battery["actions"][0]["action"] == "Replace or overhaul battery."


def test_fleet_bad_input():
    eng = FleetHealthEngine()
    assert eng.assess(vehicle(wear_metrics={"tire_wear": 140}))["errors"] == ["wear metric tire_wear out of range"]
    assert eng.assess(vehicle(wear_metrics={"paint": 1}))["errors"] == ["unsupported wear metric paint"]
    assert eng.assess(vehicle(), last_service_km=60000, service_interval_km=10000)["status"] == "failed"
    assert eng.assess(vehicle(mileage="far", fault_codes=None))["status"] == "failed"
    assert eng.assess(vehicle(), wear_limits={"tire_wear": 0})["status"] == "failed"


# ---- INVENTORY_DECISION_ENGINE ----------------------------------------------------

def item(**over):
    return InventoryInput(**{"item_id": "toner", "avg_demand": 10, "demand_variance": 4, "lead_time": 9,
                             "holding_cost": 2, "shortage_cost": 50, "order_cost": 100, "max_capacity": 1000,
                             "constraints": {}, **over})


def test_inventory_safety_stock_rop_eoq():
    r = InventoryDecisionEngine().compute(item())
    # z(95%) = 1.6449; SS = 1.6449 x 2 x 3 = 9.87 -> 10; ROP = 90 + 10 = 100; EOQ = sqrt(2 x 3650 x 100 / 2) = 604.2 -> 605
    assert (r["z"], r["safety_stock"], r["reorder_point"], r["order_quantity"]) == (1.6449, 10, 100, 605)
    assert r["orders_per_year"] == round(3650 / 605, 2)
    priority = InventoryDecisionEngine().compute(item(constraints={"priority_item": True, "fragile": False}))
    # z(99%) = 2.3263; SS = 13.96 -> 14
    assert (priority["service_level"], priority["safety_stock"], priority["constraints_not_applied"]) == (0.99, 14, [])


def test_inventory_refuses_flags_it_has_no_rule_for_and_uses_shortage_cost():
    """KAN-70: perishable/fragile/bulk_item=true used to be accepted and ignored; shortage_cost used to be dead."""
    for flag in ("perishable", "fragile", "bulk_item"):
        r = InventoryDecisionEngine().compute(item(constraints={flag: True}))
        assert r["status"] == "failed" and flag in str(r)
    base = InventoryDecisionEngine().compute(item())
    # sigma_L = 2 x 3 = 6; G(1.6449) = 0.0206 -> 0.1236 units short per cycle; x 50 x (3650/605) cycles = about 37.3
    assert 0.12 < base["expected_units_short_per_cycle"] < 0.13 and 36 < base["expected_shortage_cost_per_year"] < 38.5
    assert InventoryDecisionEngine().compute(item(), service_level=0.999)["expected_shortage_cost_per_year"] < base["expected_shortage_cost_per_year"]


def test_inventory_caps_and_zero_holding_cost():
    capped = InventoryDecisionEngine().compute(item(max_capacity=50))
    assert (capped["order_quantity"], capped["reorder_point"], capped["reorder_point_uncapped"]) == (50, 50, 100)
    assert len(capped["notes"]) == 2
    free = InventoryDecisionEngine().compute(item(holding_cost=0))
    assert free["eoq_uncapped"] is None and free["order_quantity"] == 1000


def test_inventory_bad_input():
    eng = InventoryDecisionEngine()
    assert eng.compute(item(avg_demand=-1))["errors"] == ["avg_demand invalid"]
    assert eng.compute(item(), service_level=1.2)["status"] == "failed"
    assert eng.compute(item(lead_time=None, constraints=[]))["status"] == "failed"


# ---- MACHINE_LIFECYCLE_ENGINE ------------------------------------------------------

def machine(**over):
    return MachineLifecycleInput(**{"machine_id": "cnc-1", "install_year": 2020, "operating_hours": 12000,
                                    "maintenance_events": {"preventive": 6, "corrective": 3, "minor_repair": 1},
                                    "component_age": {"bearing": 6, "motor": 2}, "load_factor": 1.2, **over})


def test_machine_lifecycle_mtbf_and_remaining_life():
    r = MachineLifecycleEngine().assess(machine(), expected_life_hours=60000,
                                        component_life={"bearing": 5, "motor": 10}, as_of_year=2026)
    # age 6; 2000 h/yr; MTBF 12000 / 4 = 3000; preventive 6/10
    assert (r["age_years"], r["hours_per_year"], r["mtbf_hours"], r["preventive_share"]) == (6, 2000.0, 3000.0, 0.6)
    # effective life 60000 / 1.2 = 50000; 38000 left; 19 years at 2000 h/yr
    rul = r["remaining_useful_life"]
    assert (rul["effective_life_hours"], rul["remaining_hours"], rul["remaining_years"], rul["life_used"]) == \
        (50000.0, 38000.0, 19.0, 0.24)
    assert r["components"]["due_for_replacement"] == ["bearing"] and r["needs_data"] == []


def test_machine_lifecycle_without_design_life_and_new_machine():
    r = MachineLifecycleEngine().assess(machine(install_year=2026, maintenance_events={}), as_of_year=2026)
    assert r["remaining_useful_life"]["status"] == "needs_data" and r["components"]["status"] == "needs_data"
    assert (r["hours_per_year"], r["mtbf_hours"], r["preventive_share"]) == (None, None, None)
    assert r["needs_data"] == ["expected_life_hours", "component_life"]
    worn = MachineLifecycleEngine().assess(machine(), expected_life_hours=10000, as_of_year=2026)
    assert worn["remaining_useful_life"]["past_design_life"] is True
    assert worn["remaining_useful_life"]["remaining_years"] == 0.0


def test_machine_lifecycle_bad_input():
    eng = MachineLifecycleEngine()
    assert eng.assess(machine(install_year=2030), as_of_year=2026)["errors"] == ["install_year invalid"]
    assert eng.assess(machine(maintenance_events={"corrective": -1}))["status"] == "failed"
    assert eng.assess(machine(), expected_life_hours=0)["status"] == "failed"
    assert eng.assess(machine(load_factor="heavy"))["status"] == "failed"


# ---- ROUTE_OPTIMIZATION_ENGINE ---------------------------------------------------------

POINTS = {"A": (20, 15), "B": (2, 11), "C": (2, 13), "D": (4, 0), "E": (9, 13), "F": (13, 3), "G": (1, 19)}


def matrix(points):
    return {a: {b: round(math.dist(points[a], points[b]), 3) for b in points if b != a} for a in points}


def test_route_two_opt_improves_nearest_neighbour_to_the_optimum():
    r = RouteOptimizationEngine().compute_route(RouteRequest("r1", list(POINTS), matrix(POINTS), {}, {}))
    # checked by brute force over all 720 tours from A: the shortest is 63.822; nearest neighbour gives 70.856
    assert r["route"] == ["A", "E", "G", "C", "B", "D", "F", "A"]
    assert (r["nearest_neighbour_cost"], r["total_cost"], r["total_distance"]) == (70.856, 63.822, 63.822)
    assert r["improvement_by_2opt"] == 7.034 and r["time_windows_applied"] is False


def test_route_depot_traffic_and_one_way_fallback():
    d = {"Depot": {"X": 1, "Y": 4}, "X": {"Y": 2}}           # Y->X etc. fall back to the reverse distance
    r = RouteOptimizationEngine().compute_route(RouteRequest("r2", ["X", "Depot", "Y"], d, {}, {"Y": 2.0}),
                                                depot="Depot")
    assert r["route"][0] == r["route"][-1] == "Depot" and r["total_distance"] == 7
    # any 3-stop tour covers each edge once; Y is entered once, so cost = 7 + 2 (if entered via X) or + 4 (via Depot)
    assert r["total_cost"] == 9.0 and r["route"] == ["Depot", "X", "Y", "Depot"]


def test_route_bad_input():
    eng = RouteOptimizationEngine()
    assert eng.compute_route(RouteRequest("r", ["A"], {}, {}, {}))["errors"] == ["invalid location count"]
    assert eng.compute_route(RouteRequest("r", ["A", "B", "C"], {"A": {"B": 1}}, {}, {}))["errors"][0].startswith(
        "missing distance")
    assert eng.compute_route(RouteRequest("r", ["A", "B"], {"A": {"B": -1}}, {}, {}))["status"] == "failed"
    assert eng.compute_route(RouteRequest("r", ["A", "B"], {"A": {"B": 1}}, {}, {}), depot="Z")["status"] == "failed"
    assert eng.compute_route(RouteRequest("r", "AB", None, {}, {}))["status"] == "failed"


# ---- SUPPLY_CHAIN_ENGINE ------------------------------------------------------------

def test_supply_chain_simulation_by_hand():
    r = SupplyChainEngine().compute_plan(SupplyChainInput("sc", [10, 10, 10, 10, 10], 2, 5, 1, 20, 40))
    # s = 5 + 10 x 2 = 25, S = 40. Day 0: 40-10 = 30. Day 1: 20 <= 25 -> order 20, arrives day 3.
    # Day 2: 10 (position 30). Day 3: +20 -> 30 - 10 = 20, position 20 -> order 20 for day 5. Day 4: 10.
    assert r["reorder_point"] == 25 and [o["period"] for o in r["orders"]] == [1, 3]
    assert [p["closing_stock"] for p in r["schedule"]] == [30, 20, 10, 20, 10]
    assert (r["units_short"], r["fill_rate"], r["holding_cost_total"], r["total_cost"]) == (0, 1.0, "90.00", "90.00")
    assert r["orders_outstanding_at_end"] == [{"arrives": 5, "quantity": 20}]


def test_supply_chain_shortage_is_costed():
    r = SupplyChainEngine().compute_plan(SupplyChainInput("sc", [30, 30], 1, 0, 1, 20, 40), opening_stock=20)
    # day 0: 20 served, 10 short, order 40 (position 0 <= 30) arriving day 1; day 1: 40 - 30 = 10
    assert (r["units_short"], r["shortage_cost_total"], r["holding_cost_total"]) == (10, "200.00", "10.00")
    assert r["fill_rate"] == round(1 - 10 / 60, 4)


def test_supply_chain_bad_input():
    eng = SupplyChainEngine()
    assert eng.compute_plan(SupplyChainInput("sc", [], 1, 0, 1, 1, 10))["errors"] == ["demand_forecast invalid"]
    assert eng.compute_plan(SupplyChainInput("sc", [1, -2], 1, 0, 1, 1, 10))["status"] == "failed"
    assert eng.compute_plan(SupplyChainInput("sc", "123", "1", 0, 1, 1, 10))["status"] == "failed"
    assert eng.compute_plan(SupplyChainInput("sc", [1], 1, 0, 1, 1, 10), opening_stock=-5)["status"] == "failed"


# ---- WAREHOUSE_FLOW_ENGINE ----------------------------------------------------------

def warehouse(**over):
    return WarehouseFlowInput(**{"warehouse_id": "chennai-1", "inbound_units": 1000, "outbound_units": 800,
                                 "storage_capacity": 5000, "picking_efficiency": 0.9, "putaway_efficiency": 0.8,
                                 "congestion_flags": {}, **over})


def test_warehouse_flow_arithmetic():
    r = WarehouseFlowEngine().assess(warehouse(), opening_stock=3000)
    # put away 800, dock backlog 200; picked 720, backlog 80; closing 3080; util 0.616; 1920 free / 80 = 24 periods
    assert (r["put_away"], r["dock_backlog"], r["picked"], r["pick_backlog"]) == (800, 200, 720, 80)
    assert (r["closing_stock"], r["utilisation"], r["periods_until_full"]) == (3080, 0.616, 24)


def test_warehouse_flags_checked_against_numbers_and_stock_limit():
    r = WarehouseFlowEngine().assess(warehouse(congestion_flags={"storage_overflow": True, "aisle_block": False}))
    assert [c["flag"] for c in r["congestion"]] == ["storage_overflow"]
    assert r["picked"] == 720 and r["closing_stock"] == 80
    assert any("storage_overflow is raised" in f for f in r["findings"])
    empty = WarehouseFlowEngine().assess(warehouse(inbound_units=0))
    assert empty["picked"] == 0 and any("only 0 of 720" in f for f in empty["findings"])


def test_warehouse_bad_input():
    eng = WarehouseFlowEngine()
    assert eng.assess(warehouse(picking_efficiency=0))["errors"] == ["picking_efficiency invalid"]
    assert eng.assess(warehouse(), opening_stock=-1)["errors"] == ["opening_stock invalid"]
    assert eng.assess(warehouse(congestion_flags={"fog": True}))["status"] == "failed"
    assert eng.assess(warehouse(inbound_units="lots"))["status"] == "failed"


def test_route_refuses_time_windows_it_cannot_honour():
    """KAN-70: windows were accepted, ignored, and the tour reported as fine."""
    r = RouteOptimizationEngine().compute_route(RouteRequest("r", ["A", "B"], {"A": {"B": 1}}, {"B": [0, 5]}, {}))
    assert r["status"] == "failed" and "time_windows" in str(r)
