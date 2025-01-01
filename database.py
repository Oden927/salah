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
    discussion_start_time = db.Column(db.DateTime, nullable=True)
    target_id = db.Column(
        db.Integer,
        db.ForeignKey('player.id', use_alter=True, name="fk_game_target_id"),
        nullable=True
    )
    current_phase = db.Column(db.String(50), default='night')
    phase_start_time = db.Column(db.DateTime, nullable=True)
    day_phase_duration = db.Column(db.Integer, default=300)
    night_phase_duration = db.Column(db.Integer, default=300)

  
    def get_remaining_time(self):
        if self.discussion_start_time:
            elapsed_time = datetime.utcnow() - self.discussion_start_time
            remaining_time = max(300 - elapsed_time.total_seconds(), 0)
            return int(remaining_time)
        return 300

    def get_host(self):
        first_player = Player.query.filter_by(game_id=self.id).order_by(Player.id).first()
        print(f"First player for Game {self.id}: {first_player.user_id if first_player else 'None'}")
        return first_player

    def __repr__(self):
        return f'<Game {self.name}>'



class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(
        db.Integer,
        db.ForeignKey('game.id', use_alter=True, name="fk_player_game_id"),
        nullable=False
    )
    lover_id = db.Column(
        db.Integer,
        db.ForeignKey('player.id', use_alter=True, name="fk_player_lover_id"),
        nullable=True
    )

    # Relations
    user = db.relationship('User', backref='players', lazy=True)
    lover = db.relationship(
        'Player',
        remote_side=[id],
        backref=db.backref('lovers', lazy=True)
    )
    game = db.relationship(
        'Game',
        backref=db.backref('players', lazy=True),
        foreign_keys=[game_id]
    )

    eliminated = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(50), nullable=False)
    potion_heal_used = db.Column(db.Boolean, default=False)
    potion_poison_used = db.Column(db.Boolean, default=False)
    seer_used = db.Column(db.Boolean, default=False)
    action_used = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Player User: {self.user_id} in Game: {self.game_id}>'


import random

def assign_roles(players):

    roles = []

    # Toujours inclure un Loup-Garou et un Villageois
    roles.append('Loup-Garou')
    roles.append('Villageois')

    # Calculer le reste des rôles
    num_werewolves = max(1, (len(players) - 2) // 4)  # Exemple : 1 Loup-Garou pour 4 joueurs restants
    num_seer = min(1, len(players) - len(roles))  # 1 Voyante si possible
    num_sorceress = min(1, len(players) - len(roles))  # 1 Sorcière si possible
    num_cupid = min(1, len(players) - len(roles))  # 1 Cupidon si possible
    num_villagers = len(players) - len(roles) - num_werewolves - num_seer - num_sorceress - num_cupid
    num_fool = min(1, len(players) - len(roles))  # Inclure le Fou

    # Ajouter les rôles restants
    roles.extend(['Loup-Garou'] * num_werewolves)
    roles.extend(['Voyante'] * num_seer)
    roles.extend(['Sorcière'] * num_sorceress)
    roles.extend(['Cupidon'] * num_cupid)
    roles.extend(['Villageois'] * num_villagers)
    roles.extend(['Fou'] * num_fool)  # Ajout du rôle Fou   

    # Mélanger les rôles pour les distribuer aléatoirement
    random.shuffle(roles)

    # Assigner les rôles aux joueurs
    for player, role in zip(players, roles):
        player.role = role






class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)

    # Relations
    user = db.relationship('User', backref=db.backref('messages', lazy=True))
    game = db.relationship('Game', backref=db.backref('messages', lazy=True))
