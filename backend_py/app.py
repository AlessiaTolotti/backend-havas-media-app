import os
import time
import pandas as pd
from flask import Flask, request, render_template, url_for, send_from_directory, redirect
from rapidfuzz import process, fuzz
import re
from flask import session
import secrets
from dotenv import load_dotenv
from unidecode import unidecode
from flask import jsonify
from flask_cors import CORS

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
    error = None  # inizializzo la variabile error
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if user in users and users[user] == pwd:
            session['username'] = user
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Credenziali errate!"}), 401


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
