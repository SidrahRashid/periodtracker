from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # disables caching of static files
app.secret_key = "helloperiods"

# --- Database Setup ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir,'tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = "helloperiods"

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Model ---
class Cycle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.String(10), nullable=False)  # DD-MM-YYYY
    cycle_length = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"<Cycle {self.start_date} ({self.cycle_length} days)>"

# --- Routes ---

@app.route('/')
def home():
    return render_template('index.html')

from flask_login import login_required, current_user

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_cycle():
    if request.method == 'POST':
        start_date = request.form['start_date']
        cycle_length = int(request.form['cycle_length'])

        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        start_date_str = start_date_obj.strftime("%d-%m-%Y")

        # Make sure current_user is not None
        if current_user.is_authenticated:
            new_cycle = Cycle(
                start_date=start_date_str,
                cycle_length=cycle_length,
                user_id=current_user.id
            )
            db.session.add(new_cycle)
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('login'))

    return render_template('add_cycle.html')


@app.route('/dashboard')
@login_required
def dashboard():
    cycles = Cycle.query.filter_by(user_id=current_user.id).order_by(Cycle.id).all()
    next_period = "N/A"
    fertile_window = "N/A"

    if cycles:
        # Moving average prediction
        lengths = [c.cycle_length for c in cycles]
        window = 3
        if len(lengths) >= window:
            avg_length = round(sum(lengths[-window:]) / window)
        else:
            avg_length = lengths[-1]

        last_cycle = cycles[-1]
        last_date = datetime.strptime(last_cycle.start_date, "%d-%m-%Y")

        # Predicted next period
        next_date = last_date + timedelta(days=avg_length)
        next_period = next_date.strftime("%d-%m-%Y")

        # Fertile window (14 days before next period ±2)
        fertile_start = next_date - timedelta(days=16)
        fertile_end = next_date - timedelta(days=12)
        fertile_window = f"{fertile_start.strftime('%d-%m-%Y')} to {fertile_end.strftime('%d-%m-%Y')}"

    # Pass cycles as list of tuples for templates
    cycle_list = [(c.start_date, c.cycle_length) for c in cycles]
    # Prepare data for chart
    cycle_dates = [c.start_date for c in cycles]   # x-axis
    cycle_lengths = [c.cycle_length for c in cycles]  # y-axis

    return render_template('dashboard.html',
                       cycles=cycle_list,
                       next_period=next_period,
                       fertile_window=fertile_window,
                       cycle_dates=cycle_dates,
                       cycle_lengths=cycle_lengths)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if username exists
        if User.query.filter_by(username=username).first():
            return "Username already exists"

        # Hash password and save
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        return "Invalid credentials"

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))




# --- Run App ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure DB exists
    app.run(debug=True)
