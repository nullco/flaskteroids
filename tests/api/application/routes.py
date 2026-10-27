def register(route):
    route.resources("probes")
    route.resources("wrappeds", only=["create"])
    route.resources("custom_wrappeds", only=["create"])
    for name in (
        "inherited_wrappeds",
        "disabled_wrappeds",
        "restored_wrappeds",
        "mixin_wrappeds",
        "overridden_wrappeds",
        "browser_wrappeds",
    ):
        route.resources(name, only=["create"])
    route.resource("account")
    route.resources(
        "parents",
        nested=lambda parent: parent.resources("children"),
    )
    route.get("/empty", to="probes#empty")
    route.get("/failure", to="probes#failure")
    route.get("/conditional", to="probes#conditional")
    route.get("/limited", to="probes#limited")
    route.get("/download", to="probes#download")
    route.post("/cookie", to="probes#cookie")
    route.get("/browser", to="browser#show")
    route.post("/browser", to="browser#create")
