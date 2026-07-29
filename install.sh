#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "تحديث الحزم..."
pkg update -y
echo "تثبيت Python..."
pkg install python -y
echo "تثبيت المكتبات..."
pip install --upgrade pip
pip install flask routeros-api
echo
echo "تم التثبيت بنجاح."
echo "شغّل اللوحة بالأمر:"
echo "python app.py"
