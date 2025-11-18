from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_premium = db.Column(db.Boolean, default=False)
    subscription_date = db.Column(db.DateTime, nullable=True)
    monthly_quota = db.Column(db.Integer, default=5)
    used_quota = db.Column(db.Integer, default=0)
    quota_reset_date = db.Column(db.DateTime, nullable=True)
    
    urls = db.relationship('Url', backref='user', lazy=True, cascade='all, delete-orphan')

class Url(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.Text, nullable=False)
    short_code = db.Column(db.String(10), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    clicks = db.relationship('Click', backref='url', lazy=True, cascade='all, delete-orphan')

class Click(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('url.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_agent = db.Column(db.String(500), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)