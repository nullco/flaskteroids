from flask import request
from werkzeug.datastructures import FileStorage

from flaskteroids import params
from flaskteroids.controller import ActionController


def describe(value):
    if isinstance(value, FileStorage):
        return {"filename": value.filename, "content": value.read().decode()}
    if isinstance(value, dict):
        return {key: describe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [describe(item) for item in value]
    return value


def response(action):
    return {
        "action": action,
        "method": request.method,
        "params": describe(dict(params)),
    }


class ProbesController(ActionController):
    def index(self):
        return response("index")

    def new(self):
        return response("new")

    def create(self):
        return response("create")

    def show(self):
        return response("show")

    def edit(self):
        return response("edit")

    def update(self):
        return response("update")

    def destroy(self):
        return response("destroy")


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
