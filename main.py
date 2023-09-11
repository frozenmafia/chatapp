from flask import Flask, render_template, request , redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS  # Import CORS

app  = Flask(__name__)

app.secret_key = 'secret key'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '123qwe123qwe'
app.config['MYSQL_DB'] = 'flasklogin'


mysql = MySQL(app)
socketio = SocketIO(app)
CORS(app)


def get_active_users(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    sql_query = "SELECT id, username FROM users WHERE is_active = true AND id != % s"
    cursor.execute(sql_query,(id,))
    active_users = cursor.fetchall()
    return active_users
    # mysql.connection.commit()
    
@app.route('/')
@app.route('/login', methods = ['GET','POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password =request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users where username = % s and password = % s',(username, password,))
        account = cursor.fetchone()

        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            msg = 'Logged in successfully !'
            return redirect(url_for('chats', id = account['id']))
        
    elif request.method == 'GET':
        print(request.args)
        username = request.args.get('username')
        password = request.args.get('password')
        print(username, password)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users where username = % s and password = % s',(username, password,))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
    
            msg = 'Logged in successfully !'
            return redirect(url_for('chats', id = account['id']))


    return render_template('login.html', msg = msg)

@app.route('/logout')
def logout():
    id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('UPDATE users SET is_active = %s where id=%s',(False,id))
    mysql.connection.commit()
    session.pop('id', None)  # Remove the 'id' key from the session
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''

    if request.method == 'POST':
        username = request.form['username']
        print(request.form)
        # print(request.form['interests[]'])
        interests = []
        for key, value in request.form.items():
            if key.startswith('interests'):
                parts = key.split('[')
                index = int(parts[1].split(']')[0])
                field = parts[2].split(']')[0]

                if index >= len(interests):
                    interests.append({})

                if field == 'name':
                    interests[index]['name'] = value
                elif field == 'level':
                    interests[index]['level'] = int(value)
        # print(interests)
        # Check if the username already exists
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()
        
        if account:
            msg = 'Username already exists. Please choose another.'
        else:
            # Assuming you've already validated and hashed the password on the frontend
            interest_ids = []
            interest_id = None
            for interest_data in interests:
                interest_name = interest_data['name']
                cursor.execute('SELECT id FROM interests WHERE name = %s', (interest_name,))
                existing_interest = cursor.fetchone()
                if existing_interest:
                    interest_ids.append(existing_interest['id'])
                else:
                    cursor.execute('INSERT INTO interests (name) VALUES (%s)', (interest_name,))
                    interest_id = cursor.lastrowid
                    interest_ids.append(interest_id)

            password = request.form['password']
            email = request.form['email']
            # Insert the new user into the database
            cursor.execute('INSERT INTO users (username, password, email) VALUES (%s, %s, %s)', (username, password,email))

            user_id = cursor.lastrowid

        # Step 3: Insert the user's interests and levels into the 'user_interest' table
            for interest_id, interest_data in zip(interest_ids, interests):
                level = interest_data['level']
                cursor.execute('INSERT INTO user_interests (user_id, interest_id, interest_level) VALUES (%s, %s, %s)',
                            (user_id, interest_id, level))
            
            mysql.connection.commit()
            msg = 'You have successfully registered!'
            cursor.close()
            return redirect(url_for('login',username = username, password = password))
    
    return render_template('register.html', msg=msg)

@app.route('/check_username', methods=['POST'])
def check_username():
    username = request.form['username']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    account = cursor.fetchone()
    
    if account:
        return jsonify({'message': 'Username already exists. Please choose another.', 'valid': False})
    else:
        return jsonify({'message': '', 'valid': True})

@app.route('/chats/<int:id>')
def chats(id):
    id = session['id']
    username = session['username']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('UPDATE users SET is_active = %s where id=%s',(True,id))
    mysql.connection.commit()
    active_users = get_active_users(id)
    print(active_users)
    return render_template('chats.html', username = username,active_users=active_users)


@socketio.on('connect')
def handle_connect():
    join_room('global-chat-room')
    user_id = session.get('id')

    if user_id:
        private_chat_room = f'user-{user_id}'
        join_room(private_chat_room)

@socketio.on('disconnect')
def handle_disconnect():
    # Leave the global chat room when a user disconnects
    leave_room('global-chat-room')


@socketio.on('private-message')
def handle_private_message(data):
    recipient_id = data['recipientId']
    message = data['message']

    # Send the private message to the recipient's private chat room
    private_chat_room = f'user-{recipient_id}'
    emit('private-message', {'message': message}, room=private_chat_room)

@socketio.on('message')
def handle_message(data):
    recipient_id = data['recipientId']  # Use recipient's ID instead of username
    message = data['message']

    sender_id = session.get('id') 
    # Here, you can save the message to a database and handle sending it to the recipient
    room_id = recipient_id
    emit('message', {'message': message, 'senderId': sender_id}, room = room_id)


if __name__ == '__main__':
    socketio.run(app,debug=True)