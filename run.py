from flask import Flask, render_template, request, jsonify, redirect, url_for
import os, json
from werkzeug.utils import secure_filename
from datetime import datetime

# Initialize Flask app
webapplication = Flask(__name__)
webapplication.secret_key = "session"

# Define folder for uploads and journal file
UPLOAD_FOLDER = 'static/uploads'
JOURNAL_FILE = 'journal_entries.json'
TRIPS_FILE = 'trips.json'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Index route
from datetime import timedelta

# Index route
@webapplication.route("/", methods=['GET'])
def index():
    try:
        # Load trip data
        with open(TRIPS_FILE, 'r') as f:
            trips = json.load(f)

        # Get the date 7 days ago
        today = datetime.today()
        seven_days_ago = today - timedelta(days=7)

        # Filter trips from the last 7 days
        recent_trips = [
            trip for trip in trips 
            if datetime.strptime(trip['startTime'].split()[0], "%d/%m/%Y") >= seven_days_ago
        ]
        
        # Calculate weekly insights
        total_distance = sum(trip['distance'] for trip in recent_trips)
        total_entries = len(recent_trips)
        total_duration = sum(trip['duration'] for trip in recent_trips)

        # Format the insights
        weekly_insights = {
            "distance": format_distance(total_distance),
            "entries": total_entries,
            "duration": format_duration(total_duration),
        }

        # Extract details for each trip 
        trip_events = [
            {
                'tripDate': trip['startTime'].split()[0],
                'day': trip['dayOfWeek'],
                'coordinates': trip['coordinates'][0]['location'] if trip['coordinates'] else None,
                'description': f"Trip #{trip['id']} - Distance: {format_distance(trip['distance'])}"
            }
            for trip in recent_trips
        ]

        # Sort trips by date in descending order
        recent_events = sorted(
            trip_events, 
            key=lambda x: datetime.strptime(x['tripDate'], "%d/%m/%Y"), 
            reverse=True
        )[:3]

        # Pass insights and recent events to the index template
        return render_template('index.html', 
                               recent_trips=recent_events, 
                               weekly_insights=weekly_insights)

    except Exception as e:
        print(f"Error loading recent trips: {e}")
        return "Error loading recent trips", 500

# Helper function to format duration (in seconds)
def format_duration(duration_s):
    hours = duration_s // 3600
    minutes = (duration_s % 3600) // 60
    return f"{hours} hours {minutes} minutes" if hours else f"{minutes} minutes"


# Route to load the journal page
@webapplication.route("/journal")
def journal():
    return render_template("journal.html")

# Route to load the history page
@webapplication.route("/list")
def list():
    return render_template("history.html")

# Route to load the calendar page with trips data
@webapplication.route('/calendar')
def calendar():
    try:
        # Load trips data
        with open(TRIPS_FILE, 'r') as f:
            trips = json.load(f)

        # Load journal entries data
        with open(JOURNAL_FILE, 'r') as f:
            journal_entries = json.load(f)
        
        # Extract dates and details from trips
        trip_events = [
            {
                'tripDate': trip['startTime'].split()[0],
                'time': trip['startTime'].split()[1],
                'day': trip['dayOfWeek'],
                'description': f"Trip #{trip['id']} - Distance: {format_distance(trip['distance'])}"
            }
            for trip in trips
        ]
        
        # Extract dates and details from journal entries
        journal_events = [
            {
                'tripDate': datetime.strptime(entry['date'], "%d/%m/%Y").strftime("%d/%m/%Y"),
                'time': None,
                'day': datetime.strptime(entry['date'], "%d/%m/%Y").strftime("%A"),
                'description': "Journal Entry"
            }
            for entry in journal_entries
        ]

        # Combine events by date
        combined_events_dict = {}
        for event in trip_events + journal_events:
            date = event['tripDate']
            if date not in combined_events_dict:
                combined_events_dict[date] = {
                    'tripDate': date,
                    'day': event['day'],
                    'events': [event['description']]
                }
            else:
                combined_events_dict[date]['events'].append(event['description'])

        # Sort combined events in descending order by date
        combined_events = sorted(
            combined_events_dict.values(),
            key=lambda x: datetime.strptime(x['tripDate'], "%d/%m/%Y"),
            reverse=True
        )

        # Pass combined events to the calendar template
        return render_template('calendar.html', events=combined_events)

    except Exception as e:
        print(f"Error loading calendar events: {e}")
        return "Error loading calendar events", 500



# format distance
def format_distance(distance_m):
    if distance_m == 0:
        return "0 km"
    distance_km = distance_m / 1000
    return f"{distance_km:.2f} km"

# Route to save trip data
@webapplication.route("/save_trip", methods=['POST'])
def save_trip():
    try:
        trip_data = request.json
        if os.path.exists(TRIPS_FILE):
            with open(TRIPS_FILE, 'r') as f:
                trips = json.load(f)
        else:
            trips = []
        
        trip_data['id'] = len(trips) + 1
        trips.append(trip_data)
        
        with open(TRIPS_FILE, 'w') as f:
            json.dump(trips, f, indent=2)
        
        return jsonify({"status": "success", "message": "Trip saved successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Route to log trips and display specific date data
@webapplication.route('/log')
def log():
    try:
        trip_date = request.args.get('date')
        
        with open(TRIPS_FILE, 'r') as f:
            trips = json.load(f)

        filtered_trips = [trip for trip in trips 
                        if trip['startTime'].split()[0] == trip_date]
        combined_coordinates = []
        for trip in filtered_trips:
            combined_coordinates.extend(trip['coordinates'])

        with open(JOURNAL_FILE, 'r') as f:
            journal_entries = json.load(f)

        journal_entry = next((entry for entry in journal_entries 
                            if entry['date'] == trip_date), None)
        
        return render_template(
            'log.html', 
            trips=filtered_trips, 
            selected_date=trip_date, 
            combined_coordinates=combined_coordinates, 
            journal_entry=journal_entry
        )
    except Exception as e:
        print(f"Error loading trips: {str(e)}")
        return render_template('log.html', trips=[], selected_date=trip_date)

# Route to save a journal entry
from datetime import datetime

@webapplication.route("/save_journal_entry", methods=['POST'])
def save_journal_entry():
    raw_date = request.form['date']
    try:
        date_obj = datetime.strptime(raw_date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d/%m/%Y")
        folder_date = date_obj.strftime("%d-%m-%Y")  # Format for folder name
    except ValueError:
        formatted_date = raw_date
        folder_date = raw_date.replace('/', '-')

    entry_text = request.form['entry']
    image = request.files.get('image', None)
    
    entry_data = {
        "date": formatted_date,
        "entry": entry_text,
        "image_path": None
    }

    if image:
        # Create date-specific folder
        date_folder = os.path.join(UPLOAD_FOLDER, folder_date)
        os.makedirs(date_folder, exist_ok=True)
        
        filename = secure_filename(image.filename)
        image_path = os.path.join(date_folder, filename)
        relative_path = os.path.join(folder_date, filename)  
        image.save(os.path.join('static/uploads', relative_path))
        entry_data["image_path"] = relative_path

    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, 'r') as f:
            journal_entries = json.load(f)
    else:
        journal_entries = []

    # Update existing entry or add new one
    existing_entry = next((entry for entry in journal_entries 
                         if entry['date'] == formatted_date), None)
    if existing_entry:
        existing_entry.update(entry_data)
    else:
        journal_entries.append(entry_data)

    with open(JOURNAL_FILE, 'w') as f:
        json.dump(journal_entries, f, indent=2)

    return redirect(url_for('journal'))

# Run the application
if __name__ == "__main__":
    webapplication.run(host="127.0.0.1", port=5000, debug=True)
