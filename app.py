from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = "database.db"

# Secret key is required for Flask sessions
app.config["SECRET_KEY"] = "student-study-planner-secret-key"

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def get_db_connection():
     connection = sqlite3.connect(DATABASE)
     connection.row_factory = sqlite3.Row
     connection.execute("PRAGMA foreign_keys = ON")
     return connection

def create_database():
    connection = get_db_connection()
   


    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            student_id TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            course TEXT NOT NULL,
            semester TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_email
        ON users(email)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_student_id
        ON users(student_id)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_code TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            credits INTEGER NOT NULL,
            semester TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, subject_code)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS study_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            target_hours INTEGER NOT NULL,
            progress INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"].strip()
        student_id = request.form["student_id"].strip()
        email = request.form["email"].strip()
        course = request.form["course"].strip()
        semester = request.form["semester"].strip()

        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

                # Server-side validation
        if not full_name:
            return "Full name is required."

        if not student_id:
            return "Student ID is required."

        if not email:
            return "Email is required."

        if not course:
            return "Course is required."

        if not semester:
            return "Semester is required."

        if not password:
            return "Password is required."
        
        if password != confirm_password:
            return "Passwords do not match."

        if len(password) < 8:
            return "Password must contain at least 8 characters."

        if not any(char.isupper() for char in password):
            return "Password must contain at least one uppercase letter."

        if not any(char.islower() for char in password):
            return "Password must contain at least one lowercase letter."

        if not any(char.isdigit() for char in password):
            return "Password must contain at least one number."
        
        connection = get_db_connection()

        existing_email = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_email:
            connection.close()
            return "Email is already registered."

        existing_student = connection.execute(
            "SELECT id FROM users WHERE student_id = ?",
            (student_id,)
        ).fetchone()

        if existing_student:
            connection.close()
            return "Student ID is already registered."

        password_hash = generate_password_hash(password)

        connection.execute("""
            INSERT INTO users
            (
                full_name,
                student_id,
                email,
                course,
                semester,
                password_hash
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            full_name,
            student_id,
            email,
            course,
            semester,
            password_hash
        ))

        connection.commit()
        connection.close()

        return "Registration successful!"

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        connection.close()

        if user is None:
            return render_template(
                "login.html",
                error="Invalid email or password."
            )

        if not check_password_hash(user["password_hash"], password):
            return render_template(
                "login.html",
                error="Invalid email or password."
            )

        # Store logged-in user's ID in session
        session["user_id"] = user["id"]
        session["login_message"] = "Login successful. Welcome back!"

        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    user = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    connection.close()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template("dashboard.html", user=user)

@app.route("/planner")
def planner():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    sessions = connection.execute(
        """
        SELECT * FROM study_sessions
        WHERE user_id = ?
        ORDER BY date, time
        """,
        (session["user_id"],)
    ).fetchall()

    total_hours = connection.execute(
        """
        SELECT COALESCE(SUM(duration), 0)
        FROM study_sessions
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()[0]

    weekly_hours = connection.execute(
        """
        SELECT COALESCE(SUM(duration), 0)
        FROM study_sessions
        WHERE user_id = ?
        AND date >= date('now', 'weekday 0', '-6 days')
        AND date <= date('now', 'weekday 0')
        """,
        (session["user_id"],)
    ).fetchone()[0]

    completed_sessions = connection.execute(
    """
    SELECT COUNT(*)
    FROM study_sessions
    WHERE user_id = ?
    AND status = 'Completed'
    """,
    (session["user_id"],)
).fetchone()[0]
    connection.close()

    return render_template(
        "study-planner.html",
        sessions=sessions,
        total_hours=total_hours,
        weekly_hours=weekly_hours,
        completed_sessions=completed_sessions
    )
   
@app.route("/add-study", methods=["GET", "POST"])
def add_study():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        subject = request.form["subject"]
        topic = request.form["topic"]
        date = request.form["date"]
        time = request.form["time"]
        duration = request.form["duration"]

        connection = get_db_connection()

        connection.execute(
            """
            INSERT INTO study_sessions
            (user_id, subject, topic, date, time, duration, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                subject,
                topic,
                date,
                time,
                duration,
                "Pending"
            )
        )

        connection.commit()
        connection.close()

        return redirect(url_for("planner"))

    return render_template("add-study.html")

@app.route("/edit-study/<int:study_id>", methods=["GET", "POST"])
def edit_study(study_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    study = connection.execute(
        """
        SELECT * FROM study_sessions
        WHERE id = ? AND user_id = ?
        """,
        (study_id, session["user_id"])
    ).fetchone()

    if study is None:
        connection.close()
        return "Study session not found."

    if request.method == "POST":

        subject = request.form["subject"]
        topic = request.form["topic"]
        date = request.form["date"]
        time = request.form["time"]
        duration = request.form["duration"]

        connection.execute(
            """
            UPDATE study_sessions
            SET subject = ?, topic = ?, date = ?, time = ?, duration = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                subject,
                topic,
                date,
                time,
                duration,
                study_id,
                session["user_id"]
            )
        )

        connection.commit()
        connection.close()

        return redirect(url_for("planner"))

    connection.close()

    return render_template(
        "edit-study.html",
        study=study
    )

@app.route("/delete-study/<int:study_id>", methods=["POST"])
def delete_study(study_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    connection.execute(
        """
        DELETE FROM study_sessions
        WHERE id = ? AND user_id = ?
        """,
        (study_id, session["user_id"])
    )

    connection.commit()
    connection.close()

    return redirect(url_for("planner"))

@app.route("/complete-study/<int:study_id>", methods=["POST"])
def complete_study(study_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    connection.execute(
        """
        UPDATE study_sessions
        SET status = 'Completed'
        WHERE id = ? AND user_id = ?
        """,
        (study_id, session["user_id"])
    )

    connection.commit()
    connection.close()

    return redirect(url_for("planner"))
@app.route("/goals", methods=["GET", "POST"])
def goals():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    if request.method == "POST":

        title = request.form["title"].strip()
        description = request.form["description"].strip()
        target_hours = request.form["target_hours"]

        if not title or not description or not target_hours:
            goals = connection.execute(
                """
                SELECT * FROM study_goals
                WHERE user_id = ?
                ORDER BY id DESC
                """,
                (session["user_id"],)
            ).fetchall()

            connection.close()

            return render_template(
                "goals.html",
                goals=goals,
                error="All goal fields are required."
            )

        try:
            target_hours = int(target_hours)

            if target_hours <= 0:
                connection.close()
                return "Target study hours must be greater than 0."

            connection.execute(
                """
                INSERT INTO study_goals
                (user_id, title, description, target_hours, progress)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    title,
                    description,
                    target_hours,
                    0
                )
            )

            connection.commit()

        except ValueError:
            connection.close()
            return "Target study hours must be a valid number."

    goals = connection.execute(
        """
        SELECT * FROM study_goals
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "goals.html",
        goals=goals
    )

@app.route("/edit-goal/<int:goal_id>", methods=["GET", "POST"])
def edit_goal(goal_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    goal = connection.execute(
        """
        SELECT * FROM study_goals
        WHERE id = ? AND user_id = ?
        """,
        (goal_id, session["user_id"])
    ).fetchone()

    if goal is None:
        connection.close()
        return "Study goal not found."

    if request.method == "POST":

        title = request.form["title"].strip()
        description = request.form["description"].strip()
        target_hours = request.form["target_hours"]

        if not title or not description or not target_hours:
            connection.close()
            return "All goal fields are required."

        try:
            target_hours = int(target_hours)

            if target_hours <= 0:
                connection.close()
                return "Target study hours must be greater than 0."

            connection.execute(
                """
                UPDATE study_goals
                SET title = ?, description = ?, target_hours = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    title,
                    description,
                    target_hours,
                    goal_id,
                    session["user_id"]
                )
            )

            connection.commit()
            connection.close()

            return redirect(url_for("goals"))

        except ValueError:
            connection.close()
            return "Target study hours must be a valid number."

    connection.close()

    return render_template(
        "edit-goal.html",
        goal=goal
    )

@app.route("/update-goal-progress/<int:goal_id>", methods=["GET", "POST"])
def update_goal_progress(goal_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "update-progress.html",
            goal_id=goal_id
        )

    progress = request.form["progress"]

    try:
        progress = int(progress)

        if progress < 0 or progress > 100:
            return "Progress must be between 0 and 100."

    except ValueError:
        return "Progress must be a valid number."

    connection = get_db_connection()

    connection.execute(
        """
        UPDATE study_goals
        SET progress = ?
        WHERE id = ? AND user_id = ?
        """,
        (
            progress,
            goal_id,
            session["user_id"]
        )
    )

    connection.commit()
    connection.close()

    return redirect(url_for("goals"))
    return redirect(url_for("goals"))
@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    user = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    connection.close()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template("profile.html", user=user)


    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    study = connection.execute(
        """
        SELECT * FROM study_sessions
        WHERE id = ? AND user_id = ?
        """,
        (study_id, session["user_id"])
    ).fetchone()

    if study is None:
        connection.close()
        return "Study session not found."

    if request.method == "POST":

        subject = request.form["subject"]
        topic = request.form["topic"]
        date = request.form["date"]
        time = request.form["time"]
        duration = request.form["duration"]

        connection.execute(
            """
            UPDATE study_sessions
            SET subject = ?, topic = ?, date = ?, time = ?, duration = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                subject,
                topic,
                date,
                time,
                duration,
                study_id,
                session["user_id"]
            )
        )

        connection.commit()
        connection.close()

        return redirect(url_for("planner"))

    connection.close()

    return render_template(
        "edit-study.html",
        study=study
    )
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    user = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    connection.close()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template("profile.html", user=user)

@app.route("/subjects", methods=["GET", "POST"])
def subjects():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    if request.method == "POST":

        subject_code = request.form["subject_code"].strip()
        subject_name = request.form["subject_name"].strip()
        credits = request.form["credits"].strip()
        semester = request.form["semester"].strip()

        if not subject_code or not subject_name or not credits or not semester:

            subjects = connection.execute("""
                SELECT *
                FROM subjects
                WHERE user_id = ?
                ORDER BY semester, subject_code
            """, (session["user_id"],)).fetchall()

            connection.close()

            return render_template(
                "subjects.html",
                error="All subject fields are required.",
                subjects=subjects
            )

        try:
            credits = int(credits)

            if credits < 1 or credits > 4:

                subjects = connection.execute("""
                    SELECT *
                    FROM subjects
                    WHERE user_id = ?
                    ORDER BY semester, subject_code
                """, (session["user_id"],)).fetchall()

                connection.close()

                return render_template(
                    "subjects.html",
                    error="Credits must be between 1 and 4.",
                    subjects=subjects
                )

            connection.execute("""
                INSERT INTO subjects
                (
                    user_id,
                    subject_code,
                    subject_name,
                    credits,
                    semester
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                subject_code,
                subject_name,
                credits,
                semester
            ))

            connection.commit()

        except ValueError:

            subjects = connection.execute("""
                SELECT *
                FROM subjects
                WHERE user_id = ?
                ORDER BY semester, subject_code
            """, (session["user_id"],)).fetchall()

            connection.close()

            return render_template(
                "subjects.html",
                error="Credits must be a valid number.",
                subjects=subjects
            )

        except sqlite3.IntegrityError:

            subjects = connection.execute("""
                SELECT *
                FROM subjects
                WHERE user_id = ?
                ORDER BY semester, subject_code
            """, (session["user_id"],)).fetchall()

            connection.close()

            return render_template(
                "subjects.html",
                error="This subject code already exists.",
                subjects=subjects
            )

    subjects = connection.execute("""
        SELECT *
        FROM subjects
        WHERE user_id = ?
        ORDER BY semester, subject_code
    """, (session["user_id"],)).fetchall()

    connection.close()

    return render_template(
        "subjects.html",
        subjects=subjects
    )


@app.route("/subjects/delete/<int:subject_id>", methods=["POST"])
def delete_subject(subject_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    connection.execute("""
        DELETE FROM subjects
        WHERE id = ? AND user_id = ?
    """, (
        subject_id,
        session["user_id"]
    ))

    connection.commit()
    connection.close()

    return redirect(url_for("subjects"))

@app.route("/logout")
def logout():

    # Remove login information from session
    session.clear()

    return render_template(
        "login.html",
        logout_message="You have been logged out successfully."
    )


if __name__ == "__main__":
    create_database()
    app.run(debug=True, host="127.0.0.1", port=5001)
