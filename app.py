import shutil
from flask import Flask, request, render_template, abort, flash, redirect, url_for, jsonify
import instaloader
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
bootstrap = Bootstrap5(app)

# Configure download directory
DOWNLOAD_FOLDER = 'static/reels_thumbnails'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Instaloader instance
L = instaloader.Instaloader()
INSTAGRAM_ID = "divine.eyes.hindu"

# Configure Flask Login
login_manager = LoginManager()
login_manager.init_app(app)


# Database Configuration
class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
db.init_app(app)


# Users Table
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)


class Reels(db.Model):
    __tablename__ = "reels"
    id: Mapped[int] = mapped_column(primary_key=True)
    thumbnail: Mapped[str] = mapped_column(nullable=False)
    video_link: Mapped[str] = mapped_column(nullable=False)
    shortcode: Mapped[str] = mapped_column(nullable=False)
    view_count: Mapped[int] = mapped_column(nullable=False)
    likes: Mapped[int] = mapped_column(nullable=False)
    date: Mapped[str] = mapped_column(nullable=False)


# Initialize Database
with app.app_context():
    db.create_all()


# Admin Only Decorator
def admin_only(func):
    @wraps(func)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            abort(403)  # Forbidden for non-admin users
        return func(*args, **kwargs)

    return decorated_function


# User Loader
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


@app.route('/')
def home():
    return render_template("index.html")


def is_folder_empty(folder_path):
    # List all files and directories in the folder
    files = os.listdir(folder_path)

    # Check if any files exist (i.e., non-directory files)
    for file in files:
        if os.path.isfile(os.path.join(folder_path, file)):
            return True  # Folder contains files

    return False  # No files found, folder is empty or only contains directories


@app.route('/content')
def content_page():
    if is_folder_empty(DOWNLOAD_FOLDER):
        all_reels = db.session.execute(db.select(Reels)).scalars().all()
        return render_template("content.html", all_reels=all_reels)
    try:
        # Initialize Instaloader for downloading reels
        profile = instaloader.Profile.from_username(L.context, INSTAGRAM_ID)

        # Loop through reels of the profile
        for post in profile.get_posts():

            if post.is_video and post.typename == "GraphVideo":
                # Save the thumbnail of the reel
                thumbnail_path = os.path.join(DOWNLOAD_FOLDER, f"{post.shortcode}")
                L.download_pic(
                    filename=thumbnail_path,
                    url=post.url,
                    mtime=post.date_local
                )

                # reel_link = f"https://www.instagram.com/reel/{post.shortcode}/"

                # add reel data to database
                new_reel = Reels(
                    thumbnail=post.video_url,
                    video_link=post.url,
                    shortcode=post.shortcode,
                    view_count=post.video_view_count,
                    likes=post.likes,
                    date=post.date
                )

                db.session.add(new_reel)
                db.session.commit()

        all_reels = db.session.execute(db.select(Reels)).scalars().all()

        return render_template("content.html", all_reels=all_reels)

    except Exception as e:
        return f"Error: {str(e)}"


@app.route('/sign-up', methods=["GET", "POST"])
def sign_up():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # Validate inputs
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("sign_up"))

        if db.session.execute(db.select(User).where(User.email == email)).scalar():
            flash("Email already registered. Please log in.", "warning")
            return redirect(url_for("login"))

        # Hash password
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256", salt_length=8)

        # Create and save new user
        new_user = User(
            email=email,
            password=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("sign-up.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if not user or not check_password_hash(user.password, password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        login_user(user)
        # flash("Logged in successfully!", "success")

        return redirect(url_for("home"))

    return render_template("login.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    # flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


@app.route('/records')
@admin_only
def records():
    users = db.session.execute(db.select(User)).scalars().all()
    return render_template("records.html", users=users, users_exist=bool(users))


@app.route('/delete/<int:record_id>')
@admin_only
def delete(record_id):
    user_to_delete = db.get_or_404(User, record_id)
    if user_to_delete.id == 1:
        flash("Cannot delete the admin user.", "danger")
        return redirect(url_for("records"))
    db.session.delete(user_to_delete)
    db.session.commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for("records"))


@app.route("/update-database", methods=["GET", "POST"])
@admin_only
def update_database():
    if request.method == "POST":
        flash("Database is being updated. Please wait...", "info")
        # Delete all files in the download folder
        shutil.rmtree(DOWNLOAD_FOLDER, ignore_errors=True)
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
        return redirect(url_for("content_page"))
    return render_template("update-database.html")


if __name__ == '__main__':
    app.run(debug=True)
