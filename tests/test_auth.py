import pytest
from app import app, db
from models import User
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

def test_signup_success(client):
    """Test successful user signup"""
    response = client.post('/signup', data={
        'email': 'test@example.com',
        'password': 'testpassword123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        assert user is not None
        assert user.monthly_quota == 5

def test_signup_duplicate_email(client):
    """Test signup with existing email"""
    # Create first user
    with app.app_context():
        user = User(
            email='test@example.com',
            password=generate_password_hash('password123')
        )
        db.session.add(user)
        db.session.commit()
    
    # Try to create duplicate
    response = client.post('/signup', data={
        'email': 'test@example.com',
        'password': 'anotherpassword'
    }, follow_redirects=True)
    
    assert b'Email already registered' in response.data

def test_login_success(client):
    """Test successful login"""
    # Create user
    with app.app_context():
        user = User(
            email='test@example.com',
            password=generate_password_hash('password123')
        )
        db.session.add(user)
        db.session.commit()
    
    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Logged in successfully' in response.data

def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post('/login', data={
        'email': 'wrong@example.com',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    
    assert b'Invalid email or password' in response.data

def test_logout(client):
    """Test logout functionality"""
    # Create and login user
    with app.app_context():
        user = User(
            email='test@example.com',
            password=generate_password_hash('password123')
        )
        db.session.add(user)
        db.session.commit()
    
    client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password123'
    })
    
    response = client.get('/logout', follow_redirects=True)
    assert b'Logged out successfully' in response.data

def test_password_validation(client):
    """Test password length validation"""
    response = client.post('/signup', data={
        'email': 'test@example.com',
        'password': 'short'
    }, follow_redirects=True)
    
    assert b'Password must be at least 8 characters' in response.data 