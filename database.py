import bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def __repr__(self):
        return f'<User {self.username}>'

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    max_players = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    started = db.Column(db.Boolean, default=False)
    players = db.relationship('Player', backref='game', cascade="all, delete-orphan", lazy=True)
    discussion_start_time = db.Column(db.DateTime, nullable=True)
    # Relation avec les joueurs
    players = db.relationship('Player', backref='game', lazy=True)



    def get_host(self):
        # Vérifiez les joueurs et retournez le premier joueur comme hôte
        first_player = Player.query.filter_by(game_id=self.id).order_by(Player.id).first()
        print(f"First player for Game {self.id}: {first_player.user_id if first_player else 'None'}")
        return first_player
    
    def __repr__(self):
        return f'<Game {self.name}>'




class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    user = db.relationship('User', backref='players', lazy=True)  # Relation avec User

    def __repr__(self):
        return f'<Player User: {self.user_id} in Game: {self.game_id}>'
    
import random

def assign_roles(players):
    roles = ['Loup-Garou', 'Voyante', 'Villageois']  # Exemple de rôles
    role_distribution = random.choices(roles, k=len(players))
    
    assigned_roles = []
    for player, role in zip(players, role_distribution):
        assigned_roles.append({'player_id': player.user_id, 'role': role})
    
    return assigned_roles



class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)

    # Relations
    user = db.relationship('User', backref=db.backref('messages', lazy=True))
    game = db.relationship('Game', backref=db.backref('messages', lazy=True))
