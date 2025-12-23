from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pandas as pd
import os
from datetime import datetime, timedelta

import face_recognition

app = Flask(__name__)
app.secret_key = 'super_secret_9832!@#XYZ'

USER = {'username': 'manish', 'password': 'manish123'}

periods = [
    "1ST PERIOD (9:00-10:00)", "2ND PERIOD (10:00-11:00)", "3RD PERIOD (11:00-12:00)",
    "4TH PERIOD (12:00-1:00)", "LUNCH BREAK (2:00-3:00)",
    "5TH PERIOD (3:00-4:00)", "6TH PERIOD (4:00-5:00)", "7TH PERIOD (5:00-6:00)"
]
hour_to_period = {9:0, 10:1, 11:2, 12:3, 14:5, 15:5, 16:6, 17:7}

@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    error = ""
    if request.method == 'POST':
        if request.form['username'] == USER['username'] and request.form['password'] == USER['password']:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    reg_result = att_result = ""
    students = os.listdir('faces') if os.path.exists('faces') else []
    if 'reg_submit' in request.form:
        name = request.form.get('student_name', '').strip()
        file = request.files.get('face_file')
        if name and file and allowed_file(file.filename):
            folder = os.path.join('faces', name)
            os.makedirs(folder, exist_ok=True)
            file.save(os.path.join(folder, file.filename))
            reg_result = f"Registered {name}!"
            students = os.listdir('faces') if os.path.exists('faces') else []
        else:
            reg_result = "Name and image required."
    if 'att_submit' in request.form:
        file = request.files.get('attendance_file')
        if file and allowed_file(file.filename):
            matched_name = recognize_face(file)
            if matched_name:
                att_result = mark_attendance(matched_name)
            else:
                att_result = "Face not recognized—not marked."
        else:
            att_result = "Please upload an image."
    return render_template('dashboard.html',
                           reg_result=reg_result, att_result=att_result, students=students)

@app.route('/attendance_table')
def attendance_table_page():
    return render_template('attendance_table.html', table_html=get_attendance_table())

@app.route('/download_csv')
def download_csv():
    return send_file('attendance.csv', as_attachment=True, download_name='attendance.csv')

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in {'jpg', 'jpeg', 'png'}

def recognize_face(uploaded_file):
    # Save uploaded file temporarily
    temp_path = "temp_uploaded.jpg"
    uploaded_file.save(temp_path)
    unknown_image = face_recognition.load_image_file(temp_path)
    unknown_encodings = face_recognition.face_encodings(unknown_image)
    if not unknown_encodings:
        try: os.remove(temp_path)
        except: pass
        return None
    unknown_encoding = unknown_encodings[0]
    faces_dir = 'faces'
    if not os.path.exists(faces_dir):
        try: os.remove(temp_path)
        except: pass
        return None
    for student in os.listdir(faces_dir):
        student_dir = os.path.join(faces_dir, student)
        if not os.path.isdir(student_dir):
            continue
        for fname in os.listdir(student_dir):
            if not (fname.lower().endswith('.jpg') or fname.lower().endswith('.jpeg') or fname.lower().endswith('.png')):
                continue
            known_image = face_recognition.load_image_file(os.path.join(student_dir, fname))
            known_encodings = face_recognition.face_encodings(known_image)
            if not known_encodings:
                continue
            result = face_recognition.compare_faces([known_encodings[0]], unknown_encoding, tolerance=0.5)
            if result[0]:
                try: os.remove(temp_path)
                except: pass
                return student
    try: os.remove(temp_path)
    except: pass
    return None



def mark_attendance(name):
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)  # Now in IST
    today = now.strftime('%Y-%m-%d')
    hour = now.hour
    if hour == 14:
        return "It's Lunch Break right now (2:00-3:00)!"
    period_idx = hour_to_period.get(hour, None)
    if period_idx is None or period_idx >= len(periods):
        return "Attendance only between 9AM-1PM, 3PM-6PM (no attendance 1-3PM)."
    period_col = periods[period_idx]
    if os.path.exists('attendance.csv'):
        df = pd.read_csv('attendance.csv')
        for col in ["Name", "Date"] + periods:
            if col not in df.columns:
                df[col] = ""
    else:
        df = pd.DataFrame(columns=["Name", "Date"] + periods)
    mask = (df["Name"] == name) & (df["Date"] == today)
    if not mask.any():
        row = [name, today] + ['Absent'] * len(periods)
        df.loc[len(df)] = row
        mask = (df["Name"] == name) & (df["Date"] == today)
    df.loc[mask, period_col] = "Present"
    df.to_csv('attendance.csv', index=False)
    return f"{name} marked Present for {period_col}"


def get_attendance_table():
    if not os.path.exists('attendance.csv'):
        return "<p>No attendance records yet.</p>"
    df = pd.read_csv('attendance.csv')
    df.columns = [col.upper() for col in df.columns]
    return df.to_html(index=False, classes="table table-striped table-bordered att-table", border=0)

if __name__ == "__main__":
    app.run(debug=True)
