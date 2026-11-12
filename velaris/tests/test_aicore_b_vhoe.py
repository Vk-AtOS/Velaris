"""VHOE family: work routing, queue assignment, completion analytics, planning."""
from velaris.agents.VHOE_ANALYTICS.main import VHOE_ANALYTICSAgent
from velaris.agents.VHOE_CORE.main import VHOE_COREAgent
from velaris.agents.VHOE_OPTIMIZER.main import VHOE_OPTIMIZERAgent
from velaris.agents.VHOE_ROUTER.main import VHOE_ROUTERAgent

WORKERS = [
    {"id": "asha", "skills": ["payroll", "tax"], "capacity": 8, "load": 6},
    {"id": "ravi", "skills": ["payroll"], "capacity": 8, "load": 2},
    {"id": "bot-1", "skills": ["tax"], "capacity": 4},
]
H = 3600


def test_router_picks_least_utilised_qualified_worker():
    r = VHOE_ROUTERAgent().route({"id": "t1", "skill": "payroll", "effort": 2}, WORKERS)
    assert r["status"] == "ok" and r["worker"] == "ravi" and r["utilisation_after"] == 0.5 and r["candidates"] == 2
    assert VHOE_ROUTERAgent().route({"id": "t2", "skill": "tax"}, WORKERS)["worker"] == "bot-1"


def test_router_says_why_nobody_can_take_it():
    router = VHOE_ROUTERAgent()
    assert router.route({"id": "t", "skill": "legal"}, WORKERS)["cause"] == "no_skill"
    full = router.route({"id": "t", "skill": "payroll", "effort": 7}, WORKERS)
    assert full["status"] == "unassigned" and full["cause"] == "no_capacity" and full["worker"] is None
    exact = router.route({"id": "t", "skill": "payroll", "effort": 6}, WORKERS)      # exactly fills ravi
    assert exact["worker"] == "ravi" and exact["utilisation_after"] == 1.0


def test_router_bad_input():
    router = VHOE_ROUTERAgent()
    assert router.route({"id": "t"}, WORKERS)["status"] == "invalid_input"
    assert router.route({"id": "t", "skill": "tax", "effort": 0}, WORKERS)["status"] == "invalid_input"
    assert router.route({"id": "t", "skill": "tax"}, [])["status"] == "invalid_input"
    assert router.route({"id": "t", "skill": "tax"}, [{"id": "w", "skills": "tax", "capacity": 1}])["status"] \
        == "invalid_input"
    assert router.route("task", WORKERS)["worker"] is None


def test_optimizer_gives_capacity_to_important_work_first():
    items = [
        {"id": "low", "skill": "tax", "effort": 4, "priority": 5},
        {"id": "high", "skill": "tax", "effort": 4, "priority": 1},
        {"id": "mid", "skill": "tax", "effort": 2, "priority": 3, "due": 10},
        {"id": "mid-late", "skill": "tax", "effort": 2, "priority": 3, "due": 99},
    ]
    r = VHOE_OPTIMIZERAgent().optimize(items, WORKERS)
    assert [a["item"] for a in r["assignments"]] == ["high", "mid"]
    assert r["assignments"][0]["worker"] == "bot-1" and r["assignments"][1]["worker"] == "asha"
    assert [u["item"] for u in r["unassigned"]] == ["mid-late", "low"]
    assert r["utilisation"] == {"asha": 1.0, "ravi": 0.25, "bot-1": 1.0}
    assert WORKERS[0]["load"] == 6                                       # callers' data is not modified


def test_optimizer_empty_queue_and_bad_input():
    opt = VHOE_OPTIMIZERAgent()
    empty = opt.optimize([], WORKERS)
    assert empty["status"] == "ok" and empty["assignments"] == [] and empty["utilisation"]["ravi"] == 0.25
    assert opt.optimize([{"id": "a", "skill": "tax"}], [])["status"] == "invalid_input"
    assert opt.optimize([{"id": "a", "skill": "tax"}, {"id": "a", "skill": "tax"}], WORKERS)["status"] \
        == "invalid_input"
    assert opt.optimize([{"id": "a", "skill": "tax", "priority": "high"}], WORKERS)["status"] == "invalid_input"
    assert opt.optimize("queue", WORKERS)["assignments"] == []


def test_analytics_cycle_time_lateness_and_per_worker():
    records = [
        {"id": 1, "worker": "asha", "started": 0, "finished": 2 * H, "due": 3 * H},
        {"id": 2, "worker": "asha", "started": 0, "finished": 4 * H, "due": 3 * H},
        {"id": 3, "worker": "ravi", "started": 0, "finished": 6 * H},
        {"id": 4, "worker": "ravi", "started": 5 * H, "finished": 4 * H},      # finished before it started
        {"id": 5, "worker": "ravi", "started": "soon"},
    ]
    r = VHOE_ANALYTICSAgent().analyse(records)
    assert r["completed"] == 3 and r["skipped"] == 2
    assert r["cycle_time"]["mean_hours"] == 4.0 and r["cycle_time"]["median_hours"] == 4.0
    assert r["late"] == 1 and r["late_rate"] == 0.5                       # only records with a due time count
    assert r["per_worker"]["asha"] == {"completed": 2, "mean_hours": 3.0, "median_hours": 3.0,
                                       "p90_hours": 3.8, "late": 1}
    assert r["per_worker"]["ravi"]["completed"] == 1 and r["per_worker"]["ravi"]["p90_hours"] == 6.0


def test_analytics_no_data_and_bad_input():
    a = VHOE_ANALYTICSAgent()
    assert a.analyse([])["status"] == "no_data"
    assert a.analyse([{"id": 1}, "x", None])["skipped"] == 3
    assert a.analyse("records")["status"] == "invalid_input"
    single = a.analyse([{"worker": "w", "started": 0, "finished": H}])
    assert single["cycle_time"]["p90_hours"] == 1.0 and single["late_rate"] is None


def test_core_plan_flags_what_needs_attention():
    items = [{"id": "a", "skill": "tax", "effort": 4}, {"id": "b", "skill": "legal"}]
    history = [{"worker": "asha", "started": 0, "finished": 5 * H, "due": H},
               {"worker": "asha", "started": 0, "finished": H, "due": 2 * H}]
    r = VHOE_COREAgent().plan(items, WORKERS, history)
    assert r["status"] == "ok" and r["assignments"] == [{"item": "a", "worker": "bot-1", "effort": 4.0}]
    assert r["history"]["late_rate"] == 0.5
    assert r["flags"] == ["1 item(s) could not be assigned", "bot-1 is at 100% of capacity",
                          "50% of past work with a due time finished late"]


def test_core_quiet_plan_and_bad_input():
    core = VHOE_COREAgent()
    calm = core.plan([{"id": "a", "skill": "payroll"}], WORKERS)
    assert calm["flags"] == [] and "history" not in calm
    bad = core.plan([{"id": "a"}], WORKERS)
    assert bad["status"] == "invalid_input" and bad["flags"] == []
