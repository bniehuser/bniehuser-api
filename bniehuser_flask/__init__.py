__version__ = '0.1.0'
from flask import Flask


def create_app():
    return Flask(__name__)

