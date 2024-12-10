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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relation avec les joueurs
    players = db.relationship('Player', backref='game', lazy=True)

    def __repr__(self):
        return f'<Game {self.name}>'


class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)

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

