import os
import smtplib
from datetime import datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

# 加载.env文件
load_dotenv()

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

DEBUG = os.getenv("DEBUG", 'false').lower() in ['true', '1', 't', 'y', 'yes', 'on']

# 从环境变量读取邮件配置
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    expiry_date = db.Column(db.DateTime, nullable=False)
    reminder_days = db.Column(db.Integer, nullable=False)  # 提前多少天开始提醒
    reminder_minutes = db.Column(db.Integer, nullable=False, default=0)  # 提前分钟数
    reminder_frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly
    email = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    open_id = db.Column(db.String(50), nullable=False, default='')
    created_at = db.Column(db.DateTime, default=datetime.now())
    last_reminder_id = db.Column(db.String(50))  # 最后一次发送的提醒邮件ID

    @property
    def remaining_time(self):
        """计算距离到期还有多长时间"""
        now = datetime.now()
        expiry = self.expiry_date
        if now > expiry:
            return None
        delta = expiry - now
        days = delta.days
        hours = (delta.seconds) // 3600
        minutes = (delta.seconds % 3600) // 60
        return {'days': days, 'hours': hours, 'minutes': minutes}


def generate_reminder_id(event_id):
    """生成提醒邮件的唯一标识符"""
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    return f"{timestamp}-{event_id}"


def send_email(to_email, subject, content, reminder_id):
    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = f"事件提醒工具 <{SMTP_USER}>"
        msg['To'] = to_email
        msg['Message-ID'] = f"<{reminder_id}@schedule.system>"  # 添加邮件ID到头部

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"发送邮件失败: {str(e)}")
        return False


def should_send_reminder(event, current_time):
    """判断是否应该发送提醒"""
    if not event.is_active:
        return False

    # 如果已过期，不发送提醒
    if current_time > event.expiry_date:
        return False

    # 计算提醒时间
    reminder_delta = timedelta(
        days=event.reminder_days,
        minutes=event.reminder_minutes
    )
    time_until_expiry = event.expiry_date - current_time

    # 如果还没到提醒时间，不发送提醒
    if time_until_expiry > reminder_delta:
        return False

    # 根据不同的提醒频率判断是否需要发送提醒
    freq = event.reminder_frequency
    if freq == 'never':
        return False
    elif freq == 'every_minute':
        return True
    elif freq == 'every_5_minutes':
        return current_time.minute % 5 == 0
    elif freq == 'every_10_minutes':
        return current_time.minute % 10 == 0
    elif freq == 'every_15_minutes':
        return current_time.minute % 15 == 0
    elif freq == 'every_30_minutes':
        return current_time.minute % 30 == 0
    elif freq == 'hourly':
        return current_time.minute == 0
    elif freq == 'every_3_hours':
        return current_time.minute == 0 and current_time.hour % 3 == 0
    elif freq == 'every_6_hours':
        return current_time.minute == 0 and current_time.hour % 6 == 0
    elif freq == 'every_12_hours':
        return current_time.minute == 0 and current_time.hour % 12 == 0
    elif freq == 'daily':
        return current_time.minute == 0 and current_time.hour == 0
    elif freq == 'weekly':
        return current_time.minute == 0 and current_time.hour == 0 and current_time.weekday() == 0
    elif freq == 'monthly':
        return current_time.minute == 0 and current_time.hour == 0 and current_time.day == 1

    return False


def check_events():
    with app.app_context():
        current_time = datetime.now()
        events = Event.query.filter_by(is_active=True).all()

        for event in events:
            if current_time > event.expiry_date:
                event.is_active = False
                db.session.commit()
                continue

            reminder_id = generate_reminder_id(event.id)
            subject = f"事件提醒: {event.title} [ID: {reminder_id}]"
            if should_send_reminder(event, current_time):
                remaining = event.remaining_time
                content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=no, shrink-to-fit=no">
    <meta name="theme-color" content="#000000">
    <meta name="renderer" content="webkit">
    <meta name="google" content="notranslate">
    <meta name="format-detection" content="telephone=no">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>' . $subject . '</title>
</head>
<body>
<table>
<tr><td align="right" style="word-break: keep-all">距离到期还有：</td><td style="word-break: break-all">{remaining['days']}天{remaining['hours']}小时{remaining['minutes']}分钟</td></tr>
<tr><td align="right" style="word-break: keep-all">到期时间：</td><td style="word-break: break-all">{event.expiry_date.strftime('%Y-%m-%d %H:%M')}</td></tr>
</table>
</body>
</html>
"""
                send_result = send_email(event.email, subject, content, reminder_id)
                if send_result:
                    event.last_reminder_id = reminder_id
                    db.session.commit()
                print(f"{subject}，邮件发送结果: {'成功' if send_result else '失败'}")
            else:
                print(f"{subject}，当前不需要发送提醒")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/events', methods=['POST'])
def create_event():
    data = request.json
    try:
        expiry_date = datetime.strptime(data['expiry_date'], '%Y-%m-%d %H:%M')
        event = Event(
            title=data['title'],
            expiry_date=expiry_date,
            reminder_days=int(data['reminder_days']),
            reminder_minutes=int(data['reminder_minutes']),
            reminder_frequency=data['reminder_frequency'],
            open_id=data['open_id'],
            email=data['email']
        )
        db.session.add(event)
        db.session.commit()
        return jsonify({"message": "事件创建成功", "id": event.id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/events', methods=['GET'])
def get_events():
    # 从请求参数中获取 open_id，如果没有则默认为空字符串
    open_id = request.args.get('open_id', '')
    # 按到期时间升序排序
    events = Event.query.filter(Event.open_id == open_id).order_by(Event.expiry_date.asc()).all()
    return jsonify([{
        'id': event.id,
        'title': event.title,
        'expiry_date': event.expiry_date.strftime('%Y-%m-%d %H:%M'),
        'reminder_days': event.reminder_days,
        'reminder_minutes': event.reminder_minutes,
        'reminder_frequency': event.reminder_frequency,
        'email': event.email,
        'is_active': event.is_active,
        'open_id': event.open_id,
        'remaining_time': event.remaining_time,
        'last_reminder_id': event.last_reminder_id
    } for event in events])


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return jsonify({"message": "事件已删除"}), 200


@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    event = Event.query.get_or_404(event_id)
    return jsonify({
        'id': event.id,
        'title': event.title,
        'expiry_date': event.expiry_date.strftime('%Y-%m-%d %H:%M'),
        'reminder_days': event.reminder_days,
        'reminder_minutes': event.reminder_minutes,
        'reminder_frequency': event.reminder_frequency,
        'email': event.email,
        'is_active': event.is_active,
        'open_id': event.open_id,
        'remaining_time': event.remaining_time,
        'last_reminder_id': event.last_reminder_id
    }), 200


@app.route('/api/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    event = Event.query.get_or_404(event_id)
    data = request.json

    try:
        if 'title' in data:
            event.title = data['title']
        if 'expiry_date' in data:
            expiry_date = datetime.strptime(data['expiry_date'], '%Y-%m-%d %H:%M')
            print(expiry_date)
            event.expiry_date = expiry_date
        if 'reminder_days' in data:
            event.reminder_days = int(data['reminder_days'])
        if 'reminder_minutes' in data:
            event.reminder_minutes = int(data['reminder_minutes'])
        if 'reminder_frequency' in data:
            event.reminder_frequency = data['reminder_frequency']
        if 'email' in data:
            event.email = data['email']
        if 'is_active' in data:
            event.is_active = bool(data['is_active'])

        db.session.commit()
        return jsonify({"message": "事件更新成功"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_events,
        CronTrigger(minute='*'),  # 每分钟检查一次
        id='check_events',
        replace_existing=True
    )
    scheduler.start()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':  # 判断是否是主进程
        init_scheduler()
    app.run(debug=DEBUG, host='0.0.0.0', port=5000)
