const socket = io();

// Rejoindre la salle
const gameId = document.getElementById('game-id').value; // ID de la partie
const userId = document.getElementById('user-id').value; // ID de l'utilisateur

socket.emit('join_room', { game_id: gameId });

// Charger les messages existants
socket.on('load_messages', (messages) => {
    messages.forEach(msg => {
        displayMessage(msg);
    });
});

// Envoyer un message
document.getElementById('send-button').addEventListener('click', () => {
    const messageContent = document.getElementById('message-box').value;
    socket.emit('send_message', {
        game_id: gameId,
        user_id: userId,
        content: messageContent
    });
    document.getElementById('message-box').value = '';
});

// Recevoir les nouveaux messages
socket.on('receive_message', (msg) => {
    displayMessage(msg);
});

// Fonction pour afficher un message
function displayMessage(msg) {
    const messageContainer = document.getElementById('messages');
    const messageElement = document.createElement('div');
    messageElement.textContent = `[${msg.timestamp}] User ${msg.user_id}: ${msg.content}`;
    messageContainer.appendChild(messageElement);
}
