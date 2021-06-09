from flask import Blueprint

# Declare the blueprint with whatever name you want to give it
root_blueprint = Blueprint('root', __name__)


# This is how you register a controller, it accepts OPTIONS and GET methods by default
@root_blueprint.route('/health/')
def health():
    return {'message': 'Healthy'}  # This will return as JSON by default with a 200 status code
