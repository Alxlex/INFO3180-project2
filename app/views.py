"""
Flask Documentation:     https://flask.palletsprojects.com/
Jinja2 Documentation:    https://jinja.palletsprojects.com/
Werkzeug Documentation:  https://werkzeug.palletsprojects.com/
This file creates your application.
"""

from app import app, db
from flask import render_template, request, jsonify, send_file, session, send_from_directory
import os
from werkzeug.security import check_password_hash
from app.models import Post, Likes, Follows, UserProfile
from app.forms import RegisterForm, LoginForm, PostForm
from flask_wtf.csrf import generate_csrf
from werkzeug.utils import secure_filename
import datetime
import jwt

###
# Routing for your application.
###

@app.route('/')
def index():
    return jsonify(message="Share photos of your favourite moments with friends, family and the world.")

@app.route('/api/v1/csrf-token', methods=['GET'])
def get_csrf():
    return jsonify({'csrf_token': generate_csrf()})

# API ROUTES

@app.route('/api/v1/register', methods=['POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Gather data from the form
        username = form.username.data
        password = form.password.data
        firstname = form.firstname.data
        lastname = form.lastname.data
        email = form.email.data
        
        errors = []
        existing_email = db.session.execute(db.select(UserProfile).filter_by(email=email)).scalar()
        if existing_email:
            errors.append("Email already exists")

        existing_username = db.session.execute(db.select(UserProfile).filter_by(username=username)).scalar()
        if existing_username:
            errors.append("Username already exists")
        
        if errors != []:
            return jsonify({"errors":errors}), 400

        location = form.location.data
        biography = form.biography.data
        profile_photo = form.profile_photo.data
        filename = secure_filename(profile_photo.filename)

        profile_photo.save(
            os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename)
        )

        joined_on = datetime.datetime.now()

        user = UserProfile(
            username,
            password,
            firstname,
            lastname,
            email,
            location,
            biography,
            filename,
            joined_on
        )

        db.session.add(user)
        db.session.commit()

        return jsonify({"message":"Successfully created account"}), 201
    else:
        return jsonify({"errors":form_errors(form)}), 400

@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = db.session.execute(db.select(UserProfile).filter_by(username=username)).scalar()
        print(user)
        if not user or not check_password_hash(user.password, password):
            return jsonify({'errors':'Invalid username or password'}), 401
        token = jwt.encode({'user_id':user.id}, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({'token':token})
    else:
        return jsonify({"errors": form_errors(form)}), 400

@app.route('/api/v1/auth/logout', methods=['POST'])
def logout():
    return jsonify({'message':'Logged out successfully'})

@app.route('/api/v1/users/<user_id>/posts', methods=['GET', 'POST'])
def user_posts(user_id):
    form = PostForm()
    if request.method == 'GET':
        posts = db.session.execute(db.select(Post).filter_by(user_id)).scalars()
        return jsonify({"posts":[post.__dict__ for post in posts]})
    elif form.validate_on_submit():
        caption = form.caption.data
        photo = form.photo.data
        filename = secure_filename(photo.filename)

        photo.save(
            os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename)
        )

        post = Post(caption=caption, 
                    photo=filename, 
                    user_id=user_id, 
                    created_on=datetime.datetime.now())
        db.session.add(post)
        db.session.commit()

        return jsonify({'message': 'Post created successfully'}), 201
    else:
        return jsonify({"errors": form_errors(form)}), 400

@app.route('/api/users/<user_id>/follow', methods=['POST'])
def follow_user(user_id):
    form = PostForm()
    if form.validate_on_submit() and request.method == "POST":
        follower_id = form.user_id.data
    
    follow = Follow.query.filter_by(follower_id=follower_id, user_id=user_id).first()
    if not follow:
        follow = Follow(follower_id=follower_id, user_id=user_id)
        db.session.add(follow)
        db.session.commit()
        return jsonify({'message': 'User followed successfully'})
    else:
        db.session.delete(follow)
        db.session.commit()
        return jsonify({'message': 'User unfollowed successfully'})

@app.route('/api/v1/posts', methods=['GET'])
def get_all_post():
    posts = db.session.execute(db.select(Post)).scalars()
    if not posts:
        return jsonify({"error":"There are no posts to view"}), 200
    else:
        posts = [{
            "username":str(db.session.execute(db.select(UserProfile.username).filter_by(id=post.user_id)).scalar()),
            "profilePhoto":"/api/v1/users/"+str(db.session.execute(db.select(UserProfile.id).filter_by(id=post.user_id)).scalar())+"/"+str(post.id),
            "caption":post.caption, 
            "photo":"/api/v1/posts/"+post.photo, 
            "user_id":post.user_id, 
            "likes":len(db.session.execute(db.select(Likes.post_id).filter_by(post_id=post.id)).all()),
            "created_on":post.created_on.strftime("%d %b %Y")} for post in posts]
        return jsonify({"posts": posts}), 200

@app.route('/api/v1/posts/<post_id>/like', methods=['POST'])
def likepost(post_id):
    form = PostForm()
    if form.validate_on_submit() and request.method == "POST":
        user_id = form.user_id.data
    
    like = Like.query.filter_by(post_id=post_id, user_id=user_id).first()
    if not like:
        like = Like(post_id=post_id, user_id=user_id)
        db.session.add(like)
        db.session.commit()
        return jsonify({'message': 'Post liked successfully'})
    else:
        db.session.delete(like)
        db.session.commit()
        return jsonify({'message': 'Post unlike successfully'})

@app.route('/api/v1/posts/<filename>') #MAY BE USED TO FIND PICTURES, CHANGE TO FIT CURRENT CODE
def getPostImage(filename):
    return send_from_directory(os.path.join(os.getcwd(),app.config['UPLOAD_FOLDER']),filename)

@app.route('/api/v1/users/<user_id>/<post_id>') #MAY BE USED TO FIND PICTURES, CHANGE TO FIT CURRENT CODE
def getProfilePhoto(user_id, post_id):
    filename = db.session.execute(db.select(UserProfile.profile_photo).filter_by(id=user_id)).scalar()
    return send_from_directory(os.path.join(os.getcwd(),app.config['UPLOAD_FOLDER']),filename)

###
# The functions below should be applicable to all Flask apps.
###

# Here we define a function to collect form errors from Flask-WTF
# which we can later use
def form_errors(form):
    error_messages = []
    """Collects form errors"""
    for field, errors in form.errors.items():
        for error in errors:
            message = u"Error in the %s field - %s" % (
                    getattr(form, field).label.text,
                    error
                )
            error_messages.append(message)

    return error_messages

@app.route('/<file_name>.txt')
def send_text_file(file_name):
    """Send your static text file."""
    file_dot_text = file_name + '.txt'
    return app.send_static_file(file_dot_text)

@app.after_request
def add_header(response):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also tell the browser not to cache the rendered page. If we wanted
    to we could change max-age to 600 seconds which would be 10 minutes.
    """
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response

@app.errorhandler(404)
def page_not_found(error):
    """Custom 404 page."""
    return render_template('404.html'), 404