from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Créer l'instance SQLAlchemy sans l'initialiser
db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    # Champs supplémentaires selon le rôle
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    organisation = db.Column(db.String(200))
    
    # Relations organisationnelles
    cabinet_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    centre_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relations hiérarchiques
    cabinet = db.relationship('User', remote_side=[id], backref='medecins_cabinet', foreign_keys=[cabinet_id])
    service = db.relationship('User', remote_side=[id], backref='medecins_service', foreign_keys=[service_id])
    centre = db.relationship('User', remote_side=[id], backref='medecins_centre', foreign_keys=[centre_id])
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Définition des rôles possibles
ROLES = {
    'ADMIN': 'admin',
    'CENTRE_REGIONAL': 'centre_regional',
    'CENTRE_HOSPITALIER': 'centre_hospitalier',
    'SERVICE_HOSPITALIER': 'service_hospitalier',
    'CABINET_MEDICAL': 'cabinet_medical',
    'MEDECIN': 'medecin',
    'PATIENT': 'patient'
}

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_pages = db.Column(db.Integer)
    # Relations avec les différentes entités
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relations
    user = db.relationship('User', foreign_keys=[user_id], backref='documents')
    
    pages = db.relationship('Page', backref='document', cascade='all, delete-orphan')
    prescription = db.relationship('PrescriptionAnalysis', backref='document', uselist=False, cascade='all, delete-orphan')
    summary = db.relationship('DocumentSummary', backref='document', uselist=False, cascade='all, delete-orphan')

class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page_number = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_data = db.Column(db.Text)  # Store base64 encoded image
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)

class PrescriptionAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'))
    analysis_date = db.Column(db.DateTime, default=datetime.utcnow)
    medications = db.relationship('Medication', backref='prescription')

class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescription_analysis.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    dosage = db.Column(db.String(255))
    frequency = db.Column(db.String(255))
    start_date = db.Column(db.Date)
    duration = db.Column(db.String(255))
    duration_raw = db.Column(db.String(255))
    end_date = db.Column(db.Date)
    instructions = db.Column(db.Text)
    page_number = db.Column(db.Integer)

class DocumentSummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    analysis_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    extractions = db.relationship('SummaryExtraction', backref='summary', lazy=True, cascade='all, delete-orphan')

class SummaryExtraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    summary_id = db.Column(db.Integer, db.ForeignKey('document_summary.id'), nullable=False)
    category = db.Column(db.String(255), nullable=False)
    field = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=False)
    page_number = db.Column(db.Integer)
    associated_date = db.Column(db.Date)
    extraction_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='patients')
    user = db.relationship('User', foreign_keys=[user_id], backref='patient_record')

class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expiration = db.Column(db.DateTime, nullable=False) 