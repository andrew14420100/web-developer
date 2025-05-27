from flask import Flask, request, jsonify, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from database_setup import create_tables, populate_services # Import populate_services

app = Flask(__name__)
# app.config['SECRET_KEY'] = os.urandom(24) # Generate a random secret key
app.config['SECRET_KEY'] = 'a_very_secret_key_for_development_only' # Fixed secret key for session stability

# Calculate absolute path to database.db in the root directory
DATABASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # This enables column access by name: row['column_name']
    return conn

@app.cli.command('init-db')
def init_db_command():
    """Creates the database tables."""
    create_tables()
    print('Initialized the database.')

@app.route('/')
def hello_world():
    # Test database connection
    try:
        conn = get_db()
        conn.close()
        user_id = session.get('user_id')
        if user_id:
            return f'Hello, World! Database connected. Logged in as user {user_id}.'
        return 'Hello, World! Database connected. Not logged in.'
    except sqlite3.Error as e:
        return f'Hello, World! Database connection failed: {e}'

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name')

    if not email or not password or not full_name:
        return jsonify({'error': 'Missing data'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM Users WHERE email = ?", (email,))
        if cursor.fetchone():
            return jsonify({'error': 'Email already exists'}), 409 # Conflict

        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO Users (email, password_hash, full_name) VALUES (?, ?, ?)",
                       (email, hashed_password, full_name))
        conn.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Missing email or password'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_full_name'] = user['full_name']
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'full_name': user['full_name']
                }
            }), 200
        else:
            return jsonify({'error': 'Invalid email or password'}), 401
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_full_name', None)
    return jsonify({'message': 'Logout successful'}), 200

# Decorator to protect routes that require login
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- Pet Management Endpoints ---

@app.route('/api/pets', methods=['POST'])
@login_required
def add_pet():
    user_id = session['user_id']
    data = request.get_json()
    name = data.get('name')
    breed = data.get('breed')
    age = data.get('age')
    notes = data.get('notes')

    if not name:
        return jsonify({'error': 'Pet name is required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Pets (user_id, name, breed, age, notes) VALUES (?, ?, ?, ?, ?)",
                       (user_id, name, breed, age, notes))
        conn.commit()
        pet_id = cursor.lastrowid
        return jsonify({
            'message': 'Pet added successfully',
            'pet': {'id': pet_id, 'user_id': user_id, 'name': name, 'breed': breed, 'age': age, 'notes': notes}
        }), 201
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/pets', methods=['GET'])
@login_required
def get_pets():
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, breed, age, notes FROM Pets WHERE user_id = ?", (user_id,))
        pets_rows = cursor.fetchall()
        pets = [dict(row) for row in pets_rows] # Convert rows to list of dicts
        return jsonify(pets), 200
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/pets/<int:pet_id>', methods=['PUT'])
@login_required
def update_pet(pet_id):
    user_id = session['user_id']
    data = request.get_json()
    name = data.get('name')
    breed = data.get('breed')
    age = data.get('age')
    notes = data.get('notes')

    if not name: # Name is mandatory
        return jsonify({'error': 'Pet name is required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        # Verify pet belongs to the user
        cursor.execute("SELECT id FROM Pets WHERE id = ? AND user_id = ?", (pet_id, user_id))
        pet = cursor.fetchone()
        if not pet:
            return jsonify({'error': 'Pet not found or access denied'}), 404

        cursor.execute("UPDATE Pets SET name = ?, breed = ?, age = ?, notes = ? WHERE id = ? AND user_id = ?",
                       (name, breed, age, notes, pet_id, user_id))
        conn.commit()
        if cursor.rowcount == 0:
             return jsonify({'error': 'Pet not found or access denied, or no data changed'}), 404 # Or some other appropriate error
        return jsonify({
            'message': 'Pet updated successfully',
            'pet': {'id': pet_id, 'user_id': user_id, 'name': name, 'breed': breed, 'age': age, 'notes': notes}
        }), 200
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/pets/<int:pet_id>', methods=['DELETE'])
@login_required
def delete_pet(pet_id):
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Verify pet belongs to the user
        cursor.execute("SELECT id FROM Pets WHERE id = ? AND user_id = ?", (pet_id, user_id))
        pet = cursor.fetchone()
        if not pet:
            return jsonify({'error': 'Pet not found or access denied'}), 404

        cursor.execute("DELETE FROM Pets WHERE id = ? AND user_id = ?", (pet_id, user_id))
        conn.commit()
        if cursor.rowcount == 0: # Should not happen if previous check passed, but good for safety
            return jsonify({'error': 'Pet not found or access denied during delete'}), 404
        return jsonify({'message': 'Pet deleted successfully'}), 200
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()


# --- Services Endpoint ---

@app.route('/api/services', methods=['GET'])
def get_services():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, description, duration_minutes, price FROM Services")
        services_rows = cursor.fetchall()
        services = [dict(row) for row in services_rows]
        return jsonify(services), 200
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

# --- Appointment Booking Endpoints ---
from datetime import datetime, timedelta, time as dt_time

@app.route('/api/services/<int:service_id>', methods=['GET'])
def get_service_details(service_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, description, duration_minutes, price FROM Services WHERE id = ?", (service_id,))
        service = cursor.fetchone()
        if service:
            return jsonify(dict(service)), 200
        else:
            return jsonify({'error': 'Service not found'}), 404
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/availability', methods=['GET'])
def check_availability():
    service_id = request.args.get('service_id', type=int)
    date_str = request.args.get('date') # YYYY-MM-DD

    if not service_id or not date_str:
        return jsonify({'error': 'Missing service_id or date'}), 400

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if selected_date < datetime.now().date():
        return jsonify({'available_slots': [], 'message': 'Cannot book for past dates.'}), 200
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT duration_minutes FROM Services WHERE id = ?", (service_id,))
    service_row = cursor.fetchone()
    if not service_row:
        conn.close()
        return jsonify({'error': 'Service not found'}), 404
    
    service_duration = timedelta(minutes=service_row['duration_minutes'])
    
    # Define business hours
    business_start_hour = 9
    business_end_hour = 17 # 5 PM
    slot_interval_minutes = 30 # Consider slots every 30 minutes for simplicity

    available_slots = []
    current_slot_time = datetime.combine(selected_date, dt_time(business_start_hour, 0))
    business_end_dt = datetime.combine(selected_date, dt_time(business_end_hour, 0))

    # Get existing appointments for the selected date
    cursor.execute("""
        SELECT appointment_time, s.duration_minutes 
        FROM Appointments a
        JOIN Services s ON a.service_id = s.id
        WHERE date(a.appointment_time) = ? AND a.status = 'booked'
    """, (date_str,))
    booked_appointments = cursor.fetchall()
    conn.close()

    booked_intervals = []
    for appt in booked_appointments:
        appt_start = datetime.fromisoformat(appt['appointment_time'])
        appt_duration = timedelta(minutes=appt['duration_minutes'])
        appt_end = appt_start + appt_duration
        booked_intervals.append((appt_start, appt_end))

    while current_slot_time + service_duration <= business_end_dt:
        slot_end_time = current_slot_time + service_duration
        
        # Check for overlaps with booked appointments
        is_free = True
        for booked_start, booked_end in booked_intervals:
            # Check if proposed slot [current_slot_time, slot_end_time)
            # overlaps with booked interval [booked_start, booked_end)
            if max(current_slot_time, booked_start) < min(slot_end_time, booked_end):
                is_free = False
                break
        
        if is_free:
            # For today, only show future slots
            if selected_date == datetime.now().date() and current_slot_time.time() <= datetime.now().time():
                pass # Slot is in the past for today
            else:
                 available_slots.append(current_slot_time.strftime('%H:%M'))

        current_slot_time += timedelta(minutes=slot_interval_minutes) # Move to next potential slot start

    return jsonify({'available_slots': available_slots}), 200


@app.route('/api/bookings', methods=['POST'])
@login_required
def create_booking():
    user_id = session['user_id']
    data = request.get_json()
    pet_id = data.get('pet_id')
    service_id = data.get('service_id')
    appointment_time_str = data.get('appointment_time') # Expect "YYYY-MM-DD HH:MM"

    if not all([pet_id, service_id, appointment_time_str]):
        return jsonify({'error': 'Missing data: pet_id, service_id, or appointment_time is required'}), 400

    try:
        appointment_dt = datetime.strptime(appointment_time_str, '%Y-%m-%d %H:%M')
    except ValueError:
        return jsonify({'error': 'Invalid appointment_time format. Use YYYY-MM-DD HH:MM'}), 400

    # Basic validation: appointment must be in the future
    if appointment_dt < datetime.now():
        return jsonify({'error': 'Cannot book appointments in the past'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Verify pet belongs to user
    cursor.execute("SELECT id FROM Pets WHERE id = ? AND user_id = ?", (pet_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Pet not found or does not belong to user'}), 403
    
    # Verify service exists
    cursor.execute("SELECT duration_minutes FROM Services WHERE id = ?", (service_id,))
    service_row = cursor.fetchone()
    if not service_row:
        conn.close()
        return jsonify({'error': 'Service not found'}), 404
    service_duration = timedelta(minutes=service_row['duration_minutes'])
    appointment_end_dt = appointment_dt + service_duration

    # More robust availability check (re-check just before booking)
    # Check business hours (e.g. 9am to 5pm)
    business_start_time = dt_time(9,0)
    business_end_time = dt_time(17,0)
    if not (business_start_time <= appointment_dt.time() and appointment_end_dt.time() <= business_end_time):
         # Check if appointment ends exactly at 5 PM, which is allowed.
        if appointment_dt.time() < business_end_time and appointment_end_dt.time() == business_end_time:
            pass # This is fine
        else: 
            conn.close()
            return jsonify({'error': f'Appointment must be within business hours (09:00 - 17:00). Proposed end: {appointment_end_dt.strftime("%H:%M")}'}), 400


    cursor.execute("""
        SELECT id FROM Appointments 
        WHERE service_id = ? AND status = 'booked' AND 
        (
            (datetime(appointment_time) >= datetime(?) AND datetime(appointment_time) < datetime(?)) OR
            (datetime(appointment_time, '+' || (SELECT duration_minutes FROM Services WHERE id = service_id) || ' minutes') > datetime(?) AND
             datetime(appointment_time, '+' || (SELECT duration_minutes FROM Services WHERE id = service_id) || ' minutes') <= datetime(?)) OR
            (datetime(appointment_time) <= datetime(?) AND 
             datetime(appointment_time, '+' || (SELECT duration_minutes FROM Services WHERE id = service_id) || ' minutes') >= datetime(?))
        )
    """, (service_id, 
          appointment_dt.isoformat(), appointment_end_dt.isoformat(), # Slot starts within proposed
          appointment_dt.isoformat(), appointment_end_dt.isoformat(), # Slot ends within proposed
          appointment_dt.isoformat(), appointment_end_dt.isoformat()  # Slot contains proposed
          ))
    
    # The above SQL for conflict is a bit complex and might not be perfect for all edge cases with SQLite datetime functions.
    # A simpler approach for now, given the /api/availability already checked:
    # Check if chosen exact start time is already booked FOR ANY SERVICE (as a proxy for groomer availability)
    # This is a simplification. A real system would have groomer schedules.
    cursor.execute("""
        SELECT a.id, s.duration_minutes FROM Appointments a
        JOIN Services s ON a.service_id = s.id
        WHERE date(a.appointment_time) = date(?) AND a.status = 'booked'
    """, (appointment_dt.date().isoformat(),))

    existing_appointments_on_date = cursor.fetchall()
    appointment_start_iso = appointment_dt.isoformat()
    appointment_end_iso = appointment_end_dt.isoformat()

    for existing_appt in existing_appointments_on_date:
        existing_start = datetime.fromisoformat(existing_appt['appointment_time'])
        existing_duration = timedelta(minutes=existing_appt['duration_minutes'])
        existing_end = existing_start + existing_duration
        # Check for overlap: max(start1, start2) < min(end1, end2)
        if max(appointment_dt, existing_start) < min(appointment_end_dt, existing_end):
            conn.close()
            return jsonify({'error': f'The selected time slot {appointment_time_str} is no longer available.'}), 409 # Conflict
            
    try:
        cursor.execute("INSERT INTO Appointments (user_id, pet_id, service_id, appointment_time, status) VALUES (?, ?, ?, ?, 'booked')",
                       (user_id, pet_id, service_id, appointment_dt.isoformat()))
        conn.commit()
        booking_id = cursor.lastrowid
        return jsonify({
            'message': 'Appointment booked successfully',
            'booking': {
                'id': booking_id, 'user_id': user_id, 'pet_id': pet_id, 
                'service_id': service_id, 'appointment_time': appointment_dt.isoformat(), 'status': 'booked'
            }
        }), 201
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error during booking: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/bookings', methods=['GET'])
@login_required
def get_user_bookings():
    user_id = session['user_id']
    status_filter = request.args.get('status') # e.g., 'upcoming', 'past', 'cancelled'

    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            a.id, a.appointment_time, a.status,
            p.name as pet_name, p.breed as pet_breed,
            s.name as service_name, s.duration_minutes as service_duration, s.price as service_price
        FROM Appointments a
        JOIN Pets p ON a.pet_id = p.id
        JOIN Services s ON a.service_id = s.id
        WHERE a.user_id = ?
    """
    params = [user_id]

    # For filtering by status (upcoming/past)
    # This requires comparing appointment_time with current time
    now_iso = datetime.now().isoformat()
    if status_filter == 'upcoming':
        query += " AND datetime(a.appointment_time) >= datetime(?)"
        params.append(now_iso)
    elif status_filter == 'past':
        query += " AND datetime(a.appointment_time) < datetime(?)"
        params.append(now_iso)
    elif status_filter: # Specific status like 'booked', 'cancelled'
        query += " AND a.status = ?"
        params.append(status_filter)
    
    query += " ORDER BY datetime(a.appointment_time) DESC" # Show most recent first, or adjust as needed

    try:
        cursor.execute(query, tuple(params))
        bookings_rows = cursor.fetchall()
        bookings = [dict(row) for row in bookings_rows]
        return jsonify(bookings), 200
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    # Ensure tables are created and services populated when the app is run directly
    create_tables()
    populate_services() # Call populate_services
    app.run(debug=True, host='0.0.0.0', port=5000) # Specify port
