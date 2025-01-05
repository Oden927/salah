from flask import Flask, render_template, session, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from database import db, User, Game , Player , assign_roles # Importer la base de données et les modèles
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask_socketio import SocketIO, join_room, leave_room, send
from flask_socketio import emit
from datetime import datetime
import random
import os


from dotenv import load_dotenv
from threading import Lock

phase_lock = Lock()

load_dotenv()




app = Flask(__name__)
app.secret_key = 'votre_cle_secrete'  # Utilisez une clé secrète sécurisée
socketio = SocketIO(app)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'



# Configurer Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'  # Nom d'utilisateur obligatoire pour SendGrid
app.config['MAIL_PASSWORD'] = os.getenv('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = 'noreply.loupgarou@gmail.com'  # Expéditeur par défaut
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

db.init_app(app)
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
            # Créez un message avec encodage explicite
            msg = Message(
                subject="Bienvenue sur Loup-Garou",  # Sujet avec des accents
                recipients=[email],
                sender="noreply.loupgarou@gmail.com",
                charset="utf-8"  # Encodage UTF-8 explicite
            )

            # Ajouter le corps HTML encodé en UTF-8
            msg.html = render_template('email/welcome.html', username=username)

            try:
                mail.send(msg)
                flash("Votre compte a été créé. Un email de confirmation a été envoyé !", "success")
            except Exception as e:
                flash(f"Erreur lors de l'envoi de l'email : {e}", "danger")
                print(f"Erreur complète : {repr(e)}")

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
                msg = Message(
                    subject="Réinitialisation de votre mot de passe".encode('utf-8').decode('utf-8'),
                    recipients=[email],
                    charset="utf-8"
                )
                msg.body = f"""Bonjour {user.username},

                Pour réinitialiser votre mot de passe, cliquez sur le lien suivant :
                {reset_link}

                Ce lien expirera dans 1 heure.

                Si vous n'avez pas demandé cette action, veuillez ignorer cet email.
                """.encode('utf-8').decode('utf-8')
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
        max_players = int(request.form.get('max_players', 0))
        num_werewolves = int(request.form.get('num_werewolves', 0))
        num_villagers = int(request.form.get('num_villagers', 0))
        num_seer = int(request.form.get('num_seer', 0))  # Voyante
        num_sorceress = int(request.form.get('num_sorceress', 0))  # Sorcière
        num_cupid = int(request.form.get('num_cupid', 0))  # Cupidon
        num_fool = int(request.form.get('num_fool', 0))  # Fou

        # Validation des rôles
        if num_werewolves < 1 or num_villagers < 1:
            flash("Il doit y avoir au moins un Loup-Garou et un Villageois.", "danger")
            return redirect(url_for('create_game'))

        # Configuration des rôles
        config_roles = {
            "Loup-Garou": num_werewolves,
            "Villageois": num_villagers,
            "Voyante": num_seer,
            "Sorcière": num_sorceress,
            "Cupidon": num_cupid,
            "Fou": num_fool
        }

        # Créer la partie
        new_game = Game(
            name=game_name,
            max_players=max_players,
            created_by=session['user_id'],
            current_phase='waiting',
            config_roles=config_roles
        )
        db.session.add(new_game)
        db.session.commit()

        # Ajouter le créateur en tant qu'hôte et joueur
        host_player = Player(
            user_id=session['user_id'],
            game_id=new_game.id,
            role='Hôte'  # Défini comme rôle d'hôte temporaire
        )
        db.session.add(host_player)
        db.session.commit()

        flash(f"Partie '{game_name}' créée avec succès ! Vous êtes l'hôte.", "success")
        return redirect(url_for('waiting_room', game_id=new_game.id))

    return render_template('create_game.html')




def get_time_remaining(game):
    if not game.phase_start_time:
        return game.phase_duration
    elapsed_time = (datetime.utcnow() - game.phase_start_time).total_seconds()
    remaining_time = max(0, game.phase_duration - elapsed_time)
    return int(remaining_time)


@socketio.on('get_game_state')
def handle_get_game_state(data):
    game_id = data.get('game_id')
    game = Game.query.get(game_id)

    if not game:
        emit('error', {'message': "La partie n'existe pas."})
        return

    remaining_time = get_time_remaining(game)

    emit('game_state', {
        'current_phase': game.current_phase,
        'remaining_time': remaining_time,
        'players': [
            {'username': p.user.username, 'eliminated': p.eliminated}
            for p in game.players
        ]
    }, to=request.sid)


from sqlalchemy.sql import func

  

@app.route('/join_game', methods=['GET', 'POST'])
def join_game():
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour rejoindre une partie.", "danger")
        return redirect(url_for('login'))

    # Get all available games
    games = Game.query.filter(
        Game.started == False,
        Game.max_players > db.session.query(func.count(Player.id)).filter(Player.game_id == Game.id)
    ).all()

    if request.method == 'POST':
        game_id = request.form.get('game_id')

        if not game_id or not game_id.isdigit():
            flash("Aucune partie valide sélectionnée.", "danger")
            return redirect(url_for('join_game'))

        game = Game.query.get(game_id)
        if not game:
            flash("Cette partie n'existe pas.", "danger")
            return redirect(url_for('join_game'))

        # Check if game has started
        if game.started:
            flash("Cette partie a déjà commencé.", "danger")
            return redirect(url_for('join_game'))

        # Check if game is full
        current_players = Player.query.filter_by(game_id=game_id).count()
        if current_players >= game.max_players:
            flash("Cette partie est complète.", "danger")
            return redirect(url_for('join_game'))

        # Check if player is already in the game
        existing_player = Player.query.filter_by(user_id=session['user_id'], game_id=game_id).first()
        if existing_player:
            flash("Vous êtes déjà dans cette partie.", "info")
            return redirect(url_for('waiting_room', game_id=game_id))

        # Add player to game
        new_player = Player(
            user_id=session['user_id'],
            game_id=game_id,
            role='En attente'
        )
        db.session.add(new_player)
        
        try:
            db.session.commit()
            flash(f"Vous avez rejoint la partie '{game.name}'.", "success")
            
            # Notify other players via WebSocket
            socketio.emit('player_joined', {
                'username': session.get('username'),
                'game_id': game_id
            }, room=f'game_{game_id}')
            
            return redirect(url_for('waiting_room', game_id=game_id))
        except:
            db.session.rollback()
            flash("Une erreur est survenue lors de l'inscription.", "danger")
            return redirect(url_for('join_game'))

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

def get_host(self):
    return Player.query.filter_by(game_id=self.id, user_id=self.created_by).first()
def assign_new_host(self):
    # Trouver le premier joueur encore dans la partie
    new_host = Player.query.filter_by(game_id=self.id).order_by(Player.id).first()
    if new_host:
        self.created_by = new_host.user_id
        db.session.commit()


def eliminate_player(game, player):
    player.eliminated = True
    db.session.commit()

    # Vérifiez s'il a un amoureux
    if player.lover_id:
        lover = Player.query.filter_by(user_id=player.lover_id, game_id=game.id).first()
        if lover and not lover.eliminated:
            lover.eliminated = True
            db.session.commit()
            socketio.emit('lover_died', {
                'lover': lover.user.username,
                'reason': f"{player.user.username} a été éliminé(e)."
            }, room=f"game_{game.id}")
        # Émettez un événement pour notifier les clients
    socketio.emit('player_eliminated', {
        'user_id': player.user_id,
        'username': player.user.username
    }, room=f"game_{game.id}")




@app.route('/waiting_room/<int:game_id>')
def waiting_room(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("Cette partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    players = game.players
    host = game.get_host()
    is_host = session.get('user_id') == (host.user_id if host else None)

    return render_template('waiting_room.html', game=game, players=players, is_host=is_host)

@socketio.on('phase_end')
def handle_phase_end(data):
    room = data.get('room')
    game_id = room.split('_')[1]
    game = Game.query.get(game_id)

    if not game:
        emit('error', {'message': "La partie n'existe pas."})
        return

    # Déterminer la phase suivante et la notification associée
    if game.current_phase == 'night':
        game.current_phase = 'day'
        notification = "☀️ La journée commence. Les joueurs discutent."
    elif game.current_phase == 'day':
        game.current_phase = 'voting'
        notification = "🗳️ Phase de vote. Les joueurs doivent voter pour éliminer un suspect."
    elif game.current_phase == 'voting':
        game.current_phase = 'night'
        notification = "🌙 La nuit tombe. Les Loups-Garous se réveillent."

    # Mettre à jour l'heure de début de la nouvelle phase
    game.phase_start_time = datetime.utcnow()
    db.session.commit()

    # Inclure la liste des joueurs actifs pour la phase de vote
    active_players = [
        {'user_id': p.user_id, 'username': p.user.username}
        for p in game.players if not p.eliminated
    ]

    # Émettre l'événement de changement de phase avec une notification et les joueurs actifs
    socketio.emit('phase_change', {
        'game_id': game.id,
        'new_phase': game.current_phase,
        'notification': notification,
        'active_players': active_players  # Ajouter les joueurs actifs
    }, room=f"game_{game.id}")



@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    room = data.get('room')

    if not room:
        emit('error', {'message': "Salle invalide."})
        return

    # Rejoindre la room
    join_room(room)
    print(f"DEBUG: {username} a rejoint la salle {room}")

    # Personnaliser le message en fonction de la room
    if "eliminated" in room:
        message = f"{username} a rejoint la salle des éliminés."
    else:
        message = f"{username} a rejoint la partie."

    # Envoyer un message dans la room
    emit('message', {
        'username': "Système",
        'message': message,
        'timestamp': datetime.utcnow().strftime('%H:%M:%S')
    }, room=room)



@socketio.on('message')
def handle_message(data):
    room = data.get('room')
    game_id = room.split('_')[1]
    message = data.get('message')
    username = session.get('username', "Utilisateur inconnu")  # Utiliser le nom d'utilisateur de la session

    game = Game.query.get(game_id)
    player = Player.query.filter_by(user_id=session['user_id'], game_id=game_id).first()

    if not game or not player:
        emit('error', {'message': "Erreur : Partie ou joueur introuvable."})
        return

    # Vérifiez si le joueur est dans la salle des éliminés
    if "eliminated" in room and player.eliminated:
        emit('message', {
            'username': username,
            'message': message if message else "Message non disponible",
            'timestamp': datetime.utcnow().strftime('%H:%M:%S')
        }, room=room)
        return

    # Vérifiez si le joueur est éliminé dans d'autres contextes
    if player.eliminated:
        emit('error', {'message': "Vous êtes éliminé et ne pouvez pas interagir avec le chat."})
        return

    # Phase de nuit : seuls les Loups-Garous peuvent parler
    if game.current_phase == 'night' and player.role != "Loup-Garou":
        emit('error', {'message': "Vous ne pouvez pas parler pendant la nuit."})
        return

    # Émettre le message à tous les joueurs dans la salle
    emit('message', {
        'username': username,
        'message': message if message else "Message non disponible",
        'role': player.role,
        'timestamp': datetime.utcnow().strftime('%H:%M:%S')
    }, room=room)


@socketio.on('join')
def on_join(data):
    username = session.get('username', "Utilisateur inconnu")
    room = data.get('room')

    if not room:
        return

    join_room(room)
    emit('message', {
        'username': "Système",
        'message': f"{username} a rejoint la partie.",
        'timestamp': datetime.utcnow().strftime('%H:%M:%S')
    }, room=room)



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

    # Vérifier si le joueur est inscrit
    current_player = Player.query.filter_by(user_id=session['user_id'], game_id=game_id).first()
    if not current_player:
        flash("Vous n'êtes pas inscrit dans cette partie.", "danger")
        return redirect(url_for('join_game'))

    # Sérialiser les joueurs
    players = [
        {
            "id": player.id,
            "user_id": player.user_id,
            "username": player.user.username if player.user else "Utilisateur inconnu",
            "role": player.role,
            "eliminated": player.eliminated
        }
        for player in game.players
    ]

    roles = [
        {"player_id": player.user_id, "role": player.role}
        for player in game.players
    ]

    return render_template('game.html', game=game, players=players, roles=roles, player=current_player)


def check_victory(game_id):
    game = Game.query.get(game_id)
    if not game:
        return None

    # Vérifier si le Fou a été éliminé pendant la phase de vote
    eliminated_fool = Player.query.filter_by(game_id=game_id, role='Fou', eliminated=True).first()
    if eliminated_fool and game.current_phase == 'voting':
        print("DEBUG: Le Fou a gagné en étant éliminé pendant la phase de vote.")
        socketio.emit('game_over', {
            'winner': "Fou",
            'message': "Le Fou a été éliminé pendant la phase de vote et a gagné !",
            'crazy_sound': "{{ url_for('static', filename='audio/crazy.mp3') }}"
        }, room=f"game_{game_id}")
        return "Fou"

    # Identifier les joueurs encore en vie
    active_players = Player.query.filter_by(game_id=game_id, eliminated=False).all()

    # Identifier les rôles des méchants (Loups-Garous et Sorcière)
    evil_roles = ['Loup-Garou', 'Sorcière']
    evils = [player for player in active_players if player.role in evil_roles]
    non_evils = [player for player in active_players if player.role not in evil_roles and player.role != 'Fou']

    print(f"DEBUG: Evils: {len(evils)}, Non-evils: {len(non_evils)}")

    # Condition de victoire des méchants
    if len(evils) > 0 and len(non_evils) == 0:
        print("DEBUG: Méchants ont gagné")
        socketio.emit('wolves_win', {
            'message': "Les Loups-Garous et la Sorcière ont gagné la partie !",
            'sound': "{{ url_for('static', filename='audio/werewolf_win.mp3') }}"
        }, room=f"game_{game_id}")
        return "Loups-Garous et Sorcière"

    # Condition de victoire des gentils
    if len(evils) == 0:
        print("DEBUG: Gentils ont gagné")
        return "Gentils (Villageois et alliés)"

    # Pas encore de victoire
    print("DEBUG: Pas de victoire")
    return None


from threading import Timer

def end_voting(game_id):
    with app.app_context():
        game = Game.query.get(game_id)
        if not game or game.current_phase != 'day':
            print(f"La phase de jour n'est pas active ou la partie {game_id} n'existe pas.")
            return

        # Gestion des votes
        room = f"game_{game_id}"
        if room not in votes:
            votes[room] = {}

        if votes[room]:
            # Identifier le joueur avec le plus de votes
            max_votes = max(votes[room].values())
            tied_players = [user_id for user_id, vote_count in votes[room].items() if vote_count == max_votes]
            eliminated_player_id = random.choice(tied_players)

            eliminated_player = Player.query.filter_by(user_id=eliminated_player_id, game_id=game.id).first()
            if eliminated_player:
                eliminated_player.eliminated = True
                db.session.commit()

                # Émettre une notification d'élimination à tous les joueurs
                socketio.emit('player_eliminated', {
                    'eliminatedPlayer': eliminated_player.user.username,
                    'reason': "Ce joueur a été éliminé lors du vote."
                }, room=f"game_{game.id}")

                # Gérer les amoureux si applicable
                if eliminated_player.lover_id:
                    lover = Player.query.filter_by(user_id=eliminated_player.lover_id, game_id=game.id).first()
                    if lover:
                        lover.eliminated = True
                        db.session.commit()
                        socketio.emit('lover_died', {
                            'lover': lover.user.username,
                            'reason': f"{eliminated_player.user.username} a été éliminé(e)."
                        }, room=f"game_{game.id}")

        # Réinitialiser les votes
        votes[room] = {}

        # Passer à la phase suivante
        game.current_phase = 'night'
        game.phase_start_time = datetime.utcnow()
        db.session.commit()

        socketio.emit('phase_change', {
            'game_id': game.id,
            'new_phase': game.current_phase,
        }, room=f"game_{game.id}")

def schedule_phase_end(game):
    """Planifie la fin de la phase actuelle."""
    phase_duration = 60
    # Réinitialiser le temps de début de phase
    game.phase_start_time = datetime.utcnow()
    db.session.commit()

    # Planifiez la fin de la phase
    print(f"Phase {game.current_phase} planifiée pour se terminer dans {phase_duration} secondes pour le jeu {game.id}.")
    print(f"Planification de la fin de la phase '{game.current_phase}' pour le jeu {game.id}. Durée : {phase_duration}s.")
    Timer(phase_duration, end_phase, [game.id]).start()

def end_phase(game_id):
    """Passe automatiquement à la phase suivante à la fin du timer."""
    with app.app_context():
        game = Game.query.get(game_id)
        if not game:
            print(f"Game with ID {game_id} not found.")
            return

        print(f"Fin de la phase pour la partie {game_id}. Phase actuelle : {game.current_phase}")

        # Forcez la transition à la phase suivante
        transition_phase(game)



@app.route('/start_game/<int:game_id>', methods=['POST'])
def start_game(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("La partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    # Récupérer les joueurs de la partie
    players = Player.query.filter_by(game_id=game_id).all()

    # Vérifier que la configuration des rôles existe
    if not game.config_roles:
        flash("La configuration des rôles est introuvable pour cette partie.", "danger")
        return redirect(url_for('home'))

    # Assigner les rôles
    assign_roles(players, game.config_roles)
    db.session.commit()

    # Démarrer la partie
    game.started = True
    game.current_phase = 'night'  # La phase commence par la nuit
    game.phase_start_time = datetime.utcnow()  # Enregistrez l'heure de début de la phase
    db.session.commit()

    # Planifiez la fin de la phase de nuit
    schedule_phase_end(game)

    # Notifier les joueurs que la partie a commencé
    socketio.emit('start_game', {'game_id': game_id}, to=f'game_{game_id}')
    flash("La partie a démarré !", "success")
    return redirect(url_for('game_page', game_id=game_id))




@socketio.on('start_game')
def handle_start_game(data):
    game_id = data['game_id']
    game = Game.query.get(game_id)

    if not game:
        emit('error', {'message': "La partie n'existe pas."})
        return

    # Verify the user is the host
    if session['user_id'] != game.created_by:
        emit('error', {'message': "Vous n'êtes pas autorisé à démarrer cette partie."})
        return

    # Start the game
    game.started = True
    db.session.commit()

    # Emit the start_game event to all users in the room
    socketio.emit('start_game', {'game_id': game_id}, to=f'game_{game_id}')


    # Emit the event to all players in the game room

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

@app.route('/rules')
def rules():
    return render_template('rules.html')

@app.route('/leave_game', methods=['POST'])
def leave_game():
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour accéder à cette page.", "danger")
        return redirect(url_for('login'))

    player = Player.query.filter_by(user_id=session['user_id']).first()
    
    if player:
        game = Game.query.get(player.game_id)  # Récupérer la partie
        db.session.delete(player)
        db.session.commit()

        # Si l'utilisateur qui quitte est l'hôte
        if game and game.created_by == session['user_id']:
            # Trouver un nouveau joueur pour être l'hôte
            new_host = Player.query.filter_by(game_id=game.id).order_by(Player.id).first()
            if new_host:
                game.created_by = new_host.user_id
                db.session.commit()
                flash("Un nouvel hôte a été désigné.", "info")
            else:
                flash("La partie a été supprimée car aucun joueur n'est resté.", "info")
                db.session.delete(game)
                db.session.commit()

        flash("Vous avez quitté la partie avec succès.", "success")
    else:
        flash("Vous n'êtes pas dans une partie.", "danger")

    return redirect(url_for('home'))

@app.route('/game_timer/<int:game_id>')
def game_timer(game_id):
    game = Game.query.get(game_id)
    if not game or not game.started or not game.phase_start_time:
        print(f"Game {game_id} : Temps restant par défaut (300s).")
        return {"remaining_time": 300}

    current_time = datetime.utcnow()
    elapsed_seconds = (current_time - game.phase_start_time).total_seconds()
    phase_duration = {
        'night': game.night_phase_duration,
        'day': game.day_phase_duration,
        'voting': 120  # Par défaut 2 minutes pour la phase de vote
    }.get(game.current_phase, 300)  # Valeur par défaut si aucune phase ne correspond

    remaining_time = max(phase_duration - int(elapsed_seconds), 0)
    print(f"Game {game_id} : Temps restant calculé : {remaining_time}s pour la phase {game.current_phase}.")
    return {"remaining_time": remaining_time}


def transition_phase(game):
    if game.current_phase == 'voting':
        if game.id in votes:
            votes[game.id] = {}  # Réinitialisez les votes
    with phase_lock:
        if not game:
            print("Erreur : La partie est introuvable.")
            return

        # Définir la prochaine phase
        if game.current_phase == 'night':
            game.current_phase = 'day'
            notification = "☀️ La journée commence. Les joueurs discutent."
        elif game.current_phase == 'day':
            game.current_phase = 'voting'
            notification = "🗳️ Phase de vote. Les joueurs doivent voter pour éliminer un suspect."
        elif game.current_phase == 'voting':
            game.current_phase = 'night'
            notification = "🌙 La nuit tombe. Les Loups-Garous se réveillent."

        # Sauvegarder dans la base de données
        game.phase_start_time = datetime.utcnow()
        db.session.commit()
        winner = check_victory(game.id)
        if winner:
            # Notifiez tous les joueurs de la fin de la partie
            socketio.emit('game_over', {
                'winner': winner,
                'message': f"Les {winner} ont gagné la partie !"
            }, room=f"game_{game.id}")

            # Rediriger tous les joueurs vers une page d'élimination
            socketio.emit('redirect_to_elimination', {
                'message': f"Le jeu est terminé ! Les {winner} ont remporté la partie."
            }, room=f"game_{game.id}")
            return

        # Planifiez la prochaine phase
        schedule_phase_end(game)

        # Émettez un événement Socket.IO
        socketio.emit('phase_change', {
            'game_id': game.id,
            'new_phase': game.current_phase,
            'notification': notification
        }, room=f"game_{game.id}")
        

        print(f"Transition de phase pour la partie {game.id}. Nouvelle phase : {game.current_phase}")





@app.route('/game/<int:game_id>/next_phase', methods=['POST'])
def next_phase(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("La partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    # Vérifiez si la phase actuelle est encore en cours
    elapsed_time = (datetime.utcnow() - game.phase_start_time).total_seconds()
    phase_duration = {
        'night': game.night_phase_duration,
        'day': game.day_phase_duration,
        'voting': 120  # Par défaut 2 minutes pour la phase de vote
    }.get(game.current_phase, 120)

    if elapsed_time < phase_duration:
        print(f"Phase {game.current_phase} encore en cours pour la partie {game_id}. Ignorer l'appel.")
        return "", 429  # Too Many Requests

    # Passer à la phase suivante
    transition_phase(game)
    flash(f"La phase est maintenant : {game.current_phase}", "success")
    return redirect(url_for('game_page', game_id=game_id))



def get_next_phase(current_phase):
    phases = ['night', 'voting', 'day']
    next_phase_index = (phases.index(current_phase) + 1) % len(phases)
    return phases[next_phase_index]





def end_night_phase(game_id):
    with app.app_context():
        game = Game.query.get(game_id)
        if not game:
            print(f"Game with ID {game_id} not found.")
            return

        if game.current_phase == 'night':
            print(f"Ending night phase for game {game_id}.")
            transition_phase(game)  # Passe à la phase de jour

@socketio.on('werewolf_vote')
def handle_werewolf_vote(data):
    room = data.get('room')
    victim_id = data.get('victimId')
    game_id = room.split('_')[1]
    game = Game.query.get(game_id)

    print(f"DEBUG: room={room}, victim_id={victim_id}, game_id={game_id}")

    if not game:
        print("DEBUG: La partie n'existe pas.")
        emit('error', {'message': "La partie n'existe pas."}, to=request.sid)
        return

    if game.current_phase != 'night':
        print(f"DEBUG: Phase actuelle: {game.current_phase}. Les votes sont uniquement autorisés pendant la phase de nuit.")
        emit('error', {'message': "Les votes des Loups-Garous ne sont autorisés que pendant la phase de nuit."}, to=request.sid)
        return

    # Initialisation des votes si nécessaire
    if room not in votes:
        votes[room] = {}

    # Vérifiez si le joueur a déjà voté
    voter_id = session.get('user_id')
    if voter_id in votes[room]:
        emit('error', {'message': "Vous avez déjà voté."}, to=request.sid)
        return

    # Ajout du vote pour la victime
    votes[room][voter_id] = victim_id
    print(f"DEBUG: Votes actuels : {votes[room]}")

    # Notifiez uniquement le joueur qui a voté
    victim = Player.query.filter_by(user_id=victim_id, game_id=game.id).first()
    if victim:
        emit('notification', {
            'message': f"Vous avez voté pour éliminer {victim.user.username}."
        }, to=request.sid)

    # Vérifiez si tous les Loups-Garous actifs ont voté
    werewolves = Player.query.filter_by(game_id=game.id, role='Loup-Garou', eliminated=False).all()
    if len(votes[room]) == len(werewolves):
        # Comptez les votes pour désigner la victime
        vote_counts = {}
        for _, vote in votes[room].items():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        # Trouvez la victime avec le plus de votes
        max_votes = max(vote_counts.values())
        tied_players = [user_id for user_id, count in vote_counts.items() if count == max_votes]
        selected_victim_id = random.choice(tied_players)

        # Éliminez la victime
        victim = Player.query.filter_by(user_id=selected_victim_id, game_id=game.id).first()
        if victim:
            eliminate_player(game, victim)
            print(f"DEBUG: Victime éliminée : {victim.user.username}")

            # Notifiez tous les joueurs de l'élimination
            socketio.emit('player_eliminated', {
                'eliminatedPlayer': victim.user.username,
                'reason': "Les Loups-Garous ont décidé de l'éliminer."
            }, room=f"game_{game_id}")

        # Réinitialisation des votes
        votes[room] = {}

        # Transition à la phase suivante
        transition_phase(game)



@app.route('/seer_action/<int:game_id>', methods=['POST'])
def seer_action(game_id):
    if 'user_id' not in session:
        flash("Vous devez être connecté pour effectuer cette action.", "danger")
        return redirect(url_for('login'))

    player = Player.query.filter_by(user_id=session['user_id'], game_id=game_id).first()

    # Vérifier si l'utilisateur est la Voyante
    if not player or player.role != "Voyante":
        flash("Vous n'êtes pas autorisé à utiliser cette action.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    # Vérifier si c'est la phase de nuit
    game = Game.query.get(game_id)
    if game.current_phase != 'night':
        flash("Vous ne pouvez utiliser votre pouvoir que pendant la nuit.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    # Vérifier si la voyante a déjà utilisé son pouvoir cette nuit
    if player.action_used:
        flash("Vous avez déjà utilisé votre pouvoir cette nuit.", "warning")
        return redirect(url_for('game_page', game_id=game_id))

    # Récupérer l'ID du joueur sélectionné
    target_id = request.form.get('target_id')
    target_player = Player.query.filter_by(user_id=target_id, game_id=game_id).first()

    if not target_player:
        flash("Le joueur sélectionné n'existe pas.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    # Enregistrer que l'action a été utilisée
    player.action_used = True
    db.session.commit()

    # Émettre un événement pour annoncer le rôle
    role_message = f"La Voyante a inspecté {target_player.user.username}, son rôle est : {target_player.role}."
    socketio.emit('seer_announcement', {
        'message': role_message,
        'game_id': game_id
    }, room=f'game_{game_id}')

    # Retourner le rôle au joueur (optionnel)
    flash(f"Le rôle de {target_player.user.username} est : {target_player.role}.", "info")
    return redirect(url_for('game_page', game_id=game_id))


@socketio.on('seer_action')
def handle_seer_action(data):
    game_id = data['game_id']
    target_id = data['target_id']
    game = Game.query.get(game_id)
    target_player = Player.query.filter_by(user_id=target_id, game_id=game_id).first()

    if game and target_player:
        emit('seer_result', {
            'username': target_player.user.username,
            'role': target_player.role
        }, room=f'game_{game_id}')


@app.route('/test_active_players/<int:game_id>')
def test_active_players(game_id):
    game = Game.query.get(game_id)
    if not game:
        return {"error": "Game not found"}, 404

    active_players = [
        {'user_id': p.user_id, 'username': p.user.username}
        for p in game.players if not p.eliminated
    ]

    return {"game_id": game.id, "active_players": active_players}

votes = {}  # Dictionnaire global pour stocker les votes par partie

@socketio.on('vote')
def handle_vote(data):
    voted_user_id = data.get('votedUserId')  # ID du joueur voté
    room = data.get('room')  # Salle actuelle (lié au jeu)

    if not room or not voted_user_id:
        emit('error', {'message': "Vote ou salle invalide."})
        return

    # Récupérer la partie associée
    game_id = room.split('_')[1]
    game = Game.query.get(game_id)

    # Vérifiez que nous sommes en phase de vote
    if game.current_phase != 'voting':
        emit('error', {'message': "Les votes ne sont autorisés que pendant la phase de vote."})
        return

    # Initialisez les votes si nécessaire
    if room not in votes:
        votes[room] = {}

    # Ajoutez ou mettez à jour le vote
    votes[room][voted_user_id] = votes[room].get(voted_user_id, 0) + 1

    # Vérifiez si tous les joueurs actifs ont voté
    active_players = [player for player in game.players if not player.eliminated]
    if len(votes[room]) == len(active_players):
        # Trouvez le joueur avec le plus de votes
        max_votes = max(votes[room].values())
        tied_players = [user_id for user_id, count in votes[room].items() if count == max_votes]
        eliminated_player_id = random.choice(tied_players)

        # Marquer le joueur comme éliminé
        eliminated_player = Player.query.filter_by(user_id=eliminated_player_id, game_id=game.id).first()
        if eliminated_player:
            eliminate_player(game, eliminated_player)

            # Si le joueur éliminé est le Fou, il gagne
            if eliminated_player.role == "Fou" and game.current_phase == "voting":
                socketio.emit('fool_win', {
                    'message': "Le Fou a été éliminé et a gagné la partie !",
                    'crazy_sound': "{{ url_for('static', filename='audio/crazy.mp3') }}"
                }, room=room)
                return

            # Notifiez tous les joueurs de l'élimination
            socketio.emit('vote_result', {
                'eliminatedPlayer': eliminated_player.user.username
            }, room=room)

        # Réinitialisez les votes
        votes[room] = {}

        # Passez à la phase suivante
        transition_phase(game)

        # Vérifiez les conditions de victoire après l'élimination
        winner = check_victory(game_id)
        if winner:
            socketio.emit('game_over', {
                'winner': winner,
                'message': f"Les {winner} ont gagné la partie !"
            }, room=room)
            return



@socketio.on('choose_victim')
def choose_victim(data):
    game_id = data.get('game_id')
    victim_id = data.get('victim_id')
    game = Game.query.get(game_id)

    if not game or game.current_phase != 'night':
        emit('error', {'message': "La phase de nuit n'est pas active."})
        return

    # Récupérer les joueurs actifs
    active_players = Player.query.filter_by(game_id=game_id, eliminated=False).all()

    # Vérifiez si la victime est active
    if victim_id not in [player.user_id for player in active_players]:
        emit('error', {'message': "La victime sélectionnée est déjà éliminée."})
        return

    # Marquer la victime comme éliminée
    victim = Player.query.filter_by(user_id=victim_id, game_id=game_id).first()
    if victim:
        victim.eliminated = True
        db.session.commit()

        # Passez à la phase suivante (jour)
        transition_phase(game)

        
@app.route('/werewolf_action/<int:game_id>', methods=['POST'])
def werewolf_action(game_id):
    game = Game.query.get(game_id)
    player = Player.query.filter_by(user_id=session['user_id'], game_id=game_id).first()

    if not game or not player or player.role != "Loup-Garou":
        flash("Action non autorisée.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    if game.current_phase != 'night':
        flash("Vous ne pouvez agir que pendant la nuit.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    # Enregistrez la victime choisie
    target_id = request.form.get('target_id')
    target_player = Player.query.filter_by(user_id=target_id, game_id=game_id).first()

    if not target_player or target_player.eliminated:
        flash("La cible est invalide ou déjà éliminée.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    # Sauvegardez la cible dans le jeu
    game.target_id = target_id
    db.session.commit()
    # Vérifiez les conditions de victoire
    winner = check_victory(game_id)
    if winner:
        socketio.emit('game_over', {
            'winner': winner,
            'message': f"Les {winner} ont gagné la partie !"
        }, room=f"game_{game_id}")
        return redirect(url_for('home'))  # Rediriger tous les joueurs à la fin de la partie


    # Notifiez les Loups-Garous de la sélection
    socketio.emit('werewolf_action', {
        'victim': target_player.user.username,
        'timestamp': datetime.utcnow().strftime('%H:%M:%S')
    }, room=f'werewolf_chat_{game_id}')

    flash(f"{target_player.user.username} a été choisi comme cible.", "success")
    return redirect(url_for('game_page', game_id=game_id))


@app.route('/sorceress_action/<int:game_id>', methods=['POST'])
def sorceress_action(game_id):
    game = Game.query.get(game_id)
    player = Player.query.filter_by(user_id=session['user_id'], game_id=game_id).first()

    if not player or player.role != "Sorcière":
        flash("Vous n'êtes pas autorisé à effectuer cette action.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    action = request.form.get('action')  # 'heal' ou 'poison'
    target_id = request.form.get('target_id')

    if action == 'heal':
        # Vérifiez que la potion de guérison n'a pas encore été utilisée
        if player.potion_heal_used:
            flash("Vous avez déjà utilisé votre potion de guérison.", "warning")
            return redirect(url_for('game_page', game_id=game_id))

        # Sauvez le joueur éliminé
        target_player = Player.query.filter_by(user_id=target_id, game_id=game_id).first()
        if target_player and target_player.eliminated:
            target_player.eliminated = False
            player.potion_heal_used = True  # Marquez la potion comme utilisée
            db.session.commit()

            # Notification
            socketio.emit('sorceress_action', {
                'message': f"{target_player.user.username} a été sauvé(e) par la Sorcière.",
                'action': 'heal'
            }, room=f"game_{game_id}")
            flash(f"Vous avez sauvé {target_player.user.username}.", "success")

    elif action == 'poison':
        # Vérifiez que la potion de poison n'a pas encore été utilisée
        if player.potion_poison_used:
            flash("Vous avez déjà utilisé votre potion de poison.", "warning")
            return redirect(url_for('game_page', game_id=game_id))

        # Empoisonnez le joueur
        target_player = Player.query.filter_by(user_id=target_id, game_id=game_id).first()
        if target_player and not target_player.eliminated:
            eliminate_player(game, target_player)  # Utilisez la fonction centrale d'élimination
            player.potion_poison_used = True  # Marquez la potion comme utilisée
            db.session.commit()

            # Notification
            socketio.emit('sorceress_action', {
                'message': f"{target_player.user.username} a été empoisonné(e) par la Sorcière.",
                'action': 'poison'
            }, room=f"game_{game_id}")
            flash(f"Vous avez empoisonné {target_player.user.username}.", "danger")

    else:
        flash("Action non autorisée ou invalide.", "danger")

    # Vérifiez les conditions de victoire après l'action
    winner = check_victory(game_id)
    if winner:
        socketio.emit('game_over', {
            'winner': winner,
            'message': f"Les {winner} ont gagné la partie !"
        }, room=f"game_{game_id}")
        return redirect(url_for('home'))

    return redirect(url_for('game_page', game_id=game_id))






@app.route('/cupid_action/<int:game_id>', methods=['POST'])
def cupid_action(game_id):
    game = Game.query.get(game_id)
    player = Player.query.filter_by(user_id=session['user_id'], game_id=game_id).first()

    # Vérifier si le joueur est Cupidon
    if not player or player.role != "Cupidon":
        flash("Vous n'êtes pas autorisé à effectuer cette action.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    # Vérifier si Cupidon a déjà utilisé son pouvoir
    if player.action_used:
        flash("Vous avez déjà utilisé votre pouvoir.", "warning")
        return redirect(url_for('game_page', game_id=game_id))

    # Récupérer les joueurs choisis
    lover1_id = request.form.get('lover1_id')
    lover2_id = request.form.get('lover2_id')

    if not lover1_id or not lover2_id or lover1_id == lover2_id:
        flash("Sélection invalide. Veuillez choisir deux joueurs différents.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    lover1 = Player.query.filter_by(user_id=lover1_id, game_id=game_id).first()
    lover2 = Player.query.filter_by(user_id=lover2_id, game_id=game_id).first()

    if not lover1 or not lover2:
        flash("Un ou plusieurs joueurs sélectionnés sont invalides.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    # Lier les amoureux
    lover1.lover_id = lover2.user_id
    lover2.lover_id = lover1.user_id

    # Marquer l'action de Cupidon comme utilisée et changer son rôle en Villageois
    player.action_used = True
    player.role = "Villageois"
    db.session.commit()

    # Envoyer une notification à Cupidon
    flash(f"{lover1.user.username} et {lover2.user.username} sont maintenant amoureux !", "success")

    # Émettre une notification publique via Socket.IO
    socketio.emit('cupid_announcement', {
        'message': f"Cupidon a uni {lover1.user.username} et {lover2.user.username} !",
        'game_id': game_id
    }, room=f'game_{game_id}')

    return redirect(url_for('game_page', game_id=game_id))



@app.route('/eliminated/<int:game_id>')
def eliminated_page(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash("Cette partie n'existe pas.", "danger")
        return redirect(url_for('home'))

    # Vérifier si le joueur est éliminé
    player = Player.query.filter_by(user_id=session['user_id'], game_id=game_id).first()
    if not player or not player.eliminated:
        flash("Vous n'êtes pas autorisé à accéder à cette page.", "danger")
        return redirect(url_for('game_page', game_id=game_id))

    # Récupérer les joueurs éliminés de cette partie
    eliminated_players = Player.query.filter_by(game_id=game_id, eliminated=True).all()

    return render_template('eliminated.html', game=game, eliminated_players=eliminated_players)






# Créer la base de données si elle n'existe pas encore
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, debug=True)



if __name__ == '__main__':
    app.run(debug=True)
