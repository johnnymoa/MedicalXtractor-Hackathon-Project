from flask import Flask, request, jsonify, send_from_directory, send_file, render_template, url_for, redirect, flash, Blueprint
from flask_cors import CORS
from mistralai import Mistral
from flask_sqlalchemy import SQLAlchemy
from models import (
    User, ROLES, Document, Page, PrescriptionAnalysis, 
    Medication, DocumentSummary, SummaryExtraction, 
    Patient, PasswordResetToken, db
)
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from modules.document_processor import process_pdf_document
from modules.prescription_processor import PrescriptionAgent, process_prescription_analysis
from modules.summarizer_processor import process_document_summary
import json
import tempfile
import io
from PIL import Image
import base64
import fitz  # PyMuPDF
from concurrent.futures import ThreadPoolExecutor
import time
from threading import Semaphore
import dateutil.parser
import base64
from io import BytesIO
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
import secrets
from flask_mail import Mail, Message
from datetime import date
from flask import session

# Import route modules
from routes.document_routes import init_document_routes
from routes.prescription_routes import init_prescription_routes
from routes.summary_routes import init_summary_routes
from routes.auth_routes import init_auth_routes

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, 
    static_url_path='/static',
    template_folder='templates'  # Explicitly set the template folder
)
CORS(app)

app.config['TIMEOUT'] = 3600  # 1 hour timeout in seconds
# Obtenir le chemin absolu du dossier de l'application
basedir = os.path.abspath(os.path.dirname(__file__))

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Configure Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
mail = Mail(app)

# Configure Flask-SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')

# Initialize database
db.init_app(app)

# Initialize Mistral client
mistral_client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))

# Initialize prescription agent
prescription_agent = PrescriptionAgent(mistral_client)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        print(f"Error in load_user: {str(e)}")
        return None

# Role-based access control decorator
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Initialize routes
init_document_routes(app, db, Document, Page, process_pdf_document, mistral_client)
init_prescription_routes(app, db, Document, PrescriptionAnalysis, Medication, prescription_agent, process_prescription_analysis, mistral_client)
init_summary_routes(app, db, Document, DocumentSummary, SummaryExtraction, process_document_summary, mistral_client)
init_auth_routes(app)

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/documents')
@login_required
def documents():
    if current_user.role == 'medecin':
        patient_id = request.args.get('patient_id')
        if not patient_id:
            flash('Please select a patient first', 'warning')
            return redirect(url_for('dashboard'))
        # Vérifier que le patient appartient bien au médecin
        patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
        if not patient:
            flash('Patient not found or not associated with you', 'error')
            return redirect(url_for('dashboard'))
    return render_template('documents.html')

@app.route('/prescriptions')
@login_required
def prescriptions():
    if current_user.role == 'medecin':
        patient_id = request.args.get('patient_id')
        if not patient_id:
            flash('Please select a patient first', 'warning')
            return redirect(url_for('dashboard'))
        # Vérifier que le patient appartient bien au médecin
        patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
        if not patient:
            flash('Patient not found or not associated with you', 'error')
            return redirect(url_for('dashboard'))
    return render_template('prescriptions.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/admin/users')
@login_required
@role_required('admin', 'centre_regional', 'centre_hospitalier', 'service_hospitalier', 'cabinet_medical')
def admin_users():
    return render_template('admin/users.html')

@app.route('/credits')
def credits():
    return render_template('credits.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Ajout de logs pour le débogage
        print(f"Tentative de connexion pour: {email}")
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            print(f"Connexion réussie pour: {email}")
            return redirect(url_for('dashboard'))
            
        print(f"Échec de connexion pour: {email}")
        flash('Email ou mot de passe incorrect')
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # Clear all session data
    session.clear()
    logout_user()
    return redirect(url_for('login'))

@app.route('/summarizer')
@login_required
def summarizer():
    if current_user.role == 'medecin':
        patient_id = request.args.get('patient_id')
        if not patient_id:
            flash('Please select a patient first', 'warning')
            return redirect(url_for('dashboard'))
        # Vérifier que le patient appartient bien au médecin
        patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
        if not patient:
            flash('Patient not found or not associated with you', 'error')
            return redirect(url_for('dashboard'))
    return render_template('summarizer.html')

# Création d'un décorateur pour vérifier les rôles
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))

            # Get the effective user (impersonated or real)
            effective_user = current_user
            impersonating_user_id = session.get('impersonating_user_id')
            if impersonating_user_id:
                effective_user = User.query.get(int(impersonating_user_id))

            # Check if user has required role
            if effective_user.role != role:
                flash('Access denied')
                return redirect(url_for('dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Décorateurs pour les rôles
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != ROLES['ADMIN']:
            flash('Accès réservé aux administrateurs')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def centre_regional_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != ROLES['CENTRE_REGIONAL']:
            flash('Accès réservé aux centres régionaux')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes pour l'administrateur
@app.route('/admin/utilisateurs')
@admin_required
def gestion_utilisateurs():
    users = {
        'admin': User.query.filter_by(role=ROLES['ADMIN']).all(),
        'centre_regional': User.query.filter_by(role=ROLES['CENTRE_REGIONAL']).all(),
        'centre_hospitalier': User.query.filter_by(role=ROLES['CENTRE_HOSPITALIER']).all(),
        'service_hospitalier': User.query.filter_by(role=ROLES['SERVICE_HOSPITALIER']).all(),
        'cabinet_medical': User.query.filter_by(role=ROLES['CABINET_MEDICAL']).all(),
        'medecin': User.query.filter_by(role=ROLES['MEDECIN']).all(),
        'patient': User.query.filter_by(role=ROLES['PATIENT']).all()
    }
    return render_template('admin/utilisateurs.html', users=users)

@app.route('/admin/statistiques')
@admin_required
def statistiques():
    return render_template('admin/statistiques.html')

# Routes pour le centre régional
@app.route('/regional/centres')
@centre_regional_required
def gestion_centres():
    return render_template('regional/centres.html')

@app.route('/regional/statistiques')
@centre_regional_required
def statistiques_regionales():
    return render_template('regional/statistiques.html')

# Routes pour les médecins
@app.route('/medecin/patients')
@login_required
@role_required(ROLES['MEDECIN'])
def mes_patients():
    # Récupérer la liste des patients du médecin connecté
    patients = Patient.query.filter_by(medecin_id=current_user.id).all()
    return render_template('medecin/patients.html', patients=patients)

@app.route('/medecin/prescriptions')
@login_required
@role_required(ROLES['MEDECIN'])
def prescriptions_medecin():
    # Récupérer les patients du médecin pour le select
    patients = Patient.query.filter_by(medecin_id=current_user.id).all()
    # Pour l'instant, liste vide de prescriptions
    prescriptions = []
    return render_template('medecin/prescriptions.html', 
                         prescriptions=prescriptions,
                         patients=patients)

@app.route('/api/patients', methods=['GET'])
@login_required
@role_required(ROLES['MEDECIN'])
def get_patients():
    try:
        # Récupérer tous les utilisateurs qui sont des patients du médecin connecté
        patients = (User.query
                   .join(Patient, User.id == Patient.user_id)
                   .filter(Patient.doctor_id == current_user.id)
                   .all())
        
        # Formater les données des patients
        patients_data = [{
            'id': patient.patient_record[0].id,  # ID de la relation patient-médecin
            'nom': patient.nom,
            'prenom': patient.prenom,
            'email': patient.email,
            'date_creation': patient.patient_record[0].date_creation.strftime('%Y-%m-%d') if patient.patient_record[0].date_creation else None
        } for patient in patients]
        
        return jsonify(patients_data)
    except Exception as e:
        print(f"Error getting patients: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/prescriptions', methods=['POST'])
@login_required
def create_prescription():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'File must be a PDF'}), 400

        # Get patient_id from form data when doctor is uploading
        patient_id = request.form.get('patient_id')
        
        if current_user.role == 'medecin':
            if not patient_id:
                return jsonify({'error': 'Patient ID is required'}), 400
            # Vérifier que le patient appartient bien au médecin
            patient_record = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
            if not patient_record:
                return jsonify({'error': 'Patient not found or not associated with current doctor'}), 404
        else:
            # Si c'est un patient qui upload
            patient_record = Patient.query.filter_by(user_id=current_user.id).first()
            if not patient_record:
                return jsonify({'error': 'No patient record found for current user'}), 404

        # Create document with file data
        file_data = file.read()
        document = Document(
            filename=file.filename,
            data=file_data,
            user_id=current_user.id  # Always set to current user
        )
        db.session.add(document)
        db.session.commit()

        try:
            # Analyze the prescription using the AI
            prescription_result = process_prescription_analysis(
                document=document,
                prescription_agent=prescription_agent,
                db=db,
                PrescriptionAnalysis=PrescriptionAnalysis,
                Medication=Medication
            )
            print(f"Prescription analysis completed: {prescription_result}")
            return jsonify({'message': 'Prescription uploaded and analyzed successfully', 'document_id': document.id}), 200
        except Exception as analysis_error:
            print(f"Prescription analysis error: {str(analysis_error)}")
            # Clean up if analysis fails
            db.session.delete(document)
            db.session.commit()
            return jsonify({'error': f'Failed to analyze prescription: {str(analysis_error)}'}), 500

    except Exception as e:
        db.session.rollback()
        print(f"Error creating prescription: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prescriptions/<int:id>', methods=['PUT'])
@login_required
def update_prescription(id):
    try:
        prescription = PrescriptionAnalysis.query.get_or_404(id)
        
        # Update prescription date
        prescription.analysis_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        
        # Update medications
        # First, remove all existing medications
        Medication.query.filter_by(prescription_id=id).delete()
        
        # Add new medications
        medications = request.form.get('medications').split('\n')
        for med in medications:
            if med.strip():
                medication = Medication(
                    prescription_id=id,
                    name=med.strip()
                )
                db.session.add(medication)
        
        # Update PDF if provided
        if 'file' in request.files:
            file = request.files['file']
            if file.filename and file.filename.lower().endswith('.pdf'):
                # Process new PDF
                result = process_pdf_document(file, db, Document, Page, mistral_client)
                if result.get('success'):
                    # Update document reference
                    old_document = prescription.document
                    prescription.document_id = result.get('document_id')
                    # Delete old document
                    db.session.delete(old_document)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Prescription updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating prescription: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Routes pour les patients
@app.route('/patient/prescriptions')
@login_required
@role_required(ROLES['PATIENT'])
def my_prescriptions():
    try:
        # Find patient record using user_id
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient:
            return render_template('patient/prescriptions.html', 
                                 prescriptions=[], 
                                 documents=[])

        # Récupérer les documents
        documents = Document.query.filter_by(user_id=current_user.id)\
                                .order_by(Document.upload_date.desc())\
                                .all()

        # Récupérer les prescriptions
        prescriptions = (
            PrescriptionAnalysis.query
            .join(Document)
            .filter(Document.user_id == current_user.id)
            .order_by(PrescriptionAnalysis.analysis_date.desc())
            .all()
        )

        medications_data = []
        for prescription in prescriptions:
            for medication in prescription.medications:
                medications_data.append({
                    'name': medication.name,
                    'dosage': medication.dosage,
                    'frequency': medication.frequency,
                    'start_date': medication.start_date.isoformat() if medication.start_date else None,
                    'end_date': medication.end_date.isoformat() if medication.end_date else None,
                    'duration': medication.duration,
                    'duration_raw': medication.duration_raw,
                    'instructions': medication.instructions,
                    'page_number': medication.page_number,
                    'document_name': prescription.document.filename,
                    'document_id': prescription.document.id
                })

        return render_template(
            'patient/prescriptions.html',
            prescriptions=medications_data,
            documents=documents
        )

    except Exception as e:
        print(f"Error getting prescriptions: {str(e)}")
        return render_template('patient/prescriptions.html', 
                             prescriptions=[], 
                             documents=[])

@app.route('/patient/rendez-vous')
@login_required
@role_required(ROLES['PATIENT'])
def mes_rendez_vous():
    return render_template('patient/rendez-vous.html')

@app.route('/patient/dossier')
@login_required
@role_required(ROLES['PATIENT'])
def mon_dossier():
    return render_template('patient/dossier.html')

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.nom = request.form.get('nom')
        current_user.prenom = request.form.get('prenom')
        current_user.organisation = request.form.get('organisation')
        db.session.commit()
        flash('Profil mis à jour avec succès')
        return redirect(url_for('profile'))
    return render_template('edit_profile.html')

@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        if not current_user.check_password(request.form.get('current_password')):
            flash('Mot de passe actuel incorrect')
            return redirect(url_for('change_password'))
            
        if request.form.get('new_password') != request.form.get('confirm_password'):
            flash('Les nouveaux mots de passe ne correspondent pas')
            return redirect(url_for('change_password'))
            
        current_user.set_password(request.form.get('new_password'))
        db.session.commit()
        flash('Mot de passe modifié avec succès')
        return redirect(url_for('profile'))
        
    return render_template('change_password.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Générer un token unique
            token = secrets.token_urlsafe(32)
            expiration = datetime.utcnow() + timedelta(hours=24)
            
            # Sauvegarder le token
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expiration=expiration
            )
            db.session.add(reset_token)
            db.session.commit()
            
            # Envoyer l'email
            reset_url = url_for('reset_password', token=token, _external=True)
            msg = Message('Réinitialisation de mot de passe',
                        sender='noreply@team10x.com',
                        recipients=[user.email])
            msg.body = f'''Pour réinitialiser votre mot de passe, visitez le lien suivant:
{reset_url}

Si vous n'avez pas demandé de réinitialisation de mot de passe, ignorez cet email.
'''
            mail.send(msg)
            
            flash('Un email de réinitialisation a été envoyé.', 'info')
            return redirect(url_for('login'))
            
        flash('Aucun compte associé à cet email.', 'danger')
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Vérifier le token
    reset_token = PasswordResetToken.query.filter_by(token=token).first()
    
    if not reset_token or reset_token.expiration < datetime.utcnow():
        flash('Le lien de réinitialisation est invalide ou a expiré.', 'danger')
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas.', 'danger')
            return redirect(url_for('reset_password', token=token))
            
        user = User.query.get(reset_token.user_id)
        user.set_password(password)
        
        # Supprimer le token utilisé
        db.session.delete(reset_token)
        db.session.commit()
        
        flash('Votre mot de passe a été mis à jour.', 'success')
        return redirect(url_for('login'))
        
    return render_template('reset_password.html')

@app.route('/api/patients', methods=['POST'])
@login_required
@role_required(ROLES['MEDECIN'])
def add_patient():
    try:
        data = request.get_json()
        
        # Create patient-doctor relation
        patient = Patient(
            user_id=data['user_id'],
            doctor_id=current_user.id
        )
        
        db.session.add(patient)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'patient_id': patient.id,
            'message': 'Patient relation created successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# Add this new decorator for admin impersonation
def admin_or_impersonating(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
            
        # Allow access if user is admin or is impersonating the correct role
        impersonating_role = session.get('impersonating_role')
        if current_user.role == ROLES['ADMIN'] or impersonating_role:
            return f(*args, **kwargs)
            
        flash('Access denied')
        return redirect(url_for('dashboard'))
    return decorated_function

# Add impersonation routes
@app.route('/admin/impersonate/<int:user_id>')
@admin_required
def impersonate_user(user_id):
    try:
        # Verify admin rights
        if current_user.role != ROLES['ADMIN']:
            flash('Only administrators can impersonate users')
            return redirect(url_for('dashboard'))

        # Get user to impersonate
        user_to_impersonate = User.query.get_or_404(user_id)
        
        # Store impersonation data
        session['original_user_id'] = current_user.id
        session['impersonating_user_id'] = user_id
        session['impersonating_role'] = user_to_impersonate.role
        
        flash(f'Now impersonating {user_to_impersonate.prenom} {user_to_impersonate.nom}')
        
    except Exception as e:
        print(f"Error starting impersonation: {str(e)}")
        flash('Error starting impersonation')
        
    return redirect(url_for('dashboard'))

@app.route('/admin/stop-impersonating')
def stop_impersonating():
    try:
        if 'original_user_id' in session:
            # Get the original admin user
            original_user_id = int(session['original_user_id'])
            original_user = User.query.get(original_user_id)
            
            if original_user:
                # Clear all impersonation data first
                session.pop('impersonating_user_id', None)
                session.pop('impersonating_role', None)
                session.pop('original_user_id', None)
                
                # Then log in as the original admin user
                login_user(original_user)
                flash('Successfully stopped impersonating')
            else:
                session.clear()
                flash('Error: Original user not found')
                return redirect(url_for('login'))
        else:
            flash('No active impersonation')
            
    except Exception as e:
        print(f"Error stopping impersonation: {str(e)}")
        session.clear()
        flash('Error stopping impersonation')
        return redirect(url_for('login'))
        
    return redirect(url_for('dashboard'))

# Routes pour la gestion des utilisateurs selon le rôle
@app.route('/regional/users')
@role_required(ROLES['CENTRE_REGIONAL'])
def regional_users():
    # Get hospital centers in the region
    hospital_users = User.query.filter_by(role=ROLES['CENTRE_HOSPITALIER']).all()
    return render_template('regional/users.html', users=hospital_users)

@app.route('/hospital/users')
@role_required(ROLES['CENTRE_HOSPITALIER'])
def hospital_users():
    # Get hospital services and doctors
    service_users = User.query.filter_by(role=ROLES['SERVICE_HOSPITALIER']).all()
    doctor_users = User.query.filter_by(role=ROLES['MEDECIN']).all()
    return render_template('hospital/users.html', 
                         service_users=service_users,
                         doctor_users=doctor_users)

@app.route('/service/users')
@role_required(ROLES['SERVICE_HOSPITALIER'])
def service_users():
    # Get doctors in the service
    doctor_users = User.query.filter_by(role=ROLES['MEDECIN']).all()
    return render_template('service/users.html', users=doctor_users)

@app.route('/cabinet/users')
@role_required(ROLES['CABINET_MEDICAL'])
def cabinet_users():
    # Get doctors in the medical office
    doctor_users = User.query.filter_by(role=ROLES['MEDECIN']).all()
    return render_template('cabinet/users.html', users=doctor_users)

@app.route('/api/patient/<int:patient_id>/data')
@login_required
@role_required(ROLES['MEDECIN'])
def get_patient_data(patient_id):
    try:
        # Vérifier que le patient appartient bien au médecin
        patient_record = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
        if not patient_record:
            return jsonify({'error': 'Patient not found'}), 404

        # Récupérer les documents du patient
        documents = Document.query.filter_by(user_id=patient_record.user_id)\
            .order_by(Document.upload_date.desc())\
            .all()
        
        # Récupérer les prescriptions actives
        prescriptions = PrescriptionAnalysis.query\
            .join(Document)\
            .filter(Document.user_id == patient_record.user_id)\
            .order_by(PrescriptionAnalysis.analysis_date.desc())\
            .all()

        # Formatter les données
        patient_data = {
            'documents': [{
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d'),
                'status': 'Analyzed' if hasattr(doc, 'prescription') and doc.prescription else 'Pending'
            } for doc in documents] if documents else [],
            
            'prescriptions': [{
                'id': prescription.id,
                'medications': [{
                    'name': med.name,
                    'dosage': med.dosage,
                    'frequency': med.frequency,
                    'end_date': med.end_date.strftime('%Y-%m-%d') if med.end_date else None
                } for med in prescription.medications] if prescription.medications else []
            } for prescription in prescriptions] if prescriptions else [],
            
            'medical_report': {
                'last_visit': None,  # Ces champs ne sont plus dans le modèle Patient
                'allergies': None,
                'chronic_conditions': None,
                'notes': None
            }
        }

        return jsonify(patient_data)

    except Exception as e:
        print(f"Error getting patient data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/analyze-summary/<int:doc_id>', methods=['GET', 'POST'])
@login_required
def analyze_summary(doc_id):
    try:
        document = Document.query.get_or_404(doc_id)
        
        # Vérifier les permissions
        if current_user.role == 'medecin':
            patient_id = request.args.get('patient_id')
            if not patient_id:
                return jsonify({'error': 'Patient ID is required'}), 400
            patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
            if not patient or document.user_id != patient.user_id:
                return jsonify({'error': 'Access denied'}), 403
        elif current_user.role == 'patient' and document.user_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
            
        # Continuer avec l'analyse
        if request.method == 'POST':
            return jsonify(process_document_summary(
                document=document,
                db=db,
                DocumentSummary=DocumentSummary,
                SummaryExtraction=SummaryExtraction,
                mistral_client=mistral_client
            ))
        else:
            if document.summary:
                return jsonify({
                    'extractions': [{
                        'category': ext.category,
                        'field': ext.field,
                        'value': ext.value,
                        'page_number': ext.page_number,
                        'associated_date': ext.associated_date.isoformat() if ext.associated_date else None,
                        'extraction_date': ext.extraction_date.isoformat()
                    } for ext in document.summary.extractions]
                })
            return jsonify({'message': 'No summary analysis found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:doc_id>/delete-with-analyses', methods=['DELETE'])
@login_required
def delete_document_with_analyses(doc_id):
    """Delete a document and all its associated analyses"""
    try:
        document = Document.query.get_or_404(doc_id)
        
        # Verify permissions
        if current_user.role == 'medecin':
            patient_id = request.args.get('patient_id')
            if not patient_id:
                return jsonify({'error': 'Patient ID is required'}), 400
            patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
            if not patient or document.user_id != patient.user_id:
                return jsonify({'error': 'Access denied'}), 403
        elif current_user.role == 'patient' and document.user_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403

        print(f"Starting deletion process for document {doc_id}")
        
        # First, get all related records
        prescription = PrescriptionAnalysis.query.filter_by(document_id=doc_id).first()
        summary = DocumentSummary.query.filter_by(document_id=doc_id).first()
        
        # Delete medications if they exist
        if prescription:
            print(f"Deleting medications for prescription {prescription.id}")
            Medication.query.filter_by(prescription_id=prescription.id).delete()
            db.session.flush()
        
        # Delete prescription analysis
        if prescription:
            print(f"Deleting prescription analysis {prescription.id}")
            db.session.delete(prescription)
            db.session.flush()
        
        # Delete summary extractions
        if summary:
            print(f"Deleting summary extractions for summary {summary.id}")
            SummaryExtraction.query.filter_by(summary_id=summary.id).delete()
            db.session.flush()
        
        # Delete summary
        if summary:
            print(f"Deleting summary {summary.id}")
            db.session.delete(summary)
            db.session.flush()
        
        # Delete pages
        print(f"Deleting pages for document {doc_id}")
        Page.query.filter_by(document_id=doc_id).delete()
        db.session.flush()
        
        # Refresh the document from the database
        db.session.refresh(document)
        
        # Delete the document
        print(f"Deleting document {doc_id}")
        db.session.delete(document)
        
        # Final commit
        db.session.commit()
        print(f"Successfully deleted document {doc_id} and all related records")
        
        return jsonify({'message': 'Document and associated analyses deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"Error deleting document {doc_id}: {error_msg}")
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=8080, host='0.0.0.0')
