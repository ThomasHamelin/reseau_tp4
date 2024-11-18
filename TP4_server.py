"""\
GLO-2000 Travail pratique 4 - Serveur
Noms et numéros étudiants:
-
-
-
"""

import hashlib
import hmac
import json
import os
import select
import socket
import sys

import glosocket
import gloutils


class Server:
    """Serveur mail @glo2000.ca."""

    def __init__(self) -> None:
        """
        Prépare le socket du serveur `_server_socket`
        et le met en mode écoute.

        Prépare les attributs suivants:
        - `_client_socs` une liste des sockets clients.
        - `_logged_users` un dictionnaire associant chaque
            socket client à un nom d'utilisateur.

        S'assure que les dossiers de données du serveur existent.
        """
        # self._server_socket
        # self._client_socs
        # self._logged_users
        # ...
        self._client_socs: list[socket.socket] = []
        self._logged_users:dict = {}
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(("localhost", gloutils.APP_PORT))
            self._server_socket.listen()
        except glosocket.GLOSocketError:
            sys.exit("Erreur lors de la connexion")
        print(f"Listening on port {self._server_socket.getsockname()[1]}")

        # Assure que les donnees existent
        path_exists = os.path.exists(gloutils.SERVER_DATA_DIR)
        if not path_exists:
            os.mkdir(gloutils.SERVER_DATA_DIR)
            os.mkdir(gloutils.SERVER_LOST_DIR)
        elif not os.path.exists(gloutils.SERVER_LOST_DIR):
            os.mkdir(gloutils.SERVER_LOST_DIR)


    def _handle_client(client_socket: socket.socket) -> None:

        try:
            message = glosocket.recv_mesg(client_socket)

        # Si le client s'est déconnecté, on le retire de la liste.
        except glosocket.GLOSocketError:
            self._remove_client(client_socket)
            return

        # Sinon, on récupère l'entête et on appelle la fonction correspondante
        header, data = message.split(maxsplit=1)
        if header == AUTH_REGISTER:
            answer = self._create_account(client_socket, data)
        elif header == AUTH_LOGIN:
            answer = self._login(client_socket, data)
        elif header == INBOX_READING_REQUEST:
            #TODO
        elif header == INBOX_READING_CHOICE:
            #TODO
        elif header == EMAIL_SENDING:
            #TODO
        elif header == STATS_REQUEST:
            answer = self._get_stats(client_socket, data)
        elif header == BYE:
            self._remove_client(client_socket)
            return

        _try_send_message(client_socket, answer)

    def cleanup(self) -> None:
        """Ferme toutes les connexions résiduelles."""
        for client_soc in self._client_socs:
            client_soc.close()
        self._server_socket.close()

    def _accept_client(self) -> None:
        """Accepte un nouveau client."""
        try:
            client_socket = self._server_socket.accept()[0]
            self._client_socs.append(client_socket)
            self._handle_client(client_socket)
        except glosocket.GLOSocketError as e:
            self.cleanup()
            sys.exit(e)

    def _remove_client(self, client_soc: socket.socket) -> None:
        """Retire le client des structures de données et ferme sa connexion."""
        if client_soc in _client_socs:
            _client_socs.remove(client_soc)
        client_soc.close()

    def _create_account(self, client_soc: socket.socket,
                        payload: gloutils.AuthPayload
                        ) -> gloutils.GloMessage:
        """
        Crée un compte à partir des données du payload.

        Si les identifiants sont valides, créee le dossier de l'utilisateur,
        associe le socket au nouvel l'utilisateur et retourne un succès,
        sinon retourne un message d'erreur.
        """
        try:
            message = gloutils.GloMessage()

            username = payload["username"]
            password = payload["password"]

            path = os.path.join(gloutils.SERVER_DATA_DIR, username)

            if re.search(r"[a-zA-Z0-9_.-]+", username) is not None:
                message["header"] = gloutils.Headers.ERROR
                payload1 = gloutils.ErrorPayload()
                payload1["error_message"] = "Le nom d'utilisateur est invalide"
                message["payload"] = payload1
                return message

            if os.path.exists(path):
                message["header"] = gloutils.Headers.ERROR
                payload1 = gloutils.ErrorPayload()
                payload1["error_message"] = "Le nom d'utilisateur n'est pas disponible"
                message["payload"] = payload1
                return message


            if re.search(r"[a-z]+[A-Z]+[0-9]+.{10,}", password) is not None:
                os.mkdir(path)

                hasher = hashlib.sha3_512()
                hasher.update(password.encode('utf-8'))

                filepath = os.path.join(path, gloutils.PASSWORD_FILENAME)
                with open(filepath, ‘w’) as file:
                    file.write(hasher.hexdigest())

                self._logged_users[client_soc] = username
                message["header"] = gloutils.Headers.OK

            else:
                message["header"] = gloutils.Headers.ERROR
                payload1 = gloutils.ErrorPayload()
                payload1["error_message"] = "Le mot de passe doit contenir 10 characteres, un chiffre, une minuscule et une majuscule"
                message["payload"] = payload1


            return message
        except glosocket.GLOSocketError as e:
            self.cleanup()
            sys.exit(e)

    def _login(self, client_soc: socket.socket, payload: gloutils.AuthPayload
               ) -> gloutils.GloMessage:
        """
        Vérifie que les données fournies correspondent à un compte existant.

        Si les identifiants sont valides, associe le socket à l'utilisateur et
        retourne un succès, sinon retourne un message d'erreur.
        """
        try:
            message = gloutils.GloMessage()
            str_error_msg = "Nom d'utilisateur ou mot de passe invalide."

            username = payload["username"]
            password = payload["password"]

            path = os.path.join(gloutils.SERVER_DATA_DIR, username)

            hasher = hashlib.sha3_512()
            hasher.update(password.encode('utf-8'))

            if os.path.exists(path):
                file = open(os.path.join(path, gloutils.PASSWORD_FILENAME), "r")

                if hmac.compare_digest(hasher.hexdigest(), file.readline()):
                    self._logged_users[client_soc] = username
                    message["header"] = gloutils.Headers.OK

                else:
                    message["header"] = gloutils.Headers.ERROR
                    payload1 = gloutils.ErrorPayload()
                    payload1["error_message"] = str_error_msg
                    message["payload"] = payload1
            else:
                message["header"] = gloutils.Headers.ERROR
                payload1 = gloutils.ErrorPayload()
                payload1["error_message"] = str_error_msg
                message["payload"] = payload1
            print(message["header"])
            return message
        except glosocket.GLOSocketError as e:
            self.cleanup()
            sys.exit(e)

    def _logout(self, client_soc: socket.socket) -> None:
        """Déconnecte un utilisateur."""
        try:
            del self._logged_user[client_soc]
        except glosocket.GLOSocketError as e:
            self.cleanup()
            sys.exit(e)

    def _get_email_list(self, client_soc: socket.socket
                        ) -> gloutils.GloMessage:
        """
        Récupère la liste des courriels de l'utilisateur associé au socket.
        Les éléments de la liste sont construits à l'aide du gabarit
        SUBJECT_DISPLAY et sont ordonnés du plus récent au plus ancien.

        Une absence de courriel n'est pas une erreur, mais une liste vide.
        """
        return gloutils.GloMessage()

    def _get_email(self, client_soc: socket.socket,
                   payload: gloutils.EmailChoicePayload
                   ) -> gloutils.GloMessage:
        """
        Récupère le contenu de l'email dans le dossier de l'utilisateur associé
        au socket.
        """
        try:
            email_list = self._get_email_list(client_soc).payload
            email = email_list[(int(payload['choice'])) - 1]
            return gloutils.GloMessage(header=gloutils.Headers.OK, payload=email)
        except glosocket.GLOSocketError as e:
            self.cleanup()
            sys.exit(e)

    def _get_stats(self, client_soc: socket.socket) -> gloutils.GloMessage:
        """
        Récupère le nombre de courriels et la taille du dossier et des fichiers
        de l'utilisateur associé au socket.
        """
        try:
            path = os.path.join(gloutils.SERVER_DATA_DIR, self._logged_users[client_soc])
            folder_size = 0

            email_list_size = len(self._get_email_list(client_soc))

            for x in os.scandir(path):
                folder_size+=os.path.getsize(x)

            message = gloutils.GloMessage()
            message["header"] = gloutils.Headers.OK
            payload = gloutils.StatsPayload()
            payload["count"] = email_list_size
            payload["size"] = folder_size
            message["payload"] = payload

            return message
        except glosocket.GLOSocketError as e:
            self.cleanup()
            sys.exit(e)

    def _send_email(self, payload: gloutils.EmailContentPayload
                    ) -> gloutils.GloMessage:
        """
        Détermine si l'envoi est interne ou externe et:
        - Si l'envoi est interne, écris le message tel quel dans le dossier
        du destinataire.
        - Si le destinataire n'existe pas, place le message dans le dossier
        SERVER_LOST_DIR et considère l'envoi comme un échec.
        - Si le destinataire est externe, considère l'envoi comme un échec.

        Retourne un messange indiquant le succès ou l'échec de l'opération.
        """
        return gloutils.GloMessage()

    def run(self):
        """Point d'entrée du serveur."""
        waiters = []
        while True:
            # Select readable sockets
            self._accept_client()
            for waiter in waiters:
                # Handle sockets
                pass


def _main() -> int:
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt:
        server.cleanup()
    return 0


if __name__ == '__main__':
    sys.exit(_main())
