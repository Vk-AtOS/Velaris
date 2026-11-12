"""Auto-learn core: a ledger of which option worked, per context.

record() counts one success or failure for an option in a context ("which
reminder channel gets invoices paid", "which supplier delivers on time").
best() ranks options by the lower bound of the Wilson interval on their success
rate, so three wins out of three does not outrank ninety out of a hundred.
This is counting and a confidence bound. No model is trained and nothing is
predicted beyond "this has worked more reliably so far".
State: <VELARIS_DATA>/agents/AUTO_LEARN_CORE/state.json.
"""
import math

from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "AUTO_LEARN_CORE"


def wilson_lower(successes, trials, z=1.96):
    """Lower bound of the Wilson score interval: a success rate that is not fooled by small samples."""
    if trials <= 0:
        return 0.0
    p = successes / trials
    centre = p + z * z / (2 * trials)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials)
    return max(0.0, (centre - spread) / (1 + z * z / trials))


class AUTO_LEARN_COREAgent:
    def __init__(self):
        self._state = JsonState(NAME, "state.json", {"contexts": {}})

    def health_check(self):
        return health(NAME)

    def record(self, context, option, success):
        context, option = ident(context), ident(option)
        if context is None or option is None or not isinstance(success, bool):
            return invalid("context and option must be names and success true or false")

        def change(data):
            tally = data["contexts"].setdefault(context, {}).setdefault(option, {"trials": 0, "successes": 0})
            tally["trials"] += 1
            tally["successes"] += int(success)
            return dict(tally)
        return ok(context=context, option=option, **self._state.update(change))

    def stats(self, context):
        tallies = self._state.load()["contexts"].get(context, {}) if isinstance(context, str) else {}
        return ok(context=context, options={
            o: {**t, "rate": round(t["successes"] / t["trials"], 4),
                "lower_bound": round(wilson_lower(t["successes"], t["trials"]), 4)}
            for o, t in sorted(tallies.items())})

    def best(self, context, options=None, min_trials=1):
        """Rank `options` (default: every option seen in the context).

        Order: highest lower bound, then fewest trials (so an untried option is
        tried before one that has only failed), then name. `choice` is None
        when no option has at least `min_trials` trials.
        """
        if ident(context) is None:
            return invalid("context must be a name", choice=None)
        if options is not None and not (isinstance(options, list) and all(ident(o) for o in options)):
            return invalid("options must be a list of names", choice=None)
        seen = self.stats(context)["options"]
        names = sorted(set(options)) if options is not None else sorted(seen)
        blank = {"trials": 0, "successes": 0, "rate": None, "lower_bound": 0.0}
        ranking = sorted(({"option": n, **seen.get(n, blank)} for n in names),
                         key=lambda r: (-r["lower_bound"], r["trials"], r["option"]))
        proven = [r for r in ranking if r["trials"] >= min_trials]
        untried = [r["option"] for r in ranking if r["trials"] == 0]
        if not proven:
            return fail("no_data", f"no option has {min_trials} recorded trial(s) in this context",
                        choice=None, ranking=ranking, untried=untried)
        return ok(choice=proven[0]["option"], ranking=ranking, untried=untried)
