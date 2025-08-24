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

# ✅ Настройки для загрузки файлов
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Создаем папки для загрузок
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
        # Добавляем timestamp к имени файла
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{int(datetime.now().timestamp())}{ext}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        file.save(filepath)
        
        # Оптимизируем изображение
        try:
            img = Image.open(filepath)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail((1200, 1200))  # Максимальный размер
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

# ... остальные маршруты без изменений до create_post ...

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
        # Удаляем старый аватар если есть
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

# ... остальные маршруты без изменений ...

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
