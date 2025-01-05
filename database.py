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
    config_roles = db.Column(db.JSON, nullable=True)  # Configuration des rôles
    phase_duration = db.Column(db.Integer, default=60)  # Durée par défaut de chaque phase
  
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
def assign_roles(players, config_roles):
    """
    Assigner les rôles aux joueurs en respectant les conditions :
    - Au moins un Loup-Garou et un Villageois.
    - Distribution basée sur la configuration donnée.
    - Rôles spéciaux attribués correctement.
    """
    roles = []

    # Vérifier qu'il y a au moins un Loup-Garou et un Villageois
    if config_roles.get('Loup-Garou', 0) < 1 or config_roles.get('Villageois', 0) < 1:
        raise ValueError("Il doit y avoir au moins un Loup-Garou et un Villageois.")

    # Construire la liste des rôles basée sur la configuration
    for role, count in config_roles.items():
        roles.extend([role] * count)

    # Vérifiez que le nombre de rôles n'excède pas le nombre de joueurs
    if len(roles) > len(players):
        raise ValueError("Le nombre de rôles dépasse le nombre de joueurs disponibles.")

    # Vérifiez qu'il y a assez de rôles pour les joueurs
    if len(roles) < len(players):
        # Ajouter des Villageois pour combler les joueurs restants
        roles.extend(['Villageois'] * (len(players) - len(roles)))

    # Mélanger les rôles pour une distribution aléatoire
    random.shuffle(roles)

    # Assigner les rôles aux joueurs
    for player, role in zip(players, roles):
        player.role = role
        print(f"[DEBUG] {player.user.username} a reçu le rôle : {role}")

    # Vérifiez si les rôles ont été bien attribués
    assigned_roles = {role: 0 for role in config_roles.keys()}
    for player in players:
        assigned_roles[player.role] += 1

    print(f"[DEBUG] Distribution finale des rôles : {assigned_roles}")

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
