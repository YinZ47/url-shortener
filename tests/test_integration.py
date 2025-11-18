import pytest
from app import app, db
from models import User, Url, Click
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

def test_full_user_flow(client):
    """Test complete user journey from signup to URL management"""
    
    # 1. Sign up
    response = client.post('/signup', data={
        'email': 'user@example.com',
        'password': 'securepassword123'
    }, follow_redirects=True)
    assert response.status_code == 200
    
    # 2. Create a short URL
    response = client.post('/shorten', data={
        'url': 'https://www.google.com'
    }, follow_redirects=True)
    assert response.status_code == 200
    
    # 3. Check dashboard
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b'https://www.google.com' in response.data
    
    # 4. Get the short code
    with app.app_context():
        url = Url.query.filter_by(original_url='https://www.google.com').first()
        short_code = url.short_code
    
    # 5. Visit the short URL
    response = client.get(f'/{short_code}')
    assert response.status_code == 302
    
    # 6. Check analytics
    response = client.get(f'/api/analytics/1')
    assert response.status_code == 200
    
    # 7. Delete the URL
    response = client.post('/delete-url/1', follow_redirects=True)
    assert response.status_code == 200
    
    # 8. Logout
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200

def test_premium_subscription_flow(client):
    """Test premium subscription flow"""
    
    # Create and login user
    with app.app_context():
        user = User(
            email='premium@example.com',
            password=generate_password_hash('password123'),
            monthly_quota=5,
            used_quota=0
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    
    # Check pricing page
    response = client.get('/pricing')
    assert response.status_code == 200
    assert b'$4.99' in response.data
    
    # Simulate successful subscription
    response = client.get('/subscription-success', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        user = User.query.get(user_id)
        assert user.is_premium == True

def test_rate_limiting(client):
    """Test rate limiting on login endpoint"""
    # Make multiple login attempts
    for i in range(12):  # Exceed the 10 per hour limit
        response = client.post('/login', data={
            'email': f'test{i}@example.com',
            'password': 'wrongpassword'
        })
    
    # The 11th attempt should be rate limited
    assert response.status_code == 429 or b'Too many requests' in response.data

def test_invalid_short_code(client):
    """Test accessing non-existent short URL"""
    response = client.get('/nonexistent')
    assert response.status_code == 404

def test_analytics_authorization(client):
    """Test that analytics requires authentication"""
    response = client.get('/api/analytics/1')
    assert response.status_code == 302  # Redirect to login
    
    # Create user and URL
    with app.app_context():
        user = User(
            id=1,
            email='owner@example.com',
            password='hashed'
        )
        url = Url(
            id=1,
            original_url='https://example.com',
            short_code='test123',
            user_id=1
        )
        db.session.add(user)
        db.session.add(url)
        db.session.commit()
    
    # Login as different user
    with client.session_transaction() as sess:
        sess['user_id'] = 2  # Different user ID
    
    # Try to access analytics of another user's URL
    response = client.get('/api/analytics/1')
    assert response.status_code == 404