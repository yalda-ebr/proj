from flask import Flask, render_template, request, redirect, url_for, session
from models.user import User
from models.course import Course
from models.enrollment import Enrollment
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ------------------ صفحه اصلی ------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

# ------------------ ثبت‌نام ------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'student')

        if User.find_by_email(email):
            return "⚠️ ایمیل تکراری است."

        user = User(name, email, password, role)
        user.save()
        return redirect(url_for('login'))

    return render_template('register.html')

# ------------------ ورود ------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.authenticate(email, password)

        if user:
            session['user'] = {
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='ایمیل یا رمز عبور اشتباه است.')

    return render_template('login.html')

# ------------------ هدایت به داشبورد مناسب ------------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    role = session['user']['role']
    if role == 'student':
        return redirect(url_for('student_dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return "نقش نامعتبر!"

# ------------------ داشبورد دانشجو ------------------
@app.route('/dashboard/student')
def student_dashboard():
    if 'user' not in session or session['user']['role'] != 'student':
        return redirect(url_for('login'))

    courses = Course.load_all()
    enrolled = Enrollment.get_user_courses(session['user']['email'])

    return render_template('student_dashboard.html', courses=courses, enrolled=enrolled, user=session['user'])

# ------------------ داشبورد مدیر ------------------
@app.route('/dashboard/admin')
def admin_dashboard():
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect(url_for('login'))

    courses = Course.load_all()
    users = User.load_all()
    enrollments = []

    for record in Enrollment.load_all():
        user_info = User.find_by_email(record['user'])
        course_info = Course.find_by_code(record['course'])
        if user_info and course_info:
            enrollments.append({
                'student_name': user_info.name,
                'student_email': user_info.email,
                'course_name': course_info['name']
            })

    return render_template('admin_dashboard.html', courses=courses, users=users, enrollments=enrollments, user=session['user'])

# ------------------ حذف کاربر ------------------
@app.route('/delete_user/<email>', methods=['POST'])
def delete_user(email):
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect(url_for('login'))

    if session['user']['email'] == email:
        return "❌ نمی‌توان حساب مدیر فعلی را حذف کرد."

    User.delete_by_email(email)
    return redirect(url_for('admin_dashboard'))

# ------------------ افزودن دوره ------------------
@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        capacity = int(request.form['capacity'])
        schedule_input = request.form['schedule']
        schedule = [s.strip() for s in schedule_input.split(',') if s.strip()]

        prerequisites_input = request.form.get('prerequisites', '').strip()
        prerequisites = [p.strip() for p in prerequisites_input.split(',')] if prerequisites_input else []

        if Course.find_by_code(code):
            return "⚠️ کد دوره تکراری است."

        new_course = Course(code, name, capacity, schedule, prerequisites)
        new_course.save()
        return redirect(url_for('admin_dashboard'))

    return render_template('add_course.html', user=session['user'])

# ------------------ ثبت‌نام در دوره ------------------
@app.route('/enroll/<code>')
def enroll(code):
    if 'user' not in session or session['user']['role'] != 'student':
        return redirect(url_for('login'))

    user_email = session['user']['email']
    course = Course.find_by_code(code)

    if not course:
        return "⚠️ دوره یافت نشد."

    if Enrollment.is_already_enrolled(user_email, code):
        return "⚠️ قبلاً در این دوره ثبت‌نام کرده‌اید."

    if Enrollment.count_enrolled(code) >= course['capacity']:
        return "⚠️ ظرفیت دوره پر است."

    prerequisites = course['prerequisites'] or []
    user_courses = Enrollment.get_user_courses(user_email)
    for pre in prerequisites:
        if pre not in user_courses:
            return f"⚠️ برای ثبت‌نام نیاز به گذراندن پیش‌نیاز {pre} دارید."

    if Enrollment.is_time_conflict(user_email, course['schedule']):
        return "⚠️ تداخل زمانی با دوره دیگر دارید."

    Enrollment.enroll(user_email, code)
    return redirect(url_for('my_courses'))

# ------------------ مشاهده دوره‌های دانشجو ------------------
@app.route('/my_courses')
def my_courses():
    if 'user' not in session or session['user']['role'] != 'student':
        return redirect(url_for('login'))

    user_email = session['user']['email']
    enrolled_codes = Enrollment.get_user_courses(user_email)
    all_courses = Course.load_all()
    student_courses = [course for course in all_courses if course['code'] in enrolled_codes]

    return render_template('student_courses.html', courses=student_courses, user=session['user'])

# ------------------ پروفایل ------------------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = User.find_by_email(session['user']['email'])

    if not user:
        return "⚠️ کاربر یافت نشد."

    if request.method == 'POST':
        new_name = request.form['name'].strip()
        new_password = request.form['password'].strip()

        if not new_name:
            return render_template('profile.html', user=user, error='⚠️ لطفاً نام را وارد کنید.')

        user.update_profile(new_name, new_password if new_password else None)
        session['user']['name'] = user.name
        return render_template('profile.html', user=user, message='✅ تغییرات با موفقیت ذخیره شد.')

    return render_template('profile.html', user=user)

# ------------------ خروج از حساب ------------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# ------------------ اجرای برنامه ------------------
if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    app.run(debug=True)
