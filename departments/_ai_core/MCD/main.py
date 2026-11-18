# ================================================================================

"""MCD (Master Control Dashboard): a fixed route table and a one-line HTML page template.

render(content) returns the template with the content inserted as escaped text (HTML in it is never interpreted).
route_exists(path) and get_route_target(path) look up the three built-in routes ("/", "/status", "/agents"); an unknown
path gives False and None. health_check() returns {"agent", "status": "ok", "routes": n}. It serves nothing itself: there
is no HTTP server and no authentication here.
State: none beyond the in-memory route dict. Nothing is raised on bad input.
"""
import html


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
        """The page with `content` as TEXT: HTML in it is escaped, never interpreted."""
        return self.html_template.replace("{{content}}", html.escape(str(content)))

    def health_check(self):
        return {"agent": "MCD", "status": "ok", "routes": len(self.routes)}

    def route_exists(self, path):
        return path in self.routes

    def get_route_target(self, path):
        return self.routes.get(path)

# ================================================================================