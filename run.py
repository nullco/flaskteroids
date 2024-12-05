from flask.app import Flask
from flaskteroids.route import root

app = Flask(__name__, template_folder='app/views/')

with app.app_context():
    root(to='articles#index')

app.run(debug=True)
