from flask import Flask


def init_app(app: Flask):
    from .root import root_blueprint
    app.register_blueprint(root_blueprint)
