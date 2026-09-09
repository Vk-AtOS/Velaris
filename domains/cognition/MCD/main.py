# ================================================================================

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