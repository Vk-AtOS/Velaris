# ================================================================================

"""Master Control Dashboard: a static route table and HTML shell stub.

MasterControlDashboard holds three fixed routes ("/", "/status", "/agents") mapped to the
names "dashboard", "system_status" and "agent_list", an HTML template string and a JS
boot string. render(content) substitutes content into the template, route_exists(path)
tells whether a path is in the table, and get_route_target(path) returns its name or None.
It serves nothing itself and does not call other agents.
State: keeps no state beyond those constants.
Failure: an unknown path gives False / None; render() with a non-string raises TypeError.
"""

class MasterControlDashboard:
    def __init__(self):
        self.routes = {
            "/": "dashboard",
            "/status": "system_status",
            "/agents": "agent_list"
        }
        self.html_template = "<html><body>{{content}}</body></html>"
        self.js_boot = "console.log('MCD Loaded');"

    def render(self, content):
        return self.html_template.replace("{{content}}", content)

    def route_exists(self, path):
        return path in self.routes

    def get_route_target(self, path):
        return self.routes.get(path)

# ================================================================================