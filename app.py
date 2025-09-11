import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
import uuid
from models import db, User, Novel, Chapter, Comment, UserNovel
from novel_importer import NovelImporter, DatabaseImporter

app = Flask(__name__)
# 设置固定的SECRET_KEY，避免重启后session失效
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-fixed-secret-key-for-development-12345')

# 配置session持久化
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # 会话保持7天
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # 开发环境设置为False，生产环境应设置为True
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'site.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'site.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'img')  # 图片保存目录
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # 允许的文件扩展名
db.init_app(app)

# 初始化 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录访问此页面'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#定义根目录
ROOT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# 检查文件扩展名
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 处理封面图片上传
def handle_cover_upload(cover_file):
    """处理封面图片上传，返回文件名或None"""
    if cover_file and cover_file.filename != '' and allowed_file(cover_file.filename):
        # 生成唯一的文件名
        filename = secure_filename(cover_file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{uuid.uuid4().hex[:8]}_{name}{ext}"
        
        # 确保上传目录存在
        upload_dir = os.path.join(ROOT_DIRECTORY, app.config['UPLOAD_FOLDER'])
        os.makedirs(upload_dir, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(upload_dir, unique_filename)
        cover_file.save(file_path)
        
        return unique_filename
    return None

# 删除旧的封面文件
def delete_old_cover(cover_filename):
    """删除旧的封面文件"""
    if cover_filename and cover_filename not in ['cover.jpg', 'cover_fantasy.jpg', 'cover_romance.jpg']:
        # 不删除默认封面文件
        old_file_path = os.path.join(ROOT_DIRECTORY, app.config['UPLOAD_FOLDER'], cover_filename)
        try:
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        except Exception as e:
            print(f"无法删除旧封面文件: {e}")

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

# 表单
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

# 登录表单
class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('登录')

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=True)  # 设置记住用户
            flash('登录成功！')
            # 获取next参数，如果没有则跳转到管理后台
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('admin_dashboard'))
        else:
            flash('用户名或密码错误')
    
    return render_template('login.html', title='登录', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已成功退出登录')
    return redirect(url_for('index'))

# 路由
@app.route('/')
def index():
    # 获取推荐小说（最新添加的4本小说）
    recommended_novels = Novel.query.order_by(Novel.id.desc()).limit(4).all()
    
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
    if category == 'Recommended':
        # 对于推荐小说，显示最新添加的12本小说
        novels = Novel.query.order_by(Novel.id.desc()).limit(12).all()
    else:
        # 其他类别按正常方式过滤
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

@app.route('/search')
def search():
    """搜索小说功能"""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12  # 每页显示12本小说
    
    if not query:
        # 如果没有搜索关键词，返回空结果
        novels = []
        total = 0
    else:
        # 使用SQLAlchemy的模糊匹配功能
        # 搜索标题、作者、描述中包含关键词的小说
        search_filter = db.or_(
            Novel.title.contains(query),
            Novel.author.contains(query),
            Novel.description.contains(query),
            Novel.category.contains(query)
        )
        
        # 执行搜索并分页
        novels_pagination = Novel.query.filter(search_filter).paginate(
            page=page, per_page=per_page, error_out=False
        )
        novels = novels_pagination.items
        total = novels_pagination.total
    
    return render_template('search_results.html', 
                         novels=novels, 
                         query=query, 
                         page=page,
                         total=total,
                         per_page=per_page)

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
        # 处理封面上传
        cover_file = request.files.get('cover')
        cover_filename = handle_cover_upload(cover_file)
        
        # 如果没有上传封面，使用默认封面
        if not cover_filename:
            cover_filename = 'cover_fantasy.jpg'  # 默认封面
        
        novel = Novel(
            title=form.title.data,
            description=form.description.data,
            cover_image=cover_filename,
            category=form.category.data
        )
        db.session.add(novel)
        db.session.commit()
        flash('小说添加成功！')
        return redirect(url_for('admin_dashboard'))
    
    # 如果有文件上传错误，显示提示
    if request.method == 'POST' and request.files.get('cover'):
        cover_file = request.files.get('cover')
        if cover_file.filename != '' and not allowed_file(cover_file.filename):
            flash('请选择有效的图片文件 (PNG, JPG, JPEG, GIF)')
    
    return render_template('admin/novel_form.html', form=form, title='添加小说')

@app.route('/admin/novel/<int:novel_id>/edit', methods=['GET', 'POST'], endpoint='edit_novel')
@admin_required
def edit_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    form = NovelForm(obj=novel)
    if form.validate_on_submit():
        # 处理封面上传
        cover_file = request.files.get('cover')
        new_cover_filename = handle_cover_upload(cover_file)
        
        # 如果有新封面，删除旧封面（除非是默认封面）
        if new_cover_filename:
            delete_old_cover(novel.cover_image)
            novel.cover_image = new_cover_filename
        
        # 更新其他字段
        novel.title = form.title.data
        novel.description = form.description.data
        novel.category = form.category.data
        novel.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('小说更新成功！')
        return redirect(url_for('admin_dashboard'))
    
    # 如果有文件上传错误，显示提示
    if request.method == 'POST' and request.files.get('cover'):
        cover_file = request.files.get('cover')
        if cover_file.filename != '' and not allowed_file(cover_file.filename):
            flash('请选择有效的图片文件 (PNG, JPG, JPEG, GIF)')
    
    return render_template('admin/novel_form.html', form=form, novel=novel, title='编辑小说')

@app.route('/admin/novel/<int:novel_id>/delete', methods=['POST'], endpoint='delete_novel')
@admin_required
def delete_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    
    try:
        # 删除关联的封面文件
        if novel.cover_image:
            delete_old_cover(novel.cover_image)
        
        # 先删除所有相关的评论
        for chapter in novel.chapters:
            Comment.query.filter_by(chapter_id=chapter.id).delete()
        
        # 删除所有相关的章节
        Chapter.query.filter_by(novel_id=novel_id).delete()
        
        # 删除用户书架中的记录
        UserNovel.query.filter_by(novel_id=novel_id).delete()
        
        # 最后删除小说记录
        db.session.delete(novel)
        db.session.commit()
        flash('小说删除成功！')
        
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}')
        print(f"删除小说时出错: {e}")
    
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
    
    try:
        # 先删除所有相关的评论
        Comment.query.filter_by(chapter_id=chapter_id).delete()
        
        # 删除章节
        db.session.delete(chapter)
        db.session.commit()
        flash('章节删除成功！')
        
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}')
        print(f"删除章节时出错: {e}")
    
    return redirect(url_for('admin_dashboard'))

# 批量导入功能
@app.route('/admin/batch-import', methods=['GET'], endpoint='batch_import')
@admin_required
def batch_import():
    return render_template('admin/batch_import.html', title='批量导入小说')

@app.route('/admin/analyze-novel', methods=['POST'], endpoint='analyze_novel')
@admin_required
def analyze_novel():
    """分析上传的小说文件"""
    try:
        if 'novel_file' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'})
        
        file = request.files['novel_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'})
        
        if not file.filename.lower().endswith('.txt'):
            return jsonify({'success': False, 'error': '只支持TXT格式文件'})
        
        # 保存临时文件
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{uuid.uuid4().hex[:8]}_{filename}")
        
        # 确保上传目录存在
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(temp_path)
        
        try:
            # 使用导入器分析文件
            importer = NovelImporter()
            novel_info, issues = importer.process_novel_file(temp_path)
            
            # 生成预览数据
            preview_data = importer.generate_preview_data(novel_info)
            preview_data['issues'] = issues
            
            # 生成唯一ID用于标识这次解析
            analysis_id = uuid.uuid4().hex
            
            # 保存完整的解析数据到临时文件（用于后续导入）
            analysis_data = {
                'novel_info': {
                    'title': novel_info.title,
                    'author': novel_info.author,
                    'description': novel_info.description,
                    'language': novel_info.language.value,
                    'category': novel_info.category,
                    'chapters': [
                        {
                            'title': ch.title,
                            'content': ch.content,
                            'chapter_number': ch.chapter_number
                        }
                        for ch in novel_info.chapters
                    ]
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # 保存到临时JSON文件
            temp_json_path = os.path.join(app.config['UPLOAD_FOLDER'], f"analysis_{analysis_id}.json")
            with open(temp_json_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            # 在预览数据中包含analysis_id
            preview_data['analysis_id'] = analysis_id
            
            return jsonify({
                'success': True,
                'data': preview_data
            })
            
        finally:
            # 清理原始临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/import-novel', methods=['POST'], endpoint='import_novel')
@admin_required
def import_novel():
    """执行小说导入"""
    try:
        # 处理multipart/form-data格式的请求
        if request.content_type and 'multipart/form-data' in request.content_type:
            # 从表单获取数据
            analysis_id = request.form.get('analysis_id')
            title = request.form.get('title')
            author = request.form.get('author')
            description = request.form.get('description')
            category = request.form.get('category')
            cover_file = request.files.get('cover_file')
        else:
            # JSON格式请求
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '无效的数据'})
            
            analysis_id = data.get('analysis_id')
            title = data.get('title')
            author = data.get('author')
            description = data.get('description')
            category = data.get('category')
            cover_file = None
        
        if not analysis_id:
            return jsonify({'success': False, 'error': '缺少分析ID'})
        
        # 处理封面上传
        cover_filename = 'cover_fantasy.jpg'  # 默认封面
        if cover_file and cover_file.filename:
            uploaded_cover = handle_cover_upload(cover_file)
            if uploaded_cover:
                cover_filename = uploaded_cover
        
        # 读取之前保存的解析数据
        temp_json_path = os.path.join(app.config['UPLOAD_FOLDER'], f"analysis_{analysis_id}.json")
        
        if not os.path.exists(temp_json_path):
            return jsonify({'success': False, 'error': '解析数据已过期，请重新解析文件'})
        
        try:
            with open(temp_json_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            novel_info = analysis_data['novel_info']
            
            # 使用用户修改后的数据覆盖原始数据
            novel_info['title'] = title or novel_info['title']
            novel_info['author'] = author or novel_info['author']
            novel_info['description'] = description or novel_info['description']
            novel_info['category'] = category or novel_info['category']
            
            # 检查是否需要翻译
            enable_translation = request.form.get('enable_translation') == 'true'
            custom_prompt = request.form.get('custom_prompt', '').strip()
            prompt_type = request.form.get('prompt_type', 'novel_general')
            
            if enable_translation and novel_info.get('language') == 'zh':
                print("启用翻译功能...")
                try:
                    from novel_importer import NovelImporter, NovelInfo, ChapterInfo, Language
                    
                    # 重构数据为NovelInfo对象
                    chapters = []
                    for ch_data in novel_info['chapters']:
                        chapters.append(ChapterInfo(
                            title=ch_data['title'],
                            content=ch_data['content'],
                            chapter_number=ch_data.get('chapter_number', 0)
                        ))
                    
                    novel_obj = NovelInfo(
                        title=novel_info['title'],
                        author=novel_info['author'],
                        description=novel_info['description'],
                        language=Language.CHINESE,
                        category=novel_info['category'],
                        chapters=chapters
                    )
                    
                    # 执行翻译
                    importer = NovelImporter()
                    if custom_prompt:
                        print(f"使用自定义提示词: {custom_prompt[:50]}...")
                        translated_novel = importer.translate_novel_simple(novel_obj, custom_prompt=custom_prompt, prompt_type=prompt_type)
                    else:
                        translated_novel = importer.translate_novel_simple(novel_obj, prompt_type=prompt_type)
                    
                    # 更新数据
                    novel_info['title'] = translated_novel.title
                    novel_info['description'] = translated_novel.description
                    novel_info['language'] = translated_novel.language.value
                    novel_info['category'] = translated_novel.category
                    novel_info['chapters'] = [
                        {
                            'title': ch.title,
                            'content': ch.content,
                            'chapter_number': ch.chapter_number
                        }
                        for ch in translated_novel.chapters
                    ]
                    
                except Exception as e:
                    print(f"翻译过程出错: {e}")
                    flash('翻译过程中出现错误，将保存原文版本')
            
            # 创建小说记录
            novel = Novel(
                title=novel_info['title'],
                author=novel_info['author'],
                description=novel_info['description'],
                category=novel_info['category'],
                cover_image=cover_filename
            )
            
            db.session.add(novel)
            db.session.flush()
            
            # 批量创建章节记录
            chapters_to_add = []
            for chapter_data in novel_info['chapters']:
                chapter = Chapter(
                    novel_id=novel.id,
                    title=chapter_data['title'],
                    content=chapter_data['content']
                )
                chapters_to_add.append(chapter)
                
                # 分批提交，避免内存问题
                if len(chapters_to_add) >= 50:
                    db.session.add_all(chapters_to_add)
                    db.session.flush()
                    chapters_to_add = []
            
            # 提交剩余的章节
            if chapters_to_add:
                db.session.add_all(chapters_to_add)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'novel_id': novel.id,
                'message': '小说导入成功',
                'chapters_imported': len(novel_info['chapters'])
            })
            
        finally:
            # 清理临时分析文件
            if os.path.exists(temp_json_path):
                os.remove(temp_json_path)
                
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/novel-translator', methods=['GET'], endpoint='novel_translator')
@admin_required
def novel_translator():
    """小说翻译器页面"""
    return render_template('admin/novel_translator.html')

@app.route('/admin/novel-manager', methods=['GET'], endpoint='novel_manager')
@admin_required
def novel_manager():
    """小说管理器页面"""
    return render_template('admin/novel_manager.html')

@app.route('/admin/save-parsed-novel', methods=['POST'], endpoint='save_parsed_novel')
@admin_required
def save_parsed_novel():
    """保存解析后的小说到数据库"""
    try:
        session_key = request.form.get('session_key')
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        cover_file = request.files.get('cover_file')
        
        if not session_key:
            return jsonify({'success': False, 'error': '会话已过期，请重新解析'})
        
        if not title:
            return jsonify({'success': False, 'error': '请输入小说标题'})
        
        if not author:
            return jsonify({'success': False, 'error': '请输入作者名'})
        
        if not category:
            return jsonify({'success': False, 'error': '请选择小说类型'})
        
        # 从缓存获取解析数据
        cache = app.config.get('NOVEL_PARSE_CACHE', {})
        if session_key not in cache:
            return jsonify({'success': False, 'error': '解析数据不存在，请重新解析'})
        
        cached_data = cache[session_key]
        novel_info = cached_data['novel_info']
        
        # 处理封面上传
        cover_filename = 'cover_default.jpg'
        if cover_file and cover_file.filename != '':
            cover_filename = handle_cover_upload(cover_file)
            if not cover_filename:
                return jsonify({'success': False, 'error': '封面上传失败'})
        
        # 创建小说记录
        novel = Novel(
            title=title,
            author=author,
            description=description if description else '',
            category=category,
            cover_image=cover_filename
        )
        
        db.session.add(novel)
        db.session.flush()  # 获取novel.id
        
        # 批量创建章节记录
        chapters_to_add = []
        for i, chapter in enumerate(novel_info.chapters):
            db_chapter = Chapter(
                novel_id=novel.id,
                title=chapter.title,
                content=chapter.content,
                chapter_number=chapter.chapter_number
            )
            chapters_to_add.append(db_chapter)
            
            # 分批提交，避免内存问题
            if len(chapters_to_add) >= 50:
                db.session.add_all(chapters_to_add)
                db.session.flush()
                chapters_to_add = []
        
        # 提交剩余章节
        if chapters_to_add:
            db.session.add_all(chapters_to_add)
        
        db.session.commit()
        
        # 清理缓存
        cache.pop(session_key, None)
        
        return jsonify({
            'success': True, 
            'message': f'小说《{title}》已成功保存到数据库',
            'novel_id': novel.id
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"保存小说出错: {error_details}")
        return jsonify({'success': False, 'error': f'保存失败: {str(e)}'})

@app.route('/admin/parse-novel', methods=['POST'], endpoint='parse_novel')
@admin_required
def parse_novel():
    """解析小说文件"""
    try:
        if 'novel_file' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'})
        
        file = request.files['novel_file']
        # 使用预设的API密钥或从请求中获取
        api_key = request.form.get('api_key', 'sk-569322c3628b412483ee81ffbf5794f1').strip()
        
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': '文件为空'})
        
        if not api_key:
            return jsonify({'success': False, 'error': '请提供API Key'})
        
        # 保存临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
        
        # 处理封面文件
        cover_file = request.files.get('cover_file')
        cover_filename = None
        if cover_file and cover_file.filename != '':
            cover_filename = handle_cover_upload(cover_file)
        
        # 获取小说类型
        category = request.form.get('category', '').strip()
        
        try:
            # 使用翻译器解析文件
            try:
                from novel_translator_qwen import QwenNovelTranslator
                translator = QwenNovelTranslator(api_key=api_key)
            except ImportError as e:
                return jsonify({'success': False, 'error': f'翻译器模块导入失败: {str(e)}'})
            except Exception as e:
                return jsonify({'success': False, 'error': f'翻译器初始化失败: {str(e)}'})
            
            success, novel_info, issues = translator.parse_novel_file(temp_file_path)
            
            if success:
                # 估算成本
                estimated_cost = translator.estimate_cost(novel_info)
                
                # 生成预览数据
                preview_data = {
                    'title': novel_info.title,
                    'author': novel_info.author,
                    'description': novel_info.description,
                    'category': novel_info.category,
                    'chapter_count': len(novel_info.chapters),
                    'total_words': sum(len(ch.title) + len(ch.content) for ch in novel_info.chapters),
                    'first_chapters': [
                        {
                            'title': ch.title,
                            'content_preview': ch.content[:200] + '...' if len(ch.content) > 200 else ch.content,
                            'word_count': len(ch.content)
                        }
                        for ch in novel_info.chapters[:5]
                    ]
                }
                
                # 保存解析数据到session（简单方案）
                import json
                session_key = f"novel_data_{datetime.now().timestamp()}"
                app.config.setdefault('NOVEL_PARSE_CACHE', {})
                app.config['NOVEL_PARSE_CACHE'][session_key] = {
                    'novel_info': novel_info,
                    'api_key': api_key,
                    'cover_filename': cover_filename,
                    'category': category
                }
                
                return jsonify({
                    'success': True,
                    'novel_info': preview_data,
                    'estimated_cost': estimated_cost,
                    'issues': issues,
                    'session_key': session_key
                })
            else:
                return jsonify({'success': False, 'error': '解析失败', 'issues': issues})
                
        finally:
            # 清理临时文件
            import os
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.errorhandler(500)
def handle_internal_error(e):
    """处理500内部服务器错误"""
    return jsonify({'success': False, 'error': '服务器内部错误，请检查日志'}), 500

@app.route('/admin/translate-novel', methods=['POST'], endpoint='translate_novel')
@admin_required  
def translate_novel():
    """开始翻译小说"""
    try:
        # 支持JSON和FormData两种格式
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '无效的数据'})
            
            session_key = data.get('session_key')
            api_key = data.get('api_key', '').strip()
            custom_prompt = data.get('custom_prompt', '').strip()
            description = data.get('description', '').strip()
            category = data.get('category', '').strip()
            cover_file = None
        else:
            # FormData格式
            session_key = request.form.get('session_key')
            api_key = request.form.get('api_key', '').strip()
            custom_prompt = request.form.get('custom_prompt', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', '').strip()
            cover_file = request.files.get('cover_file')
        
        if not session_key:
            return jsonify({'success': False, 'error': '会话已过期，请重新解析'})
        
        # 从缓存获取数据
        cache = app.config.get('NOVEL_PARSE_CACHE', {})
        if session_key not in cache:
            return jsonify({'success': False, 'error': '解析数据不存在，请重新解析'})
        
        cached_data = cache[session_key]
        novel_info = cached_data['novel_info']
        
        # 处理封面文件上传
        cover_filename = None
        if cover_file and cover_file.filename != '':
            cover_filename = handle_cover_upload(cover_file)
        
        # 更新缓存中的封面和类型信息
        cached_data['cover_filename'] = cover_filename
        cached_data['category'] = category
        
        print(f"翻译启动 - 封面文件名: {cover_filename}")
        print(f"翻译启动 - 小说类型: {category}")
        
        # 创建翻译任务ID
        import uuid
        task_id = str(uuid.uuid4())
        
        # 启动后台翻译任务（简化版本，实际应用建议使用Celery等任务队列）
        import threading
        
        def translation_worker():
            try:
                from novel_translator_qwen import QwenNovelTranslator
                translator = QwenNovelTranslator(api_key=api_key)
                
                # 从缓存获取最新的封面和类型信息
                current_cover_filename = cached_data.get('cover_filename')
                current_category = cached_data.get('category')
                
                print(f"翻译线程 - 封面文件名: {current_cover_filename}")
                print(f"翻译线程 - 小说类型: {current_category}")
                
                # 创建进度跟踪
                progress_cache = app.config.setdefault('TRANSLATION_PROGRESS', {})
                progress_cache[task_id] = {
                    'status': 'translating',
                    'progress': {
                        'current_chapter': 0,
                        'total_chapters': len(novel_info.chapters),
                        'current_chapter_title': '',
                        'success_count': 0,
                        'error_count': 0,
                        'estimated_cost': 0.0,
                        'elapsed_time': 0.0,
                        'progress_percent': 0.0,
                        'success_rate': 100.0
                    },
                    'log_messages': [],
                    'cover_filename': current_cover_filename,
                    'category': current_category
                }
                
                # 进度回调函数
                def progress_callback(progress):
                    progress_data = progress_cache[task_id]
                    progress_data['progress'] = {
                        'current_chapter': progress.current_chapter,
                        'total_chapters': progress.total_chapters,
                        'current_chapter_title': progress.current_chapter_title,
                        'success_count': progress.success_count,
                        'error_count': progress.error_count,
                        'estimated_cost': progress.estimated_cost,
                        'elapsed_time': progress.elapsed_time,
                        'progress_percent': progress.progress_percent,
                        'success_rate': progress.success_rate
                    }
                    progress_data['log_message'] = f"正在翻译: {progress.current_chapter_title}"
                    progress_data['log_level'] = 'info'
                
                # 更新小说信息（如果有自定义描述）
                if description:
                    novel_info.description = description
                
                # 开始翻译
                success, translated_novel, message = translator.translate_novel(
                    novel_info,
                    custom_prompt=custom_prompt,
                    progress_callback=progress_callback
                )
                
                if success:
                    # 保存翻译结果
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
                        translator.save_translated_novel(translated_novel, temp_file.name)
                        
                        # 读取内容
                        with open(temp_file.name, 'r', encoding='utf-8') as f:
                            translated_content = f.read()
                    
                    progress_cache[task_id]['status'] = 'completed'
                    progress_cache[task_id]['result'] = {
                        'title': translated_novel.title,
                        'author': translated_novel.author,
                        'description': translated_novel.description,
                        'content': translated_content,
                        'category': current_category or translated_novel.category,
                        'cover_filename': current_cover_filename,
                        'chapters': [
                            {
                                'title': chapter.title,
                                'content': chapter.content,
                                'chapter_number': chapter.chapter_number
                            }
                            for chapter in translated_novel.chapters
                        ]
                    }
                    
                    print(f"翻译完成 - 保存的封面文件名: {current_cover_filename}")
                    print(f"翻译完成 - 保存的小说类型: {current_category or translated_novel.category}")
                    progress_cache[task_id]['stats'] = {
                        'success_count': progress_cache[task_id]['progress']['success_count'],
                        'error_count': progress_cache[task_id]['progress']['error_count'],
                        'total_cost': translator.total_cost,
                        'elapsed_time': progress_cache[task_id]['progress']['elapsed_time'],
                        'success_rate': progress_cache[task_id]['progress']['success_rate']
                    }
                else:
                    progress_cache[task_id]['status'] = 'error'
                    progress_cache[task_id]['error'] = message
                    
            except Exception as e:
                if task_id in progress_cache:
                    progress_cache[task_id]['status'] = 'error'
                    progress_cache[task_id]['error'] = str(e)
                else:
                    # 如果进度缓存不存在，创建一个错误记录
                    progress_cache = app.config.setdefault('TRANSLATION_PROGRESS', {})
                    progress_cache[task_id] = {
                        'status': 'error',
                        'error': str(e)
                    }
        
        # 启动翻译线程
        thread = threading.Thread(target=translation_worker)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"翻译过程中出错: {error_details}")
        return jsonify({'success': False, 'error': f'翻译启动失败: {str(e)}'})

@app.route('/admin/translation-progress/<task_id>', methods=['GET'], endpoint='translation_progress')
@admin_required
def translation_progress(task_id):
    """获取翻译进度"""
    try:
        progress_cache = app.config.get('TRANSLATION_PROGRESS', {})
        
        if task_id not in progress_cache:
            return jsonify({'success': False, 'error': '翻译任务不存在'})
        
        progress_data = progress_cache[task_id]
        # print(f"返回翻译进度数据: {progress_data}")


        return jsonify(progress_data)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/save-translated-novel', methods=['POST'], endpoint='save_translated_novel')
@admin_required
def save_translated_novel():
    """保存翻译后的小说到数据库"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的数据'})
        
        novel_info = data.get('novel_info')
        if not novel_info:
            return jsonify({'success': False, 'error': '小说数据不完整'})
        
        # 调试信息
        print(f"保存小说数据: {novel_info}")
        print(f"封面文件名: {novel_info.get('cover_filename', 'cover_fantasy.jpg')}")
        
        # 创建小说记录
        novel = Novel(
            title=novel_info['title'],
            author=novel_info['author'],
            description=novel_info['description'],
            category=novel_info['category'],
            cover_image=novel_info.get('cover_filename', 'cover_fantasy.jpg')
        )
        
        db.session.add(novel)
        db.session.flush()  # 获取novel.id
        
        # 批量创建章节记录
        chapters_to_add = []
        for i, chapter_data in enumerate(novel_info['chapters']):
            chapter = Chapter(
                novel_id=novel.id,
                title=chapter_data['title'],
                content=chapter_data['content']
            )
            chapters_to_add.append(chapter)
            
            # 分批提交
            if len(chapters_to_add) >= 50:
                db.session.add_all(chapters_to_add)
                db.session.flush()
                chapters_to_add = []
        
        # 提交剩余章节
        if chapters_to_add:
            db.session.add_all(chapters_to_add)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'novel_id': novel.id,
            'message': '小说已成功保存到数据库',
            'chapters_count': len(novel_info['chapters'])
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/get-prompt-templates', methods=['GET'], endpoint='get_prompt_templates')
@admin_required
def get_prompt_templates():
    """获取可用的提示词模板"""
    try:
        from translation_prompts import PromptManager
        manager = PromptManager()
        templates = manager.get_available_prompts()
        
        return jsonify({
            'success': True,
            'templates': templates
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'templates': {
                'novel_general': '通用小说翻译',
                'novel_fantasy': '玄幻小说翻译',
                'novel_romance': '言情小说翻译',
                'dialogue_focused': '对话重点翻译'
            }
        })

# 章节批量翻译相关路由
@app.route('/admin/analyze-chapters', methods=['POST'], endpoint='analyze_chapters')
@admin_required
def analyze_chapters():
    """分析上传的章节文件"""
    try:
        if 'novel_file' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'})
        
        file = request.files['novel_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'})
        
        if not file.filename.lower().endswith('.txt'):
            return jsonify({'success': False, 'error': '只支持TXT格式文件'})
        
        # 获取参数
        api_key = request.form.get('api_key', '').strip()
        custom_prompt = request.form.get('custom_prompt', '').strip()
        preview_mode = request.form.get('preview_mode') == 'true'
        novel_id = request.form.get('novel_id')
        
        if not novel_id:
            return jsonify({'success': False, 'error': '缺少小说ID'})
        
        # 保存临时文件
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_chapters_{uuid.uuid4().hex[:8]}_{filename}")
        
        # 确保上传目录存在
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(temp_path)
        
        try:
            # 使用翻译器分析文件
            from novel_translator_qwen import QwenNovelTranslator
            translator = QwenNovelTranslator(api_key=api_key if api_key else None)
            
            success, novel_info, issues = translator.parse_novel_file(temp_path)
            
            if success:
                # 如果是预览模式，只保留前3章
                if preview_mode and len(novel_info.chapters) > 3:
                    novel_info.chapters = novel_info.chapters[:3]
                
                # 生成预览数据
                preview_data = {
                    'title': novel_info.title,
                    'author': novel_info.author,
                    'description': novel_info.description,
                    'category': novel_info.category,
                    'chapter_count': len(novel_info.chapters),
                    'total_words': sum(len(ch.title) + len(ch.content) for ch in novel_info.chapters),
                    'preview_chapters': [
                        {
                            'title': ch.title,
                            'content_preview': ch.content[:200] + '...' if len(ch.content) > 200 else ch.content,
                            'word_count': len(ch.content)
                        }
                        for ch in novel_info.chapters[:5]
                    ],
                    'issues': issues
                }
                
                # 生成唯一ID用于标识这次解析
                analysis_id = uuid.uuid4().hex
                
                # 保存完整的解析数据到临时文件
                analysis_data = {
                    'novel_info': {
                        'title': novel_info.title,
                        'author': novel_info.author,
                        'description': novel_info.description,
                        'language': novel_info.language.value,
                        'category': novel_info.category,
                        'chapters': [
                            {
                                'title': ch.title,
                                'content': ch.content,
                                'chapter_number': ch.chapter_number
                            }
                            for ch in novel_info.chapters
                        ]
                    },
                    'novel_id': novel_id,
                    'api_key': api_key,
                    'custom_prompt': custom_prompt,
                    'preview_mode': preview_mode,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # 保存到临时JSON文件
                temp_json_path = os.path.join(app.config['UPLOAD_FOLDER'], f"chapter_analysis_{analysis_id}.json")
                with open(temp_json_path, 'w', encoding='utf-8') as f:
                    json.dump(analysis_data, f, ensure_ascii=False, indent=2)
                
                # 在预览数据中包含analysis_id
                preview_data['analysis_id'] = analysis_id
                
                return jsonify({
                    'success': True,
                    'data': preview_data
                })
            else:
                return jsonify({'success': False, 'error': '解析失败', 'issues': issues})
                
        finally:
            # 清理原始临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/translate-chapters', methods=['POST'], endpoint='translate_chapters')
@admin_required
def translate_chapters():
    """开始翻译章节"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的数据'})
        
        analysis_id = data.get('analysis_id')
        custom_prompt = data.get('custom_prompt', '').strip()
        preview_mode = data.get('preview_mode', False)
        novel_id = data.get('novel_id')
        
        if not analysis_id:
            return jsonify({'success': False, 'error': '缺少分析ID'})
        
        if not novel_id:
            return jsonify({'success': False, 'error': '缺少小说ID'})
        
        # 读取之前保存的解析数据
        temp_json_path = os.path.join(app.config['UPLOAD_FOLDER'], f"chapter_analysis_{analysis_id}.json")
        
        if not os.path.exists(temp_json_path):
            return jsonify({'success': False, 'error': '解析数据已过期，请重新解析文件'})
        
        try:
            with open(temp_json_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            # 更新自定义提示词
            if custom_prompt:
                analysis_data['custom_prompt'] = custom_prompt
            
            # 创建翻译任务ID
            task_id = str(uuid.uuid4())
            
            # 启动后台翻译任务
            import threading
            
            def chapter_translation_worker():
                try:
                    from novel_translator_qwen import QwenNovelTranslator
                    from novel_importer import NovelInfo, ChapterInfo, Language
                    
                    # 重构数据为NovelInfo对象
                    chapters = []
                    for ch_data in analysis_data['novel_info']['chapters']:
                        chapters.append(ChapterInfo(
                            title=ch_data['title'],
                            content=ch_data['content'],
                            chapter_number=ch_data.get('chapter_number', 0)
                        ))
                    
                    novel_obj = NovelInfo(
                        title=analysis_data['novel_info']['title'],
                        author=analysis_data['novel_info']['author'],
                        description=analysis_data['novel_info']['description'],
                        language=Language.CHINESE,
                        category=analysis_data['novel_info']['category'],
                        chapters=chapters
                    )
                    
                    # 初始化翻译器
                    translator = QwenNovelTranslator(api_key=analysis_data.get('api_key'))
                    
                    # 创建进度跟踪
                    progress_cache = app.config.setdefault('CHAPTER_TRANSLATION_PROGRESS', {})
                    progress_cache[task_id] = {
                        'status': 'translating',
                        'progress': {
                            'current_chapter': 0,
                            'total_chapters': len(novel_obj.chapters),
                            'current_chapter_title': '',
                            'success_count': 0,
                            'error_count': 0,
                            'estimated_cost': 0.0,
                            'elapsed_time': 0.0,
                            'progress_percent': 0.0,
                            'success_rate': 100.0
                        },
                        'log_messages': [],
                        'novel_id': novel_id
                    }
                    
                    # 进度回调函数
                    def progress_callback(progress):
                        print(f"进度回调: status={progress.status}, current_chapter={progress.current_chapter}/{progress.total_chapters}")
                        progress_data = progress_cache[task_id]
                        progress_data['progress'] = {
                            'current_chapter': progress.current_chapter,
                            'total_chapters': progress.total_chapters,
                            'current_chapter_title': progress.current_chapter_title,
                            'success_count': progress.success_count,
                            'error_count': progress.error_count,
                            'estimated_cost': progress.estimated_cost,
                            'elapsed_time': progress.elapsed_time,
                            'progress_percent': progress.progress_percent,
                            'success_rate': progress.success_rate
                        }
                        
                        # 更新状态
                        if hasattr(progress, 'status'):
                            progress_data['status'] = progress.status
                            print(f"更新状态为: {progress.status}")
                        
                        # 更新日志消息
                        if progress.status == 'completed':
                            progress_data['log_message'] = f"翻译完成！共 {progress.total_chapters} 章"
                            progress_data['log_level'] = 'success'
                            print(f"翻译完成，设置完成状态")
                        elif progress.status == 'error':
                            progress_data['log_message'] = f"翻译出错: {progress.current_chapter_title}"
                            progress_data['log_level'] = 'error'
                        else:
                            progress_data['log_message'] = f"正在翻译: {progress.current_chapter_title}"
                            progress_data['log_level'] = 'info'
                    
                    # 开始翻译
                    success, translated_novel, message = translator.translate_novel(
                        novel_obj,
                        custom_prompt=analysis_data.get('custom_prompt'),
                        progress_callback=progress_callback
                    )
                    
                    if success:
                        print(f"翻译成功，设置最终完成状态")
                        progress_cache[task_id]['status'] = 'completed'
                        progress_cache[task_id]['result'] = {
                            'title': translated_novel.title,
                            'author': translated_novel.author,
                            'description': translated_novel.description,
                            'chapters': [
                                {
                                    'title': chapter.title,
                                    'content': chapter.content,
                                    'chapter_number': chapter.chapter_number
                                }
                                for chapter in translated_novel.chapters
                            ]
                        }
                        progress_cache[task_id]['stats'] = {
                            'success_count': progress_cache[task_id]['progress']['success_count'],
                            'error_count': progress_cache[task_id]['progress']['error_count'],
                            'total_cost': translator.total_cost,
                            'elapsed_time': progress_cache[task_id]['progress']['elapsed_time'],
                            'success_rate': progress_cache[task_id]['progress']['success_rate']
                        }
                    else:
                        progress_cache[task_id]['status'] = 'error'
                        progress_cache[task_id]['error'] = message
                        
                except Exception as e:
                    if task_id in progress_cache:
                        progress_cache[task_id]['status'] = 'error'
                        progress_cache[task_id]['error'] = str(e)
                    else:
                        # 如果进度缓存不存在，创建一个错误记录
                        progress_cache = app.config.setdefault('CHAPTER_TRANSLATION_PROGRESS', {})
                        progress_cache[task_id] = {
                            'status': 'error',
                            'error': str(e)
                        }
            
            # 启动翻译线程
            thread = threading.Thread(target=chapter_translation_worker)
            thread.daemon = True
            thread.start()
            
            return jsonify({'success': True, 'task_id': task_id})
            
        finally:
            # 清理临时分析文件
            if os.path.exists(temp_json_path):
                os.remove(temp_json_path)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"章节翻译过程中出错: {error_details}")
        return jsonify({'success': False, 'error': f'翻译启动失败: {str(e)}'})

@app.route('/admin/chapter-translation-progress/<task_id>', methods=['GET'], endpoint='chapter_translation_progress')
@admin_required
def chapter_translation_progress(task_id):
    """获取章节翻译进度"""
    try:
        progress_cache = app.config.get('CHAPTER_TRANSLATION_PROGRESS', {})
        
        if task_id not in progress_cache:
            return jsonify({'success': False, 'error': '翻译任务不存在'})
        
        progress_data = progress_cache[task_id]
        return jsonify({'success': True, **progress_data})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/save-translated-chapters', methods=['POST'], endpoint='save_translated_chapters')
@admin_required
def save_translated_chapters():
    """保存翻译后的章节到数据库"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的数据'})
        
        novel_id = data.get('novel_id')
        chapters = data.get('chapters', [])
        
        if not novel_id:
            return jsonify({'success': False, 'error': '缺少小说ID'})
        
        if not chapters:
            return jsonify({'success': False, 'error': '没有章节数据'})
        
        # 验证小说是否存在
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': '小说不存在'})
        
        # 批量创建章节记录
        chapters_to_add = []
        for chapter_data in chapters:
            chapter = Chapter(
                novel_id=novel_id,
                title=chapter_data['title'],
                content=chapter_data['content']
            )
            chapters_to_add.append(chapter)
            
            # 分批提交，避免内存问题
            if len(chapters_to_add) >= 50:
                db.session.add_all(chapters_to_add)
                db.session.flush()
                chapters_to_add = []
        
        # 提交剩余的章节
        if chapters_to_add:
            db.session.add_all(chapters_to_add)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'chapters_saved': len(chapters),
            'message': f'成功保存 {len(chapters)} 个章节到小说《{novel.title}》'
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"保存章节出错: {error_details}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/preview-translation', methods=['POST'], endpoint='preview_translation')
@admin_required
def preview_translation():
    """预览翻译效果"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的数据'})
        
        analysis_id = data.get('analysis_id')
        if not analysis_id:
            return jsonify({'success': False, 'error': '缺少分析ID'})
        
        # 读取解析数据
        temp_json_path = os.path.join(app.config['UPLOAD_FOLDER'], f"analysis_{analysis_id}.json")
        if not os.path.exists(temp_json_path):
            return jsonify({'success': False, 'error': '解析数据已过期，请重新解析文件'})
        
        with open(temp_json_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
        
        novel_info = analysis_data['novel_info']
        
        # 模拟翻译预览结果（实际应该调用翻译服务）
        # 这里提供一个简化的示例响应
        preview_result = {
            'translated_title': f"Crossing Over: Defying Fate for Immortality",
            'translated_description': "This book has a fast pace, no nonsense, the protagonist is both righteous and evil, absolutely a thrilling story [Hot-blooded fantasy comedy humorous development transmigration rebirth infinite flow] Yang Lingchen transmigrated to another world. At the beginning, he picked up an absolutely beautiful woman...",
            'preview_chapters': [
                {
                    'original_title': chapter['title'],
                    'translated_title': f"Chapter {i+1}: {chapter['title'].replace('第', 'Chapter ').replace('章', '')}",
                    'original_content_preview': chapter['content'][:200] + '...' if len(chapter['content']) > 200 else chapter['content'],
                    'translated_content_preview': f"On the Tianwu Continent, in the Taicang Mountain Range, beside a secluded pond... [Translated content preview]",
                    'cost': 0.05 + i * 0.01,  # 示例成本
                    'quality_score': 0.9 - i * 0.02  # 示例质量分数
                }
                for i, chapter in enumerate(novel_info['chapters'][:3])  # 前3章
            ],
            'terminology_mapping': {
                '杨凌晨': 'Yang Lingchen',
                '东方云冰': 'Dongfang Yunbing', 
                '天武大陆': 'Tianwu Continent',
                '太仓山脉': 'Taicang Mountain Range'
            },
            'preview_cost': 0.18,
            'estimated_full_cost': len(novel_info['chapters']) * 0.06
        }
        
        return jsonify({
            'success': True,
            'data': preview_result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


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