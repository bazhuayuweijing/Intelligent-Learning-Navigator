"""数据库模型 - 用户、测评、资源、路径、辅导记录"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), default='👤')
    bio = db.Column(db.String(200), default='')
    is_admin = db.Column(db.Boolean, default=False)
    is_teacher = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    assessments = db.relationship('Assessment', backref='user', lazy=True, cascade='all,delete')
    resources = db.relationship('ResourceHistory', backref='user', lazy=True, cascade='all,delete')
    paths = db.relationship('LearningPath', backref='user', lazy=True, cascade='all,delete')
    tutor_sessions = db.relationship('TutorSession', backref='user', lazy=True, cascade='all,delete')
    evaluations = db.relationship('Evaluation', backref='user', lazy=True, cascade='all,delete')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Assessment(db.Model):
    """测评记录"""
    __tablename__ = 'assessments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    total_score = db.Column(db.Integer)
    level_id = db.Column(db.Integer)
    level_name = db.Column(db.String(20))
    dimension_scores = db.Column(db.Text)  # JSON
    answers = db.Column(db.Text)  # JSON
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ResourceHistory(db.Model):
    """已生成的资源记录"""
    __tablename__ = 'resource_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50))
    resource_type = db.Column(db.String(50))
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    source = db.Column(db.String(100))
    level = db.Column(db.String(20))
    level_id = db.Column(db.Integer)
    tags = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LearningPath(db.Model):
    """学习路径"""
    __tablename__ = 'learning_paths'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50))
    path_data = db.Column(db.Text)  # JSON
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TutorSession(db.Model):
    """辅导对话"""
    __tablename__ = 'tutor_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50))
    question = db.Column(db.Text)
    answer = db.Column(db.Text)
    level_id = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Evaluation(db.Model):
    """学习效果评估"""
    __tablename__ = 'evaluations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50))
    overall_score = db.Column(db.Integer)
    dimension_scores = db.Column(db.Text)  # JSON
    feedback = db.Column(db.Text)
    suggested_action = db.Column(db.String(20))
    previous_level = db.Column(db.Integer)
    new_level = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LearningBehavior(db.Model):
    """学习行为轨迹 - 实时记录学生各类学习行为"""
    __tablename__ = 'learning_behaviors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50))
    behavior_type = db.Column(db.String(50))  # watch_video, do_exercise, read_resource, ask_question, generate_resource
    resource_type = db.Column(db.String(50))  # video, book, paper, quiz, document, mindmap, case, multimedia
    resource_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text)  # JSON 详细数据
    score = db.Column(db.Float, nullable=True)  # 如果有分数
    time_spent = db.Column(db.Integer, nullable=True)  # 停留/学习时长(秒)
    completion = db.Column(db.Float, nullable=True)  # 完成度 0-100
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('learning_behaviors', lazy=True))


class EvaluationReport(db.Model):
    """AI评估报告 - LLM生成的多维度评估结果"""
    __tablename__ = 'evaluation_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50))
    report_type = db.Column(db.String(30), default='full')  # full, quick, weekly
    
    # 核心评分
    overall_score = db.Column(db.Float)
    dimension_scores = db.Column(db.Text)  # JSON
    confidence = db.Column(db.Float, default=0.0)  # 评估置信度 0-1
    
    # LLM生成内容
    summary = db.Column(db.Text)  # 评估摘要
    strengths = db.Column(db.Text)  # JSON array
    weaknesses = db.Column(db.Text)  # JSON array
    recommendations = db.Column(db.Text)  # JSON array
    
    # 动态调整
    suggested_action = db.Column(db.String(20))  # upgrade, stay, consolidate, customize
    from_level = db.Column(db.Integer)
    to_level = db.Column(db.Integer)
    plan_adjustments = db.Column(db.Text)  # JSON - 学习计划调整建议
    resource_adjustments = db.Column(db.Text)  # JSON - 资源推送调整
    
    # 审核标记
    is_reviewed = db.Column(db.Boolean, default=False)
    review_notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('evaluation_reports', lazy=True))


class LearningPlan(db.Model):
    """动态学习计划 - 个性化学习方案，随评估动态调整"""
    __tablename__ = 'learning_plans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50))
    
    # 当前状态
    is_active = db.Column(db.Boolean, default=True)
    current_level = db.Column(db.Integer)
    target_level = db.Column(db.Integer)
    
    # 计划内容
    plan_data = db.Column(db.Text)  # JSON - 完整计划
    week_goals = db.Column(db.Text)  # JSON - 周目标
    daily_tasks = db.Column(db.Text)  # JSON - 每日任务
    resource_strategy = db.Column(db.Text)  # JSON - 资源推送策略
    
    # 动态调整记录
    adjustment_log = db.Column(db.Text)  # JSON array
    last_evaluation_id = db.Column(db.Integer, db.ForeignKey('evaluation_reports.id'), nullable=True)
    
    # 跨Agent协作反馈回路 - 记录评估建议与实际验证效果的闭环数据
    # 格式: JSON数组，每项包含:
    # {
    #   "evaluation_id": 评估报告ID,
    #   "suggestion": "upgrade"|"downgrade"|"maintain",  // 评估建议
    #   "suggested_level": 建议等级,
    #   "suggested_at": 建议时间,
    #   "verify_at": 验证时间(可为null),
    #   "verify_score": 验证得分(可为null),
    #   "verify_level": 验证后等级(可为null),
    #   "effect": null|"improved"|"declined"|"stable",  // 效果评估
    #   "days_to_verify": 建议到验证的天数(可为null)
    # }
    feedback_loop = db.Column(db.Text)  # JSON array
    
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('learning_plans', lazy=True))


class ContentSafetyLog(db.Model):
    """内容安全审核日志"""
    __tablename__ = 'content_safety_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content_type = db.Column(db.String(50))  # evaluation, resource, tutor_response
    content_preview = db.Column(db.String(200))
    check_result = db.Column(db.String(20))  # pass, flag, reject
    risk_type = db.Column(db.String(50), nullable=True)  # factual_error, sensitive, hallucination
    risk_detail = db.Column(db.Text)
    passed = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AsyncTask(db.Model):
    """异步任务 - 进度追踪"""
    __tablename__ = 'async_tasks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_type = db.Column(db.String(50))  # evaluate, generate_resource, analyze_progress
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    progress = db.Column(db.Float, default=0.0)  # 0-100
    stage = db.Column(db.String(50), default='')  # 当前阶段描述
    result = db.Column(db.Text, nullable=True)  # JSON
    error = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)


class ProfileConversation(db.Model):
    """对话式画像构建记录"""
    __tablename__ = 'profile_conversations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stage = db.Column(db.String(30), default='greeting')
    profile_data = db.Column(db.Text)  # JSON
    conversation = db.Column(db.Text)  # JSON array
    is_complete = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('profile_chats', lazy=True))

class GeneratedResource(db.Model):
    """AI生成的多模态学习资源"""
    __tablename__ = 'generated_resources'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50))
    resource_type = db.Column(db.String(30))  # document, mindmap, quiz, case, multimedia
    title = db.Column(db.String(200))
    content = db.Column(db.Text)  # JSON
    context = db.Column(db.Text)  # JSON - 生成时的上下文
    is_favorite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('generated_resources', lazy=True))

class WrongQuestion(db.Model):
    """错题记录 - 记录学生答错的题目，关联知识点用于复习推送"""
    __tablename__ = 'wrong_questions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    question = db.Column(db.Text, nullable=False)  # 题目内容
    correct_answer = db.Column(db.Text)  # 正确答案
    user_answer = db.Column(db.Text)  # 学生答案
    question_type = db.Column(db.String(30), default='choice')  # choice, fill, essay, trap
    knowledge_point = db.Column(db.String(200))  # 关联的知识点名称
    difficulty = db.Column(db.String(20), default='medium')  # easy, medium, hard
    source = db.Column(db.String(50), default='assessment')  # assessment, trap_exam, quiz
    is_mastered = db.Column(db.Boolean, default=False)  # 是否已掌握（复习后标记）
    mastered_at = db.Column(db.DateTime, nullable=True)  # 掌握时间
    review_count = db.Column(db.Integer, default=0)  # 复习次数
    last_review_time = db.Column(db.DateTime, nullable=True)  # 最后复习时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('wrong_questions', lazy=True))


class KnowledgePoint(db.Model):
    """知识点学习记录 - 用于记忆温度计功能"""
    __tablename__ = 'knowledge_points'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(200), nullable=False)  # 知识点名称
    mastery_level = db.Column(db.Float, default=0.5)  # 掌握程度 0-1，默认0.5
    last_study_time = db.Column(db.DateTime, default=datetime.utcnow)  # 最后学习时间
    study_count = db.Column(db.Integer, default=1)  # 学习次数
    last_remind_date = db.Column(db.Date, nullable=True)  # 上次提醒日期（用于去重）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('knowledge_points', lazy=True))
    
    def update_mastery(self, new_score):
        """更新掌握程度，取平均值"""
        self.mastery_level = (self.mastery_level * self.study_count + new_score) / (self.study_count + 1)
        self.study_count += 1
        self.last_study_time = datetime.utcnow()

def init_db(app):
    """初始化数据库"""
    with app.app_context():
        import os
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_path.startswith('sqlite:///'):
            db_dir = os.path.dirname(db_path.replace('sqlite:///', ''))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
        db.init_app(app)
        db.create_all()
        
        # 迁移：为已有表添加 is_admin / is_teacher 列
        inspector = db.inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns('users')]
        if 'is_admin' not in cols:
            db.session.execute(db.text('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0'))
            db.session.commit()
        if 'is_teacher' not in cols:
            db.session.execute(db.text('ALTER TABLE users ADD COLUMN is_teacher BOOLEAN DEFAULT 0'))
            db.session.commit()
        
        # 迁移：为 tutor_sessions 添加 is_active 列（如有旧表）
        tables = inspector.get_table_names()
        if 'tutor_sessions' in tables:
            ts_cols = [c['name'] for c in inspector.get_columns('tutor_sessions')]
            if 'is_active' not in ts_cols:
                try:
                    db.session.execute(db.text('ALTER TABLE tutor_sessions ADD COLUMN is_active BOOLEAN DEFAULT 1'))
                    db.session.execute(db.text('ALTER TABLE tutor_sessions ADD COLUMN level_id INTEGER DEFAULT 1'))
                    db.session.commit()
                except Exception:
                    db.session.rollback()

        # 创建默认管理员账号
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', is_admin=True)
            admin.set_password('admin123456')
            db.session.add(admin)
            db.session.commit()
        elif not admin.is_admin:
            admin.is_admin = True
            db.session.commit()
        
        # 创建默认教师账号
        teacher = User.query.filter_by(username='teacher').first()
        if not teacher:
            teacher = User(username='teacher', is_teacher=True, avatar='👨‍🏫')
            teacher.set_password('teacher123')
            db.session.add(teacher)
            db.session.commit()
        elif not teacher.is_teacher:
            teacher.is_teacher = True
            db.session.commit()
        
        # 创建示例用户（不同学科和程度阶段）
        sample_users = [
            # 计算机科学 - 各阶段
            {'username': 'cs_basic', 'password': '123456', 'bio': '计算机科学专业大一新生，零基础入门', 'avatar': '💻', 'subject': 'computer_science', 'level': 1},
            {'username': 'cs_intermediate', 'password': '123456', 'bio': '计算机科学大二学生，有一定编程基础', 'avatar': '📚', 'subject': 'computer_science', 'level': 3},
            {'username': 'cs_advanced', 'password': '123456', 'bio': '计算机科学大三学生，想深入学习AI', 'avatar': '🤖', 'subject': 'computer_science', 'level': 5},
            {'username': 'cs_expert', 'password': '123456', 'bio': '计算机科学研究生，专业水平', 'avatar': '🏆', 'subject': 'computer_science', 'level': 6},
            
            # 数学 - 各阶段
            {'username': 'math_basic', 'password': '123456', 'bio': '数学系大一新生，刚学微积分', 'avatar': '📐', 'subject': 'math', 'level': 1},
            {'username': 'math_intermediate', 'password': '123456', 'bio': '数学系大二学生，学习线性代数和概率论', 'avatar': '📊', 'subject': 'math', 'level': 3},
            {'username': 'math_advanced', 'password': '123456', 'bio': '数学系大三学生，专攻微分方程', 'avatar': '🔢', 'subject': 'math', 'level': 5},
            
            # 物理 - 各阶段
            {'username': 'physics_basic', 'password': '123456', 'bio': '物理系大一新生，学习力学', 'avatar': '⚛️', 'subject': 'physics', 'level': 1},
            {'username': 'physics_intermediate', 'password': '123456', 'bio': '物理系大二学生，学习电磁学', 'avatar': '🔌', 'subject': 'physics', 'level': 3},
            
            # 人工智能
            {'username': 'ai_basic', 'password': '123456', 'bio': 'AI入门学习者，对机器学习感兴趣', 'avatar': '🧠', 'subject': 'ai', 'level': 2},
            {'username': 'ai_advanced', 'password': '123456', 'bio': 'AI研究者，深入研究深度学习', 'avatar': '🚀', 'subject': 'ai', 'level': 5},
            
            # 英语
            {'username': 'english_basic', 'password': '123456', 'bio': '英语初学者，准备四六级考试', 'avatar': '🌍', 'subject': 'english', 'level': 1},
            {'username': 'english_intermediate', 'password': '123456', 'bio': '英语学习者，备考雅思', 'avatar': '📝', 'subject': 'english', 'level': 3},
            
            # 软件工程
            {'username': 'se_basic', 'password': '123456', 'bio': '软件工程专业大一学生', 'avatar': '🛠️', 'subject': 'software_engineering', 'level': 1},
            {'username': 'se_advanced', 'password': '123456', 'bio': '软件工程师，多年开发经验', 'avatar': '💼', 'subject': 'software_engineering', 'level': 5},
        ]
        
        for user_data in sample_users:
            user = User.query.filter_by(username=user_data['username']).first()
            if not user:
                user = User(
                    username=user_data['username'],
                    bio=user_data['bio'],
                    avatar=user_data['avatar']
                )
                user.set_password(user_data['password'])
                db.session.add(user)
                db.session.flush()
            
            subject = user_data.get('subject')
            level = user_data.get('level', 1)
            if subject and not Assessment.query.filter_by(user_id=user.id, subject=subject).first():
                assessment = Assessment(
                    user_id=user.id,
                    subject=subject,
                    total_score=level * 15 + 20,
                    level_id=level,
                    level_name=f'Level {level}',
                    dimension_scores='{"knowledge": 60, "skill": 55, "application": 50}',
                    answers='[]',
                    feedback=f'{user.username} 的 {subject} 测评完成'
                )
                db.session.add(assessment)
            
            behavior_types = ['watch_video', 'do_exercise', 'read_resource', 'generate_resource']
            resource_types = ['video', 'quiz', 'document', 'mindmap']
            for i, (bt, rt) in enumerate(zip(behavior_types, resource_types)):
                if not LearningBehavior.query.filter_by(user_id=user.id, behavior_type=bt, subject=subject).first():
                    behavior = LearningBehavior(
                        user_id=user.id,
                        subject=subject,
                        behavior_type=bt,
                        resource_type=rt,
                        detail=f'{{"topic": "知识点{i+1}", "action": "{bt}"}}',
                        score=60 + i * 5 if bt == 'do_exercise' else None,
                        time_spent=300 + i * 60,
                        completion=60 + i * 10
                    )
                    db.session.add(behavior)
        
        if not User.query.filter_by(username='test').first():
            u = User(username='test', bio='测试用户', avatar='👤')
            u.set_password('123456')
            db.session.add(u)
            db.session.flush()
            
            for subject in ['computer_science', 'math', 'physics']:
                assessment = Assessment(
                    user_id=u.id,
                    subject=subject,
                    total_score=50,
                    level_id=2,
                    level_name='Level 2',
                    dimension_scores='{"knowledge": 50, "skill": 45, "application": 40}',
                    answers='[]',
                    feedback=f'{u.username} 的 {subject} 测评完成'
                )
                db.session.add(assessment)
                
                for i, (bt, rt) in enumerate(zip(['watch_video', 'do_exercise', 'read_resource'], ['video', 'quiz', 'document'])):
                    behavior = LearningBehavior(
                        user_id=u.id,
                        subject=subject,
                        behavior_type=bt,
                        resource_type=rt,
                        detail=f'{{"topic": "{subject}知识点{i+1}", "action": "{bt}"}}',
                        score=55 + i * 5 if bt == 'do_exercise' else None,
                        time_spent=240 + i * 45,
                        completion=55 + i * 8
                    )
                    db.session.add(behavior)
        
        db.session.commit()
