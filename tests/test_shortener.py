import pytest
from app import app, db
from models import User, Url, Click
from utils import generate_short_code, is_valid_url
from datetime import datetime

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            # Create test user
            user = User(
                id=1,
                email='test@example.com',
                password='hashed_password',
                monthly_quota=5,
                used_quota=0
            )
            db.session.add(user)
            db.session.commit()
        yield client

def test_generate_short_code():
    """Test short code generation"""
    code = generate_short_code()
    assert len(code) == 6
    assert code.isalnum()
    
    # Test uniqueness
    codes = [generate_short_code() for _ in range(100)]
    assert len(codes) == len(set(codes))

def test_url_validation():
    """Test URL validation function"""
    valid_urls = [
        'http://example.com',
        'https://example.com',
        'https://subdomain.example.com/path',
        'http://example.com:8080/path?query=value'
    ]
    
    invalid_urls = [
        'not-a-url',
        'ftp://example.com',
        'example.com',
        '',
        'javascript:alert(1)'
    ]
    
    for url in valid_urls:
        assert is_valid_url(url) == True
    
    for url in invalid_urls:
        assert is_valid_url(url) == False

def test_shorten_url(client):
    """Test URL shortening"""
    # Login first
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    
    response = client.post('/shorten', data={
        'url': 'https://example.com'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    with app.app_context():
        url = Url.query.filter_by(original_url='https://example.com').first()
        assert url is not None
        assert len(url.short_code) == 6

def test_quota_enforcement(client):
    """Test free user quota limits"""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    
    # Update user quota
    with app.app_context():
        user = User.query.get(1)
        user.used_quota = 5  # Max quota reached
        db.session.commit()
    
    response = client.post('/shorten', data={
        'url': 'https://example.com'
    }, follow_redirects=True)
    
    assert b'Monthly quota exceeded' in response.data

def test_url_redirect(client):
    """Test URL redirect functionality"""
    # Create a shortened URL
    with app.app_context():
        url = Url(
            original_url='https://example.com',
            short_code='abc123',
            user_id=1,
            created_at=datetime.utcnow()
        )
        db.session.add(url)
        db.session.commit()
    
    response = client.get('/abc123')
    assert response.status_code == 302
    assert response.location == 'https://example.com'

def test_click_tracking(client):
    """Test click tracking"""
    with app.app_context():
        url = Url(
            id=1,
            original_url='https://example.com',
            short_code='abc123',
            user_id=1,
            created_at=datetime.utcnow()
        )
        db.session.add(url)
        db.session.commit()
    
    # Visit the short URL
    client.get('/abc123')
    
    with app.app_context():
        clicks = Click.query.filter_by(url_id=1).all()
        assert len(clicks) == 1
        assert clicks[0].ip_address is not None

def test_delete_url(client):
    """Test URL deletion"""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    
    with app.app_context():
        url = Url(
            id=1,
            original_url='https://example.com',
            short_code='abc123',
            user_id=1,
            created_at=datetime.utcnow()
        )
        db.session.add(url)
        db.session.commit()
    
    response = client.post('/delete-url/1', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        url = Url.query.get(1)
        assert url is None