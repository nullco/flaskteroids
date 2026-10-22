from flask import request
from werkzeug.datastructures import FileStorage

from flaskteroids.controller import ActionController


def describe(value):
    if isinstance(value, FileStorage):
        return {"filename": value.filename, "content": value.read().decode()}
    if isinstance(value, dict):
        return {key: describe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [describe(item) for item in value]
    return value


def response(action, parameters):
    return {
        "action": action,
        "method": request.method,
        "params": describe(dict(parameters)),
    }


class ProbesController(ActionController):
    def index(self):
        return response("index", self.params)

    def new(self):
        return response("new", self.params)

    def create(self):
        return response("create", self.params)

    def show(self):
        return response("show", self.params)

    def edit(self):
        return response("edit", self.params)

    def update(self):
        return response("update", self.params)

    def destroy(self):
        return response("destroy", self.params)


class ProductsController(ProbesController):
    pass


class SubscribersController(ProbesController):
    pass


class ShopsController(ProbesController):
    pass


class CategoriesController(ProbesController):
    pass


class FishController(ProbesController):
    pass


class EquipmentController(ProbesController):
    pass
