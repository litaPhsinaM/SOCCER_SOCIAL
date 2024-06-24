from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email
import requests
from datetime import datetime, timedelta
import pytz
from dateutil import parser
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///predictions.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Load API keys from environment variables
API_FOOTBALL_HOST = "api-football-v1.p.rapidapi.com"
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    club = db.Column(db.String(100), nullable=False)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    match_id = db.Column(db.Integer, nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    user = db.relationship('User', backref=db.backref('predictions', lazy=True))

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.String(1000), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class LoginForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    club = StringField('Club', validators=[DataRequired()])
    submit = SubmitField('Login')

class ChatForm(FlaskForm):
    content = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send')

with app.app_context():
    db.create_all()

def fetch_completed_matches():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    querystring = {"league":"39","season":"2023","status":"FT"}
    headers = {
        "X-RapidAPI-Key": API_FOOTBALL_KEY,
        "X-RapidAPI-Host": API_FOOTBALL_HOST
    }
    response = requests.get(url, headers=headers, params=querystring)
    data = response.json()
    if 'response' in data:
        for match in data['response']:
            match['fixture']['formatted_date'] = format_date(match['fixture']['date'])
        return data['response']
    else:
        print("Error fetching completed matches:", data)
        return []

def fetch_upcoming_matches():
    today = datetime.utcnow().date()
    end_date = today + timedelta(days=10)
    url = f"https://api.football-data.org/v2/matches"
    headers = {
        "X-Auth-Token": FOOTBALL_DATA_API_KEY
    }
    params = {
        "dateFrom": today.strftime("%Y-%m-%d"),
        "dateTo": end_date.strftime("%Y-%m-%d")
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    if 'matches' in data:
        for match in data['matches']:
            match['formatted_date'] = format_date(match['utcDate'])
        return data['matches']
    else:
        print("Error fetching upcoming matches:", data)
        return []

def format_date(date_str):
    utc_dt = parser.parse(date_str)
    local_tz = pytz.timezone('US/Pacific')
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt.strftime("%m/%d/%Y %I:%M %p")

@app.route("/", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        session.clear()  # Clear the session before login
        name = form.name.data
        email = form.email.data
        club = form.club.data
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=name, email=email, club=club)
            db.session.add(user)
            db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for("index"))
    return render_template("login.html", form=form)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/index", methods=["GET", "POST"])
def index():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        session.clear()
        return redirect(url_for('login'))

    completed_matches = fetch_completed_matches()
    upcoming_matches = fetch_upcoming_matches()
    form = ChatForm()
    messages = ChatMessage.query.all()
    predictions = Prediction.query.all()

    if form.validate_on_submit():
        message = ChatMessage(user_name=user.name, content=form.content.data)
        db.session.add(message)
        db.session.commit()
        return jsonify(success=True)

    return render_template("index.html", completed_matches=completed_matches, upcoming_matches=upcoming_matches, user=user, form=form, messages=messages, predictions=predictions)

@app.route("/predict", methods=["POST"])
def predict():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify(success=False, message="User not logged in.")
    user = User.query.get(user_id)
    match_id = request.form.get('match_id')
    team_name = request.form.get('team_name')
    user_name = user.name
    prediction = Prediction(user_id=user_id, match_id=match_id, team_name=team_name, user_name=user_name)
    db.session.add(prediction)
    db.session.commit()
    return jsonify(success=True, user_name=user_name, team_name=team_name)

@app.route("/messenger", methods=["POST"])
def messenger():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify(success=False, message="User not logged in.")
    user = User.query.get(user_id)
    content = request.form.get('content')
    if user and content:
        message = ChatMessage(user_name=user.name, content=content)
        db.session.add(message)
        db.session.commit()
        return jsonify(success=True, user_name=user.name, content=content, timestamp=message.timestamp.strftime('%m/%d/%Y %I:%M %p'))
    return jsonify(success=False)

if __name__ == "__main__":
    app.run(debug=True)
