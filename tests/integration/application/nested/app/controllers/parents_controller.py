from app.controllers.application_controller import ApplicationController
from app.models.parent import Parent

from flaskteroids.routes import parent_path


class ParentsController(ApplicationController):
    def edit(self):
        self.parent = Parent.find(self.params["id"])
        self.parent.children.new()

    def show(self):
        self.parent = Parent.find(self.params["id"])

    def update(self):
        self.parent = Parent.find(self.params["id"])
        attributes = self.params.expect(
            parent=[
                "name",
                ("children_attributes", [["id", "name", "quantity", "_destroy"]]),
            ]
        )
        if self.parent.update(**attributes):
            return self.redirect_to(parent_path(self.parent), status=303)
        return self.render("edit", status=422)
