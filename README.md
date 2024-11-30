# 事件提醒工具

用户输入自己关注的各种事件，设定提醒规则，系统会根据配置的提醒时间规则进行邮箱通知

## 功能特点

- 事件管理
- 邮箱通知

## 安装说明

1. 确保已安装Python 3.10或更高版本
2. 安装依赖包：

```bash
pip install -r requirements.txt
```

## 使用说明

1. 复制.env.example为.env,输入正确的smtp配置

```angular2html
DEBUG=false
SMTP_SERVER=smtp.xxx.com
SMTP_PORT=465
SMTP_USER=admin@123.top
SMTP_PASSWORD=123456
```

2. 运行应用

```bash
python app.py
```

3. 在浏览器中访问 http://localhost:5000
4. 添加事件
5. 设定通知配置
6. 系统会按照通知规则自动邮箱通知

## 截图展示

![](example.jpg)
