from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, UserForm, LoginForm, CommentForm
from sqlalchemy.ext.declarative import declarative_base
from flask_gravatar import Gravatar
import os
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv('.env')
# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")

ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("://", "ql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
Base = declarative_base()

##INITIATE LOGIN_MANAGER
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

TODAY_DATE = date.today().strftime("%B %d, %Y")
print('hello')

gravatar = Gravatar(app,
                    size=90,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONFIGURE TABLES
class User(UserMixin, db.Model, Base):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

    #back_populates is bidirectional. need to reference it in reverse below
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")

class BlogPost(db.Model, Base):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    #cannot have author as we are using author_id below to link to foreignkey
    # author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    #create foreign key
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    #back populates indicates bidirectional. need to reference it in reverse below.
    #Relationships don't show up as columns in db
    author = relationship("User", back_populates="posts")
    #blogpost is parent relationship to comment
    comments = relationship("Comment", back_populates="parent_post")

class Comment(db.Model, Base):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    comment_body = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    comment_date = db.Column(db.String(250), nullable=False)

    comment_author = relationship("User", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="comments")

with app.app_context():
    db.create_all()

def admin_only(func):
    # check whether current user is admin
    def wrapper_func(*args, **kwargs):
        if current_user.id == 1:
            return func(*args, **kwargs)
        else:
            print("abort-inside")
            abort(403)
    # so that this decorator can be applied to more than one function
    wrapper_func.__name__ = func.__name__
    return wrapper_func

##ROUTING
@app.route('/')
def get_all_posts():
    print(current_user)
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=['GET','POST'])
def register():
    user_form = UserForm()

    if user_form.validate_on_submit():
        #syntax to get form data from wtfforms vs htmlforms is different
        name = user_form.name.data
        email = user_form.email.data
        user = User.query.filter_by(
            email=email).first()  # if this returns a user, then the email already exists in database

        if user:  # if a user is found, we want to redirect back to signup page so user can try again
            flash('Email address already exists. Login instead!')
            return redirect(url_for('register'))

        password = user_form.password.data
        hashed_pw = generate_password_hash(password=password, salt_length=8)
        new_user = User(name=name, password=hashed_pw, email=email)
        db.session.add(new_user)
        db.session.commit()
        print("added user to db")
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=user_form)


@app.route('/login', methods=['GET','POST'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        email = login_form.email.data
        password = login_form.password.data
        print(email)
        # user_obj = User.query.get(email) .get only works for primary key
        user_obj = User.query.filter_by(email=email).first()
        # print(user_obj)
        if user_obj and check_password_hash(pwhash=user_obj.password, password=password):
            user_id = user_obj.get_id()
            login_user(user_obj)
            return redirect(url_for('get_all_posts'))
        elif not user_obj:
            flash('Unsuccessful Login. Email does not exist.')
        else:
            flash('Unsuccessful Login. Invalid login combination.')
    return render_template("login.html", form=login_form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET','POST'])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()

    #if user submits comments
    if comment_form.validate_on_submit():
        if current_user.is_anonymous or not current_user.is_authenticated:
            flash("Please login to comment")

        else:
            new_comment = Comment(
                comment_body=comment_form.body.data,
                author_id=current_user.id,
                post_id=post_id,
                comment_date=TODAY_DATE
            )
            db.session.add(new_comment)
            db.session.commit()
            print('saved comment and associate with user')

    return render_template("post.html", post=requested_post, form=comment_form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=['GET','POST'])
@login_required
@admin_only
def add_new_post():
    print("add-new-post")
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            date=TODAY_DATE
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['GET','POST'])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        try:
            edit_form.populate_obj(post)
            db.session.commit()
            print("blog edited and added to db")
        except Exception as error:
            return {"response": {"error": "{}".format(error)}}
        else:
            return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

@app.errorhandler(404)
def page_not_found(e):
    e=str(e)
    print(type(e))
    # note that we set the 404 status explicitly
    return render_template('error.html', error=e), 404

@app.errorhandler(403)
def not_authorized(e):
    e=str(e)
    print(type(e))
    # note that we set the 404 status explicitly
    return render_template('error.html', error=e), 403

@login_manager.unauthorized_handler     # In unauthorized_handler we have a callback URL
def unauthorized_callback():            # In call back url we can specify where we want to
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
