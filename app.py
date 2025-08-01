import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from models import db, User, Novel, Chapter, Comment, UserNovel

app = Flask(__name__)
# app.config['SECRET_KEY'] = os.urandom(24).hex()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'site.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'site.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'img')  # 图片保存目录
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # 允许的文件扩展名
db.init_app(app)

# 检查文件扩展名
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 表单
class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('注册')

class CommentForm(FlaskForm):
    content = TextAreaField('评论', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('提交')

class NovelForm(FlaskForm):
    title = StringField('小说标题', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('描述', validators=[DataRequired()])
    cover_image = StringField('封面图片文件名', validators=[Length(max=200)])
    category = StringField('分类', validators=[Length(max=50)])
    submit = SubmitField('提交')

class ChapterForm(FlaskForm):
    title = StringField('章节标题', validators=[DataRequired(), Length(max=100)])
    content = TextAreaField('内容', validators=[DataRequired()])
    submit = SubmitField('提交')

# 管理员检查装饰器
def admin_required(f):
    @wraps(f)  # 保留原始函数的元信息，避免端点冲突
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.username != 'admin':
            flash('仅管理员可访问此页面')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# 路由
@app.route('/')
def index():
    novels = Novel.query.all()
    return render_template('index.html', novels=novels)

@app.route('/novel/<int:novel_id>')
def novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    return render_template('novel.html', novel=novel)

@app.route('/novel/<int:novel_id>/chapter/<int:chapter_id>')
def chapter(novel_id, chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    form = CommentForm()
    return render_template('chapter.html', chapter=chapter, form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('用户名或密码错误')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('用户名已存在')
        else:
            user = User(username=form.username.data,
                       password=generate_password_hash(form.password.data))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/chapter/<int:chapter_id>/comment', methods=['POST'])
@login_required
def add_comment(chapter_id):
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(content=form.content.data, user_id=current_user.id, chapter_id=chapter_id)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('chapter', novel_id=Chapter.query.get(chapter_id).novel_id, chapter_id=chapter_id))

@app.route('/category/<string:category>')
def category(category):
    novels = Novel.query.filter_by(category=category).all()
    return render_template('index.html', novels=novels, category=category)

@app.route('/add_to_shelf/<int:novel_id>', methods=['POST'])
@login_required
def add_to_shelf(novel_id):
    if not UserNovel.query.filter_by(user_id=current_user.id, novel_id=novel_id).first():
        shelf = UserNovel(user_id=current_user.id, novel_id=novel_id)
        db.session.add(shelf)
        db.session.commit()
    return redirect(url_for('novel', novel_id=novel_id))

@app.route('/sitemap.xml')
def sitemap():
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '<url><loc>http://127.0.0.1:5000/</loc></url>\n'
    for novel in Novel.query.all():
        xml += f'<url><loc>http://127.0.0.1:5000/novel/{novel.id}</loc></url>\n'
        for chapter in novel.chapters:
            xml += f'<url><loc>http://127.0.0.1:5000/novel/{novel.id}/chapter/{chapter.id}</loc></url>\n'
    xml += '</urlset>'
    response = make_response(xml)
    response.headers['Content-Type'] = 'application/xml'
    return response

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

# 后台管理路由
@app.route('/admin', endpoint='admin_dashboard')
@admin_required
def admin_dashboard():
    novels = Novel.query.all()
    return render_template('admin/dashboard.html', novels=novels)

@app.route('/admin/novel/new', methods=['GET', 'POST'], endpoint='add_novel')
@admin_required
def add_novel():
    form = NovelForm()
    if form.validate_on_submit():
        novel = Novel(
            title=form.title.data,
            description=form.description.data,
            cover_image=form.cover_image.data or 'cover.jpg',
            category=form.category.data
        )
        db.session.add(novel)
        db.session.commit()
        flash('小说添加成功！')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/novel_form.html', form=form, title='添加小说')

@app.route('/admin/novel/<int:novel_id>/edit', methods=['GET', 'POST'], endpoint='edit_novel')
@admin_required
def edit_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    form = NovelForm(obj=novel)
    if form.validate_on_submit():
        novel.title = form.title.data
        novel.description = form.description.data
        novel.cover_image = form.cover_image.data or 'cover.jpg'
        novel.category = form.category.data
        db.session.commit()
        flash('小说更新成功！')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/novel_form.html', form=form, title='编辑小说')

@app.route('/admin/novel/<int:novel_id>/delete', methods=['POST'], endpoint='delete_novel')
@admin_required
def delete_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    db.session.delete(novel)
    db.session.commit()
    flash('小说删除成功！')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/novel/<int:novel_id>/chapter/new', methods=['GET', 'POST'], endpoint='add_chapter')
@admin_required
def add_chapter(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    form = ChapterForm()
    if form.validate_on_submit():
        chapter = Chapter(
            novel_id=novel_id,
            title=form.title.data,
            content=form.content.data
        )
        db.session.add(chapter)
        db.session.commit()
        flash('章节添加成功！')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/chapter_form.html', form=form, novel=novel, title='添加章节')

@app.route('/admin/novel/<int:novel_id>/chapter/<int:chapter_id>/edit', methods=['GET', 'POST'], endpoint='edit_chapter')
@admin_required
def edit_chapter(novel_id, chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    form = ChapterForm(obj=chapter)
    if form.validate_on_submit():
        chapter.title = form.title.data
        chapter.content = form.content.data
        db.session.commit()
        flash('章节更新成功！')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/chapter_form.html', form=form, novel=chapter.novel, title='编辑章节')

@app.route('/admin/novel/<int:novel_id>/chapter/<int:chapter_id>/delete', methods=['POST'], endpoint='delete_chapter')
@admin_required
def delete_chapter(novel_id, chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    db.session.delete(chapter)
    db.session.commit()
    flash('章节删除成功！')
    return redirect(url_for('admin_dashboard'))


# 数据库初始化
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123'))
        novel1 = Novel(title='黑暗森林', description='科幻小说', cover_image='cover_fantasy.jpg', category='科幻')
        novel2 = Novel(title='倾城之恋', description='言情小说', cover_image='cover_romance.jpg', category='言情')
        db.session.add_all([admin, novel1, novel2])
        db.session.commit()

if __name__ == '__main__':
    # with app.app_context():
    #     db.create_all()
    app.run(debug=True)