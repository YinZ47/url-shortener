import os
import string
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import stripe
import re
from urllib.parse import urlparse
from models import db, User, Url, Click
from auth import login_required, get_current_user
from utils import generate_short_code, is_valid_url, get_client_ip

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///urlshortener.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Initialize Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_placeholder')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_test_placeholder')
STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID', 'price_placeholder')

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Create tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    user = get_current_user()
    return render_template('index.html', user=user)

@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        
        # Validation
        if not email or not password:
            flash('Email and password are required', 'danger')
            return redirect(url_for('signup'))
        
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('Invalid email format', 'danger')
            return redirect(url_for('signup'))
        
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'danger')
            return redirect(url_for('signup'))
        
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(
            email=email,
            password=hashed_password,
            created_at=datetime.utcnow(),
            monthly_quota=5,
            used_quota=0,
            quota_reset_date=datetime.utcnow() + timedelta(days=30)
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        flash('Account created successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    
    # Reset quota if needed
    if datetime.utcnow() > user.quota_reset_date:
        user.used_quota = 0
        user.quota_reset_date = datetime.utcnow() + timedelta(days=30)
        db.session.commit()
    
    # Get user's URLs
    urls = Url.query.filter_by(user_id=user.id).order_by(Url.created_at.desc()).all()
    
    # Prepare analytics data
    for url in urls:
        url.total_clicks = Click.query.filter_by(url_id=url.id).count()
        url.unique_clicks = db.session.query(Click.ip_address).filter_by(url_id=url.id).distinct().count()
    
    return render_template('dashboard.html', 
                         user=user, 
                         urls=urls,
                         stripe_key=STRIPE_PUBLISHABLE_KEY)

@app.route('/shorten', methods=['POST'])
@login_required
def shorten_url():
    user = get_current_user()
    original_url = request.form.get('url', '').strip()
    
    # Validate URL
    if not is_valid_url(original_url):
        flash('Invalid URL format', 'danger')
        return redirect(request.referrer or url_for('index'))
    
    # Check quota for free users
    if not user.is_premium and user.used_quota >= user.monthly_quota:
        flash('Monthly quota exceeded. Upgrade to premium for unlimited links!', 'warning')
        return redirect(url_for('pricing'))
    
    # Generate short code
    short_code = generate_short_code()
    while Url.query.filter_by(short_code=short_code).first():
        short_code = generate_short_code()
    
    # Create new URL
    new_url = Url(
        original_url=original_url,
        short_code=short_code,
        user_id=user.id,
        created_at=datetime.utcnow()
    )
    
    # Update quota for free users
    if not user.is_premium:
        user.used_quota += 1
    
    db.session.add(new_url)
    db.session.commit()
    
    flash('URL shortened successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/<short_code>')
def redirect_url(short_code):
    url = Url.query.filter_by(short_code=short_code).first()
    
    if not url:
        abort(404)
    
    # Track click
    click = Click(
        url_id=url.id,
        ip_address=get_client_ip(),
        clicked_at=datetime.utcnow(),
        user_agent=request.headers.get('User-Agent', '')[:500],
        referrer=request.referrer[:500] if request.referrer else None
    )
    
    db.session.add(click)
    db.session.commit()
    
    return redirect(url.original_url)

@app.route('/api/analytics/<int:url_id>')
@login_required
def get_analytics(url_id):
    user = get_current_user()
    url = Url.query.filter_by(id=url_id, user_id=user.id).first()
    
    if not url:
        return jsonify({'error': 'URL not found'}), 404
    
    # Get click data for the last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    clicks = Click.query.filter(
        Click.url_id == url_id,
        Click.clicked_at >= seven_days_ago
    ).all()
    
    # Group clicks by day
    click_data = {}
    for click in clicks:
        date = click.clicked_at.strftime('%Y-%m-%d')
        if date not in click_data:
            click_data[date] = 0
        click_data[date] += 1
    
    # Fill in missing days with 0
    dates = []
    counts = []
    for i in range(7):
        date = (datetime.utcnow() - timedelta(days=6-i)).strftime('%Y-%m-%d')
        dates.append(date)
        counts.append(click_data.get(date, 0))
    
    return jsonify({
        'dates': dates,
        'counts': counts,
        'total_clicks': len(clicks),
        'unique_clicks': len(set(click.ip_address for click in clicks))
    })

@app.route('/pricing')
def pricing():
    user = get_current_user()
    return render_template('pricing.html', user=user, stripe_key=STRIPE_PUBLISHABLE_KEY)

@app.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    user = get_current_user()
    
    try:
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
            customer_email=user.email,
            success_url=url_for('subscription_success', _external=True),
            cancel_url=url_for('pricing', _external=True),
            metadata={'user_id': user.id}
        )
        
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        flash('Error creating subscription. Please try again.', 'danger')
        return redirect(url_for('pricing'))

@app.route('/subscription-success')
@login_required
def subscription_success():
    user = get_current_user()
    user.is_premium = True
    user.subscription_date = datetime.utcnow()
    db.session.commit()
    
    flash('Premium subscription activated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete-url/<int:url_id>', methods=['POST'])
@login_required
def delete_url(url_id):
    user = get_current_user()
    url = Url.query.filter_by(id=url_id, user_id=user.id).first()
    
    if url:
        # Delete related clicks first
        Click.query.filter_by(url_id=url.id).delete()
        db.session.delete(url)
        db.session.commit()
        flash('URL deleted successfully!', 'success')
    else:
        flash('URL not found', 'danger')
    
    return redirect(url_for('dashboard'))

@app.errorhandler(404)
def not_found(e):
    return render_template('base.html'), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    flash('Too many requests. Please try again later.', 'warning')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)