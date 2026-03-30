#!/usr/bin/env bash
# OwnerConnect - سكريبت تشغيل سريع
# الاستخدام: ./dev.sh [start|stop|check|shell|migrate]

VENV_PYTHON=".venv/bin/python"
MANAGE="$VENV_PYTHON manage.py"
PID_FILE=".dev_server.pid"

case "$1" in
  start)
    echo "🚀 تشغيل السيرفر..."
    nohup $MANAGE runserver 0.0.0.0:8000 > dev_server.log 2>&1 &
    echo $! > $PID_FILE
    sleep 2
    echo "✅ السيرفر شغّال على http://localhost:8000"
    echo "   PID: $(cat $PID_FILE) | اللوقات: dev_server.log"
    ;;
  stop)
    if [ -f $PID_FILE ]; then
      kill $(cat $PID_FILE) 2>/dev/null && echo "🛑 السيرفر اتوقف"
      rm $PID_FILE
    else
      pkill -f "manage.py runserver" && echo "🛑 السيرفر اتوقف" || echo "مفيش سيرفر شغّال"
    fi
    ;;
  check)
    echo "🔍 فحص المشروع..."
    $MANAGE check && echo "✅ المشروع OK"
    ;;
  shell)
    $MANAGE shell
    ;;
  migrate)
    $MANAGE migrate
    ;;
  makemigrations)
    $MANAGE makemigrations
    ;;
  logs)
    tail -f dev_server.log
    ;;
  *)
    echo "الاستخدام: ./dev.sh [start|stop|check|shell|migrate|makemigrations|logs]"
    ;;
esac
