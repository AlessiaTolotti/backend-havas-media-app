import os
import pandas as pd
from flask import Flask, request, session, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv('FLASK_SECRET_KEY')

users = {
    'admin': os.getenv('ADMIN_PASSWORD'),
    'federica': os.getenv('FEDERICA_PASSWORD'),
    'margherita': os.getenv('MARGHERITA_PASSWORD'),
    'lorenzo': os.getenv('LORENZO_PASSWORD')
}

@app.route('/api/login', methods=['POST'])
def login():
    user = request.form.get('username')
    pwd = request.form.get('password')

    if not user or not pwd:
        return jsonify({"success": False, "error": "Username e password richiesti"}), 400

    if user in users and users[user] == pwd:
        session['username'] = user
        return jsonify({"success": True})

    return jsonify({"success": False, "error": "Credenziali errate!"}), 401


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
