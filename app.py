import os
import secrets
from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from models import db, User, Post, Like, Comment
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs('uploads/posts', exist_ok=True)
os.makedirs('uploads/avatars', exist_ok=True)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_image(file, folder):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{int(datetime.now().timestamp())}{ext}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        file.save(filepath)
        
        try:
            img = Image.open(filepath)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail((1200, 1200))
            img.save(filepath, optimize=True, quality=85)
        except Exception as e:
            print(f"Error optimizing image: {e}")
        
        return filename
    return None

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/uploads/<folder>/<filename>')
def uploaded_file(folder, filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], folder, filename))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('feed'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            db.session.commit()
            
            reset_url = url_for('reset_password', token=token, _external=True)
            flash(f'Reset link: {reset_url}')
            return redirect(url_for('login'))
        else:
            flash('Email not found')
    
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    
    user = User.query.filter_by(reset_token=token).first()
    
    if not user:
        flash('Invalid or expired reset token')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('reset_password.html', token=token)
        
        user.set_password(password)
        user.reset_token = None
        db.session.commit()
        
        flash('Password reset successfully! Please login with your new password.')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/feed')
@login_required
def feed():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('feed.html', posts=posts)

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        content = request.form['content']
        image_file = request.files.get('image')
        
        if not content.strip() and not image_file:
            flash('Post cannot be empty! Add text or image.')
            return redirect(url_for('create_post'))
        
        image_filename = None
        if image_file:
            image_filename = save_image(image_file, 'posts')
            if not image_filename:
                flash('Invalid image format! Allowed: PNG, JPG, JPEG, GIF, WEBP')
                return redirect(url_for('create_post'))
        
        post = Post(content=content, image=image_filename, author=current_user)
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully!')
        return redirect(url_for('feed'))
    
    return render_template('create_post.html')

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        flash('No file selected')
        return redirect(url_for('profile', username=current_user.username))
    
    avatar_file = request.files['avatar']
    if avatar_file.filename == '':
        flash('No file selected')
        return redirect(url_for('profile', username=current_user.username))
    
    if avatar_file and allowed_file(avatar_file.filename):
        if current_user.avatar:
            old_avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', current_user.avatar)
            if os.path.exists(old_avatar_path):
                os.remove(old_avatar_path)
        
        avatar_filename = save_image(avatar_file, 'avatars')
        if avatar_filename:
            current_user.avatar = avatar_filename
            db.session.commit()
            flash('Avatar updated successfully!')
        else:
            flash('Invalid image format!')
    else:
        flash('Invalid file format! Allowed: PNG, JPG, JPEG, GIF, WEBP')
    
    return redirect(url_for('profile', username=current_user.username))

@app.route('/like/<int:post_id>')
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if like:
        db.session.delete(like)
        flash('Post unliked!')
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        flash('Post liked!')
    
    db.session.commit()
    return redirect(url_for('feed'))

@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
    return render_template('profile.html', user=user, posts=posts)

@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form['content']
    if content.strip():
        comment = Comment(content=content, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()
        flash('Comment added!')
    else:
        flash('Comment cannot be empty!')
    
    return redirect(url_for('feed'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
