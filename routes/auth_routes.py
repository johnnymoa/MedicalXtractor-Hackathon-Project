from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User, db, ROLES, Patient
from werkzeug.security import generate_password_hash
import secrets
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

def init_auth_routes(app):
    print("\n=== Initializing auth routes ===")
    print("Registering auth_bp Blueprint")
    app.register_blueprint(auth_bp, url_prefix='/auth')
    print("Auth routes initialized successfully")

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    print("\n=== /register route called ===")
    print("Method:", request.method)
    
    # Pour les requêtes JSON, retourner une erreur au lieu de rediriger
    if current_user.is_authenticated and not request.is_json:
        print("User already authenticated, redirecting to dashboard")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        print("\n=== Processing POST request ===")
        print("Headers:", dict(request.headers))
        print("Raw data:", request.get_data(as_text=True))
        
        # Check if the request is JSON
        if request.is_json:
            print("\n=== Request is JSON ===")
            data = request.get_json()
            print("Parsed JSON data:", data)
            email = data.get('email')
            password = data.get('password')
            role = data.get('role')
            nom = data.get('nom')
            prenom = data.get('prenom')
            organisation = data.get('organisation')

            # Validate required fields
            if not all([email, password, role]):
                print("Missing required fields")
                return jsonify({'error': 'Missing required fields'}), 400

            # Check if email already exists
            if User.query.filter_by(email=email).first():
                return jsonify({'error': 'Email already registered'}), 400

            # Validate role
            if role not in ROLES.values():
                return jsonify({'error': 'Invalid role'}), 400

            # Si c'est un patient, vérifier que l'utilisateur connecté est un médecin
            if role == ROLES['PATIENT']:
                if not current_user.is_authenticated or current_user.role != ROLES['MEDECIN']:
                    return jsonify({'error': 'Only authenticated doctors can register patients'}), 403
                
                doctor_id = current_user.id

            # Create new user
            user = User(
                email=email,
                role=role,
                nom=nom,
                prenom=prenom,
                organisation=organisation
            )
            user.set_password(password)

            db.session.add(user)
            db.session.flush()  # Pour obtenir l'ID de l'utilisateur avant le commit

            # Si c'est un patient, créer la relation patient-médecin
            if role == ROLES['PATIENT']:
                patient = Patient(
                    user_id=user.id,
                    doctor_id=doctor_id
                )
                db.session.add(patient)

            db.session.commit()

            response_data = {
                'message': 'Registration successful',
                'user_id': user.id
            }
            
            # Ajouter patient_id à la réponse si c'est un patient
            if role == ROLES['PATIENT']:
                response_data['patient_id'] = patient.id

            return jsonify(response_data), 201

        # Handle form submission
        else:
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            role = request.form.get('role')
            nom = request.form.get('nom')
            prenom = request.form.get('prenom')
            organisation = request.form.get('organisation')

            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('auth/register.html')

            if User.query.filter_by(email=email).first():
                flash('Email already registered', 'error')
                return render_template('auth/register.html')

            if role not in ROLES.values():
                flash('Invalid role', 'error')
                return render_template('auth/register.html')

            user = User(
                email=email,
                role=role,
                nom=nom,
                prenom=prenom,
                organisation=organisation
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/register.html', roles=ROLES)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expiration=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(reset_token)
            db.session.commit()

            # Send password reset email
            # TODO: Implement email sending functionality
            flash('Password reset instructions have been sent to your email.', 'info')
            return redirect(url_for('auth.login'))
        flash('Email address not found', 'error')

    return render_template('auth/reset_password_request.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    reset_token = PasswordResetToken.query.filter_by(token=token).first()
    if not reset_token or reset_token.expiration < datetime.utcnow():
        flash('Invalid or expired reset token', 'error')
        return redirect(url_for('auth.reset_password_request'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html')

        user = User.query.get(reset_token.user_id)
        user.set_password(password)
        db.session.delete(reset_token)
        db.session.commit()

        flash('Your password has been reset', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html') 