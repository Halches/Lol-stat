"""Проверки ручных настроек без UI."""
import re


def clock_seconds(text, positive=False):
    match=re.fullmatch(r'\s*(\d{1,3}):([0-5]\d)\s*',text)
    if not match:raise ValueError('Нужно ММ:СС')
    result=int(match[1])*60+int(match[2])
    if positive and result==0:raise ValueError('Интервал должен быть положительным')
    return result
