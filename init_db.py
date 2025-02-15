from flask import Flask
from models import db, User, ROLES, Patient
from datetime import date
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with app
db.init_app(app)

def init_db():
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        
        print("Creating all tables...")
        db.create_all()

        print("Creating default users...")
        
        # Créer l'administrateur
        admin = User(
            email='admin@team10x.com',
            role=ROLES['ADMIN'],
            nom='Admin',
            prenom='Super',
            organisation='Team10X'
        )
        admin.set_password('password')
        db.session.add(admin)
        db.session.commit()
        print("Admin created")

        # Créer le centre hospitalier
        hospital = User(
            email='hospital@team10x.com',
            role=ROLES['CENTRE_HOSPITALIER'],
            nom='Hospital',
            prenom='Central',
            organisation='Team10X Hospital'
        )
        hospital.set_password('password')
        db.session.add(hospital)
        db.session.commit()
        print("Hospital created")

        # Créer le cabinet médical
        cabinet = User(
            email='cabinet@team10x.com',
            role=ROLES['CABINET_MEDICAL'],
            nom='Cabinet',
            prenom='Medical',
            organisation='Team10X Cabinet'
        )
        cabinet.set_password('password')
        db.session.add(cabinet)
        db.session.commit()
        print("Medical office created")

        # Créer le médecin par défaut
        doctor = User(
            email='doctor@team10x.com',
            role=ROLES['MEDECIN'],
            nom='Doctor',
            prenom='Default',
            organisation='Team10X Medical',
            cabinet_id=cabinet.id,
            centre_id=hospital.id
        )
        doctor.set_password('password')
        db.session.add(doctor)
        db.session.commit()
        print("Default doctor created")

        # Créer plusieurs patients
        patients_data = [
            {
                'email': 'patient@team10x.com',
                'nom': 'Bernard',
                'prenom': 'Laporte'
            },
            {
                'email': 'patient1@team10x.com',
                'nom': 'Smith',
                'prenom': 'John'
            },
            {
                'email': 'patient2@team10x.com',
                'nom': 'Johnson',
                'prenom': 'Emma'
            },
            {
                'email': 'patient3@team10x.com',
                'nom': 'Brown',
                'prenom': 'Michael'
            },
            {
                'email': 'patient4@team10x.com',
                'nom': 'Davis',
                'prenom': 'Sarah'
            }
        ]

        # Créer les utilisateurs patients et les lier au médecin
        for patient_data in patients_data:
            # Créer l'utilisateur patient
            patient_user = User(
                email=patient_data['email'],
                role=ROLES['PATIENT'],
                nom=patient_data['nom'],
                prenom=patient_data['prenom']
            )
            patient_user.set_password('password')
            db.session.add(patient_user)
            db.session.commit()

            # Créer la relation patient-médecin
            patient_record = Patient(
                doctor_id=doctor.id,
                user_id=patient_user.id
            )
            db.session.add(patient_record)
            db.session.commit()
            print(f"Patient {patient_data['prenom']} {patient_data['nom']} created and linked to doctor")

        print("Database initialization completed")

if __name__ == "__main__":
    try:
        init_db()
        print("Database initialization successful")
    except Exception as e:
        print(f"Error during database initialization: {str(e)}") 