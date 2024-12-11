from flask import Flask, render_template, session, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from database import db, User, Game , Player , assign_roles # Importer la base de données et les modèles
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask_socketio import SocketIO, join_room, leave_room, send
from flask_socketio import emit
from datetime import datetime
import os



app = Flask(__name__)
app.secret_key = 'votre_cle_secrete'  # Utilisez une clé secrète sécurisée
socketio = SocketIO(app)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'



# Configurer Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'  # Nom d'utilisateur obligatoire pour SendGrid
app.config['MAIL_PASSWORD'] = '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'  # Clé API générée sur SendGrid
app.config['MAIL_DEFAULT_SENDER'] = 'loupgarou92700@gmail.com'  # Expéditeur par défaut
# Configuration de la base de données
if 'DATABASE_URL' in os.environ:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

mail = Mail(app)





# Configuration de la base de données SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)  # Initialiser la base de données avec l'application Flask
migrate = Migrate(app, db)  # Initialiser Flask-Migrate avec Flask et SQLAlchemy


@app.route('/')
def home():
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour accéder à cette page.", "danger")
        return redirect(url_for('login'))

    print(f"User ID: {session['user_id']}")  # Vérifiez si l'utilisateur est bien connecté

    games = Game.query.filter_by(created_by=session['user_id']).all()
    print("Games récupérés :", games)  # Débogage

    current_user_game = None
    player = Player.query.filter_by(user_id=session['user_id']).first()
    if player:
        current_user_game = Game.query.get(player.game_id)
    print("Partie actuelle de l'utilisateur :", current_user_game)  # Débogage

    return render_template('home.html', games=games, current_user_game=current_user_game)




# Créer la base de données si elle n'existe pas encore
with app.app_context():
    db.create_all()



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')  # Peut être un email ou un nom d'utilisateur
        password = request.form.get('password')

        # Rechercher l'utilisateur par email ou nom d'utilisateur
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username  # Ajouter le pseudo dans la session
            flash("Connexion réussie !", "success")
            return redirect(url_for('home'))
        else:
            flash("Identifiant ou mot de passe incorrect.", "danger")
    return render_template('login.html')




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Vérifier si les mots de passe correspondent
        if password != confirm_password:
            return render_template('register.html', error="Les mots de passe ne correspondent pas.")
        
        # Vérifier si l'utilisateur ou l'email existe déjà
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            return render_template('register.html', error="Le nom d'utilisateur ou l'email est déjà pris.")
        
        # Ajouter l'utilisateur à la base de données
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Envoyer un email de confirmation
        try:
            msg = Message("Bienvenue sur Loup-Garou", recipients=[email])
            msg.html = render_template('email/welcome.html', username=username)
            mail.send(msg)
            flash("Votre compte a été créé. Un email de confirmation a été envoyé !", "success")
        except Exception as e:
            flash("Votre compte a été créé, mais l'envoi de l'email a échoué.", "danger")
            print(f"Erreur d'envoi de l'email : {e}")

        return redirect(url_for('login'))  # Rediriger vers la page de connexion après inscription
    return render_template('register.html')



@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)  # Supprimer le pseudo de la session
    flash("Vous avez été déconnecté.", "success")
    return redirect(url_for('home'))




# Initialiser un sérialiseur sécurisé pour générer des jetons
serializer = URLSafeTimedSerializer(app.secret_key)

def generate_reset_token(user_id, expires_sec=3600):  # 3600 sec = 1 heure
    return serializer.dumps(user_id, salt='password-reset-salt')

def verify_reset_token(token, expires_sec=3600):
    try:
        user_id = serializer.loads(token, salt='password-reset-salt', max_age=expires_sec)
    except Exception:
        return None  # Jeton invalide ou expiré
    return user_id



@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            # Générer un jeton de réinitialisation
            reset_token = generate_reset_token(user.id)
            reset_link = url_for('reset_password', token=reset_token, _external=True)

            # Envoyer un email avec le lien de réinitialisation
            try:
                msg = Message("Réinitialisation de votre mot de passe", recipients=[email])
                msg.body = f"Bonjour {user.username},\n\nPour réinitialiser votre mot de passe, cliquez sur le lien suivant :\n{reset_link}\n\nCe lien expirera dans 1 heure.\n\nSi vous n'avez pas demandé cette action, veuillez ignorer cet email."
                mail.send(msg)
                flash("Un email de réinitialisation a été envoyé !", "success")
            except Exception as e:
                flash("Erreur lors de l'envoi de l'email. Veuillez réessayer.", "danger")
                print(f"Erreur d'envoi de l'email : {e}")
        else:
            flash("Aucun utilisateur trouvé avec cet email.", "danger")

    return render_template('forgot.html')




@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user_id = verify_reset_token(token)  # Vérifier le jeton
    if not user_id:
        flash("Le lien de réinitialisation est invalide ou a expiré.", "danger")
        return redirect(url_for('forgot'))

    user = User.query.get(user_id)  # Trouver l'utilisateur par ID
    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for('forgot'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Vérifier si les mots de passe correspondent
        if new_password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return redirect(url_for('reset_password', token=token))

        # Mettre à jour le mot de passe
        user.set_password(new_password)
        db.session.commit()
        flash("Votre mot de passe a été mis à jour avec succès !", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html', user=user)


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour accéder à cette page.", "danger")
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/create_game', methods=['GET', 'POST'])
def create_game():
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour créer une partie.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        game_name = request.form.get('game_name')
        max_players = request.form.get('max_players')

        # Vérifiez que les données sont valides
        if not game_name or not max_players.isdigit() or int(max_players) < 2:
            flash("Veuillez entrer un nom de partie valide et un nombre de joueurs supérieur à 2.", "danger")
            return redirect(url_for('create_game'))

        # Créer une nouvelle partie
        new_game = Game(
            name=game_name,
            max_players=int(max_players),
            created_by=session['user_id']  # Associer l'hôte
        )
        db.session.add(new_game)
        db.session.commit()

        flash(f"Partie '{game_name}' créée avec succès ! Vous êtes l'hôte.", "success")
        return redirect(url_for('home'))

    return render_template('create_game.html')

@app.route('/join_game', methods=['GET', 'POST'])
def join_game():
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour rejoindre une partie.", "danger")
        return redirect(url_for('login'))

    # Récupérer les parties non commencées
    games = Game.query.filter_by(started=False).all()

    if request.method == 'POST':
        game_id = request.form.get('game_id')

        # Validation de game_id
        if not game_id or not game_id.isdigit():
            flash("Aucune partie valide sélectionnée.", "danger")
            return redirect(url_for('join_game'))

        game = Game.query.get(game_id)
        if not game:
            flash("Cette partie n'existe pas.", "danger")
            return redirect(url_for('join_game'))

        # Vérifier si l'utilisateur est déjà inscrit dans une partie
        existing_player = Player.query.filter_by(user_id=session['user_id']).first()
        if existing_player:
            if existing_player.game_id == game_id:
                flash("Vous êtes déjà inscrit dans cette partie.", "info")
                return redirect(url_for('waiting_room', game_id=game_id))
            else:
                flash("Vous êtes déjà inscrit dans une autre partie.", "danger")
                return redirect(url_for('home'))

        # Vérifier si la partie est complète
        if len(game.players) >= game.max_players:
            flash("Cette partie est déjà complète.", "info")
            return redirect(url_for('waiting_room', game_id=game_id))

        # Ajouter le joueur à la partie
        new_player = Player(user_id=session['user_id'], game_id=game_id)
        db.session.add(new_player)
        db.session.commit()

        flash(f"Vous avez rejoint la partie '{game.name}'.", "success")
        return redirect(url_for('waiting_room', game_id=game_id))

    return render_template('join_game.html', games=games)



@app.route('/clean_players')
def clean_players():
    players = Player.query.all()
    for player in players:
        game = Game.query.get(player.game_id)
        if not game:
            db.session.delete(player)
    db.session.commit()
    flash("Données des joueurs nettoyées.", "info")
    return redirect(url_for('home'))

@app.route('/clean_database')
def clean_database():
    players = Player.query.all()
    for player in players:
        if not Game.query.get(player.game_id):
            db.session.delete(player)
    db.session.commit()
    flash("Base de données nettoyée des joueurs fantômes.", "info")
    return redirect(url_for('home'))



@app.route('/waiting_room/<int:game_id>')
def waiting_room(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("Cette partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    players = game.players
    host = game.get_host()

    # Débogage pour vérifier la session utilisateur
    print(f"Session User ID: {session.get('user_id')}, Host ID: {host.id if host else 'None'}")

    # Vérifiez si l'utilisateur est l'hôte
    is_host = session.get('user_id') == (host.id if host else None)

    return render_template('waiting_room.html', game=game, players=players, is_host=is_host)


# Gestion des messages en temps réel avec SocketIO
@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    send(f"{username} a rejoint la salle.", to=room)


@socketio.on('message')
def handle_message(data):
    print("Données reçues du client :", data)  # Vérifiez les données envoyées par le client

    # Données attendues
    username = data.get('username', 'Utilisateur inconnu')
    message = data.get('message', 'Message non disponible')
    room = data.get('room', None)

    if room:
        emit('message', {
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }, room=room)
    else:
        print("Erreur : room non spécifié.")


@socketio.on('leave')
def handle_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    send(f"{username} a quitté la salle.", to=room)


@app.route('/game/<int:game_id>')
def game_page(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("Cette partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    # Sérialiser les joueurs pour le frontend
    players = [
        {
            "id": player.id,
            "user_id": player.user_id,
            "username": player.user.username if player.user else "Utilisateur inconnu"
        }
        for player in game.players
    ]

    # Exemple de rôles (assurez-vous que vos rôles sont également sérialisables)
    roles = [
        {"player_id": role.player_id, "role": role.role}
        for role in game.roles
    ] if hasattr(game, "roles") else []

    return render_template('game.html', game=game, players=players, roles=roles)


votes = {}  # Dictionnaire pour stocker les votes

@socketio.on('vote')
def handle_vote(data):
    voted_user_id = data.get('votedUserId')
    room = data.get('room')

    if room not in votes:
        votes[room] = {}

    if voted_user_id in votes[room]:
        votes[room][voted_user_id] += 1
    else:
        votes[room][voted_user_id] = 1

    # Vérifiez si tous les joueurs ont voté
    game = Game.query.filter_by(id=room).first()
    if len(votes[room]) == len(game.players):
        # Trouver le joueur avec le plus de votes
        eliminated_player_id = max(votes[room], key=votes[room].get)
        eliminated_player = User.query.get(eliminated_player_id)

        # Supprimez le joueur de la partie
        Player.query.filter_by(user_id=eliminated_player_id, game_id=room).delete()
        db.session.commit()

        # Notifiez tous les joueurs de l'élimination
        socketio.emit('vote_result', {
            'eliminatedPlayer': eliminated_player.username
        }, room=room)

        # Réinitialisez les votes
        votes[room] = {}

@app.route('/start_game/<int:game_id>', methods=['POST'])
def start_game(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("Cette partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    # Débogage : Affichez l'hôte actuel
    host = game.get_host()
    print(f"Host ID: {host.id if host else 'None'}, Session User ID: {session.get('user_id')}")

    # Vérifiez l'accès pour démarrer
    if not host or session['user_id'] != host.id:
        flash("Vous n'êtes pas autorisé à démarrer cette partie.", "danger")
        return redirect(url_for('waiting_room', game_id=game_id))

    # Démarrez la partie
    game.started = True
    db.session.commit()

    flash("La partie a commencé !", "success")
    return redirect(url_for('game_page', game_id=game_id))



@socketio.on('start_game')
def handle_start_game(data):
    game_id = data['game_id']
    game = Game.query.get(game_id)

    # Vérifiez que l'utilisateur est l'hôte
    if session['user_id'] != game.created_by:
        emit('error', {'message': "Vous n'êtes pas autorisé à démarrer cette partie."})
        return

    # Démarrer la partie
    game.started = True
    db.session.commit()

    emit('game_started', {'game_id': game_id}, broadcast=True, to=f"game_{game_id}")

@app.route('/delete_game/<int:game_id>', methods=['POST'])
def delete_game(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("La partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    # Vérifiez si l'utilisateur est l'hôte
    if session['user_id'] != game.created_by:
        flash("Vous n'êtes pas autorisé à supprimer cette partie.", "danger")
        return redirect(url_for('home'))

    # Supprimez les joueurs associés à la partie
    Player.query.filter_by(game_id=game_id).delete()

    # Supprimez la partie
    db.session.delete(game)
    db.session.commit()

    flash("La partie a été supprimée.", "success")
    return redirect(url_for('home'))

@app.route('/remove_players_from_game/<int:game_id>', methods=['POST'])
def remove_players_from_game(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("La partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    # Supprimez les joueurs associés à la partie
    Player.query.filter_by(game_id=game_id).delete()
    db.session.commit()

    flash("Tous les joueurs ont été retirés de la partie.", "success")
    return redirect(url_for('home'))


@app.route('/leave_game', methods=['POST'])
def leave_game():
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour accéder à cette page.", "danger")
        return redirect(url_for('login'))

    player = Player.query.filter_by(user_id=session['user_id']).first()
    if player:
        db.session.delete(player)
        db.session.commit()
        flash("Vous avez quitté la partie avec succès.", "success")
    else:
        flash("Vous n'êtes pas dans une partie.", "danger")

    return redirect(url_for('home'))




if __name__ == '__main__':
    socketio.run(app, debug=True)



if __name__ == '__main__':
    app.run(debug=True)
