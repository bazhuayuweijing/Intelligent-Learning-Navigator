"""蓝图包初始化"""
from flask import Flask

def register_blueprints(app: Flask):
    """注册所有蓝图到应用"""
    from routes.evaluate_bp import evaluate_bp
    from routes.tutor_bp import tutor_bp
    from routes.admin_bp import admin_bp
    from routes.teacher_bp import teacher_bp
    
    app.register_blueprint(evaluate_bp)
    app.register_blueprint(tutor_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
