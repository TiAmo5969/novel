import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
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

#定义根目录
ROOT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# 检查文件扩展名
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# 模板过滤器
@app.template_filter('safe_strftime')
def safe_strftime(date_value, format_string='%b %Y'):
    """安全地格式化日期，处理字符串和datetime对象"""
    if not date_value:
        return 'Unknown'
    
    # 如果是字符串（比如 'CURRENT_TIMESTAMP'），返回默认值
    if isinstance(date_value, str):
        if date_value == 'CURRENT_TIMESTAMP':
            return 'Recent'
        # 尝试解析ISO格式的日期字符串
        try:
            date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            return date_obj.strftime(format_string)
        except (ValueError, AttributeError):
            return 'Recent'
    
    # 如果是datetime对象，直接格式化
    try:
        return date_value.strftime(format_string)
    except (AttributeError, ValueError):
        return 'Recent'

@app.template_filter('format_paragraphs')
def format_paragraphs(text):
    """格式化段落，将换行符转换为HTML段落标签"""
    if not text:
        return ''
    
    # 将Windows和Unix换行符统一处理
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 按双换行符分割段落
    paragraphs = text.split('\n\n')
    
    # 如果没有双换行符，按单换行符分割
    if len(paragraphs) == 1:
        paragraphs = text.split('\n')
    
    # 过滤空段落并包装在<p>标签中
    formatted_paragraphs = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if paragraph:  # 跳过空段落
            # 将单个换行符转换为<br>标签（主要用于诗歌或特殊格式）
            paragraph = paragraph.replace('\n', '<br>')
            
            # 所有段落使用统一样式
            formatted_paragraphs.append(f'<p class="mb-6 leading-relaxed text-gray-800 dark:text-gray-200 text-justify">{paragraph}</p>')
    
    return '\n'.join(formatted_paragraphs)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 表单
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Submit')

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
            flash('Only admins can access this page')  # '仅管理员可访问此页面'
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# 路由
@app.route('/')
def index():
    # 获取推荐小说（所有小说的前4个）
    recommended_novels = Novel.query.limit(4).all()
    
    # 获取奇幻小说（前4个）
    fantasy_novels = Novel.query.filter_by(category='Fantasy').limit(4).all()
    
    # 获取言情小说（前4个）
    romance_novels = Novel.query.filter_by(category='Romance').limit(4).all()
    
    return render_template('index.html', 
                         recommended_novels=recommended_novels,
                         fantasy_novels=fantasy_novels, 
                         romance_novels=romance_novels)

@app.route('/keep-alive')
def keep_alive():
    return 'Server is running', 200

@app.route('/novel/<int:novel_id>')
@app.route('/novel/<int:novel_id>/page/<int:page>')
def novel(novel_id, page=1):
    novel = Novel.query.get_or_404(novel_id)
    related_novels = Novel.query.filter_by(category=novel.category).filter(Novel.id != novel_id).limit(3).all()
    
    # 分页设置：每页20章
    per_page = 20
    chapters = Chapter.query.filter_by(novel_id=novel_id).order_by(Chapter.id).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('novel.html', novel=novel, related_novels=related_novels, chapters=chapters)

@app.route('/novel/<int:novel_id>/chapter/<int:chapter_id>')
def chapter(novel_id, chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    if chapter.novel_id != novel_id:
        flash('Chapter does not belong to this novel')  # '章节不属于该小说'
        return redirect(url_for('novel', novel_id=novel_id))

    # 获取当前小说的所有章节，按 id 排序
    chapters = Chapter.query.filter_by(novel_id=novel_id).order_by(Chapter.id).all()
    chapter_ids = [c.id for c in chapters]

    # 找到当前章节的索引
    current_index = chapter_ids.index(chapter_id)

    # 计算上一章和下一章的 ID
    prev_chapter_id = chapter_ids[current_index - 1] if current_index > 0 else None
    next_chapter_id = chapter_ids[current_index + 1] if current_index < len(chapter_ids) - 1 else None

    form = CommentForm()
    return render_template('chapter.html', chapter=chapter, form=form,
                           prev_chapter_id=prev_chapter_id, next_chapter_id=next_chapter_id, novel_id=novel_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')  # '用户名或密码错误'
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists')  # '用户名已存在'
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
    return render_template('category.html', novels=novels, category=category, meta_description=f"Explore {category} novels on TaleTap.")

@app.route('/add_to_shelf/<int:novel_id>', methods=['POST'])
@login_required
def add_to_shelf(novel_id):
    if not UserNovel.query.filter_by(user_id=current_user.id, novel_id=novel_id).first():
        shelf = UserNovel(user_id=current_user.id, novel_id=novel_id)
        db.session.add(shelf)
        db.session.commit()
    return redirect(url_for('novel', novel_id=novel_id))

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/sitemap.xml')
def sitemap():
    from flask import make_response
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # 添加主页
    xml += '<url><loc>https://taletap.org/</loc><lastmod>2025-01-01</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>\n'
    
    # 添加重要页面
    important_pages = [
        ('about', 'monthly', '0.8'),
        ('contact', 'monthly', '0.6'),
        ('privacy-policy', 'monthly', '0.5'),
        ('terms-of-service', 'monthly', '0.5'),
    ]
    
    for page, freq, priority in important_pages:
        xml += f'<url><loc>https://taletap.org/{page}</loc><lastmod>2025-01-01</lastmod><changefreq>{freq}</changefreq><priority>{priority}</priority></url>\n'
    
    # 添加分类页面
    categories = ['Fantasy', 'Romance', 'Sci-Fi', 'Mystery', 'Thriller', 'Recommended']
    for category in categories:
        xml += f'<url><loc>https://taletap.org/category/{category}</loc><lastmod>2025-01-01</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>\n'
    
    # 添加小说页面
    novels = Novel.query.all()
    for novel in novels:
        xml += f'<url><loc>https://taletap.org/novel/{novel.id}</loc><lastmod>2025-01-01</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>\n'
        
        # 添加章节页面（只添加前几章，避免sitemap过大）
        chapters = Chapter.query.filter_by(novel_id=novel.id).limit(5).all()
        for chapter in chapters:
            xml += f'<url><loc>https://taletap.org/novel/{novel.id}/chapter/{chapter.id}</loc><lastmod>2025-01-01</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>\n'
    
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