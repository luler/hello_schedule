from datetime import datetime


# 获取当前时间
def now_time_format():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# 打印字符串，前面自动增加时间
def print_log(msg):
    print(now_time_format() + ' ' + msg)
