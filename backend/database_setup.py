import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

def create_tables():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT
        )
    ''')

    # Create Pets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Pets (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            name TEXT NOT NULL,
            breed TEXT,
            age INTEGER,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES Users (id)
        )
    ''')

    # Create Services table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Services (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER,
            price REAL
        )
    ''')

    # Create Appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Appointments (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            pet_id INTEGER,
            service_id INTEGER,
            appointment_time TEXT, -- ISO format for datetime
            status TEXT, -- e.g., 'booked', 'completed', 'cancelled'
            FOREIGN KEY (user_id) REFERENCES Users (id),
            FOREIGN KEY (pet_id) REFERENCES Pets (id),
            FOREIGN KEY (service_id) REFERENCES Services (id)
        )
    ''')

    conn.commit()
    conn.close()

def populate_services():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    sample_services = [
        ("Bagno e Spazzolata", "Un bagno rinfrescante e una spazzolata completa.", 60, 30.00),
        ("Toelettatura Completa", "Include bagno, spazzolata, taglio unghie, pulizia orecchie e taglio.", 120, 50.00),
        ("Taglio Unghie", "Taglio e limatura delle unghie.", 15, 10.00),
        ("Pulizia Orecchie", "Pulizia delicata del canale auricolare.", 15, 10.00)
    ]

    for service in sample_services:
        cursor.execute("SELECT id FROM Services WHERE name = ?", (service[0],))
        if cursor.fetchone() is None: # If service doesn't exist
            cursor.execute("INSERT INTO Services (name, description, duration_minutes, price) VALUES (?, ?, ?, ?)", service)
    
    conn.commit()
    conn.close()
    print("Services populated successfully (if they didn't already exist).")


if __name__ == '__main__':
    create_tables()
    populate_services() # Call populate_services when script is run directly
    print("Database tables created and services populated successfully (if they didn't exist).")
