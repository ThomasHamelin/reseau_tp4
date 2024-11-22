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
import re
from email.message import EmailMessage
import smtplib
from datetime import datetime

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

        # Assure que les donnees existent
        path_exists = os.path.exists(gloutils.SERVER_DATA_DIR)
        if not path_exists:
            os.mkdir(gloutils.SERVER_DATA_DIR)
            os.mkdir(gloutils.SERVER_LOST_DIR)
        elif not os.path.exists(gloutils.SERVER_LOST_DIR):
            os.mkdir(gloutils.SERVER_LOST_DIR)

        print(f"Listening at {self._server_socket.getsockname()[0]}::{self._server_socket.getsockname()[1]}")


    def _handle_client(self, client_soc) -> None:

        try:
            message = json.loads(glosocket.recv_mesg(client_soc))

        # Si le client s'est déconnecté, on le retire de la liste.
        except glosocket.GLOSocketError as e:
            self._remove_client(client_soc)
            print(e)
            return

        # Sinon, on récupère l'entête et on appelle la fonction correspondante
        print("Message : ", message)

        header = message['header']
        answer = gloutils.GloMessage()

        match message:
            case {"header": gloutils.Headers.AUTH_LOGIN, "payload": payload}:
                answer = self._login(client_soc, payload)

            case {"header": gloutils.Headers.AUTH_REGISTER, "payload": payload}:
                answer = self._create_account(client_soc, payload)

            case {"header": gloutils.Headers.AUTH_LOGOUT, "payload": payload}:
                self._logout(client_soc)
                return

            case {"header": gloutils.Headers.STATS_REQUEST}:
                answer = self._get_stats(client_soc)

            case {"header": gloutils.Headers.EMAIL_SENDING, "payload": payload}:
                answer = self._send_email(payload)

            case {"header": gloutils.Headers.INBOX_READING_REQUEST}:
                print("dans inbox email reading")
                answer = self._get_email_list(client_soc)

            case {"header": gloutils.Headers.INBOX_READING_CHOICE, "payload": payload}:
                answer = self._get_email(client_soc, payload)

            case {"header": gloutils.Headers.BYE}:
                self._remove_client(client_soc)
                return

            case _: 
                print("Header invalide")
                return

        try:
            print("Answer : ",answer)
            glosocket.snd_mesg(client_soc,json.dumps(answer))
        except glosocket.GLOSocketError as e:
            print(e)

    def cleanup(self) -> None:
        """Ferme toutes les connexions résiduelles."""
        for client_soc in self._client_socs:
            client_soc.close()
        self._server_socket.close()

    def _accept_client(self) -> None:
        """Accepte un nouveau client."""
        try:
            client_soc = self._server_socket.accept()[0]
            self._client_socs.append(client_soc)
            self._handle_client(client_soc)
        except glosocket.GLOSocketError as e:
            self.cleanup()
            sys.exit(e)

    def _remove_client(self, client_soc: socket.socket) -> None:
        """Retire le client des structures de données et ferme sa connexion."""
        if client_soc in self._client_socs:
            self._client_socs.remove(client_soc)
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

            if re.search(r"[a-zA-Z0-9_.-]+", username) is None:
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


            if re.search(r"[a-z]+", password) is None or re.search(r"[A-Z]+", password) is None or re.search(r"[0-9]+", password) is None or re.search(r".{10,}", password) is None:
                message["header"] = gloutils.Headers.ERROR
                payload1 = gloutils.ErrorPayload()
                payload1["error_message"] = "Le mot de passe doit contenir 10 characteres, un chiffre, une minuscule et une majuscule"
                message["payload"] = payload1
                return message

            #si tout bon,
            os.mkdir(path)
            hasher = hashlib.sha3_512()
            hasher.update(password.encode('utf-8'))

            filepath = os.path.join(path, gloutils.PASSWORD_FILENAME)
            with open(filepath, 'w') as file:
                file.write(hasher.hexdigest())

            self._logged_users[client_soc] = username
            message["header"] = gloutils.Headers.OK

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
            del self._logged_users[client_soc]
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
        user = self._logged_users[client_soc]
        path = os.path.join(gloutils.SERVER_DATA_DIR, user)
        emails = []

        emails_file = os.listdir(path)
        #emails_file = sorted(emails_file, key=lambda x: datetime.strptime(open(x, "r").readlines[3], "%a, %d %b %Y %X %z"))

        for number_e, filename in enumerate(emails_file):
            if not filename == gloutils.PASSWORD_FILENAME:
                f = os.path.join(path, filename)
                with open(f, "r") as emailfile:
                    data = json.load(emailfile)
                    email = gloutils.SUBJECT_DISPLAY.format(number = number_e, sender = data["sender"], subject = data["subject"], date = data["date"])
                    emails.append(email)

        message = gloutils.GloMessage()
        message["header"] = gloutils.Headers.OK
        payload = gloutils.EmailListPayload()
        payload["email_list"] = emails
        message["payload"] = payload

        return message

    def _get_email(self, client_soc: socket.socket,
                   payload: gloutils.EmailChoicePayload
                   ) -> gloutils.GloMessage:
        """
        Récupère le contenu de l'email dans le dossier de l'utilisateur associé
        au socket.
        """

        choice = int(payload['choice'])

        user = self._logged_users[client_soc]
        path = os.path.join(gloutils.SERVER_DATA_DIR, user)
        emails_file = os.listdir(path)
        print(emails_file)

        for number_e, filename in enumerate(emails_file):
            print(number_e, " - ", filename, " - ", choice)
            if not filename == gloutils.PASSWORD_FILENAME:
                if number_e == choice:
                    f = os.path.join(path, filename)
                    with open(f, "r") as emailfile:
                        data = json.load(emailfile)
                        payload = gloutils.EmailContentPayload()
                        payload["sender"]=data["sender"]
                        payload["destination"]=data["destination"]
                        payload["subject"]=data["subject"]
                        payload["date"] = data["date"]
                        payload["content"]=data["content"]
                        message = gloutils.GloMessage()
                        message["header"] = gloutils.Headers.OK
                        message["payload"] = payload
                        return message

        print("Impossible de trouve l'email")


    def _get_stats(self, client_soc: socket.socket) -> gloutils.GloMessage:
        """
        Récupère le nombre de courriels et la taille du dossier et des fichiers
        de l'utilisateur associé au socket.
        """
        try:
            path = os.path.join(gloutils.SERVER_DATA_DIR, self._logged_users[client_soc])
            folder_size = 0

            email_list_size = len(self._get_email_list(client_soc)["payload"]["email_list"])

            for x in os.scandir(path):
                if x != gloutils.PASSWORD_FILENAME:
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

        destination = payload["destination"]

        if re.search(f'@{gloutils.SERVER_DOMAIN}$', destination) is None:
            resp_payload = gloutils.ErrorPayload()
            resp_payload["error_message"] = "Le destinataire est externe et ne peut pas être joint."
            message = gloutils.GloMessage()
            message["header"] = gloutils.Headers.ERROR
            message["payload"] = resp_payload
            return message

        path = os.path.join(gloutils.SERVER_DATA_DIR, destination.removesuffix('@'+gloutils.SERVER_DOMAIN))

        if not os.path.exists(path):
            filename = payload["date"] + ".json"
            filepath = os.path.join(gloutils.SERVER_LOST_DIR, filename)
            with open(filepath, 'w') as f:
                json.dump(payload, f)

            resp_payload = gloutils.ErrorPayload()
            resp_payload["error_message"] = "Le destinataire n'existe pas."
            message = gloutils.GloMessage()
            message["header"] = gloutils.Headers.ERROR
            message["payload"] = resp_payload
            return message
        else:
            filename = payload["date"] + ".json"
            filepath = os.path.join(path ,filename)
            with open(filepath, 'w') as f:
                json.dump(payload, f)

            message = gloutils.GloMessage()
            message["header"] = gloutils.Headers.OK

            return message


        """
        if "@glo2000.ca" not in payload.destination :
            try:
                message = EmailMessage()
                message["From"] = payload.sender
                message["To"] = payload.destination
                message["Subject"] = payload.subject
                message["Date"] = payload.date
                message.set_content(payload.content)
                connection = smtplib.SMTP(host="smtp.ulaval.ca", timeout=10) # À revoir ça
                connection.send_message(message)
                header = gloutils.Headers.OK
                return gloutils.GloMessage(header)
            except smtplib.SMTPException :
                reply = "Le message n'a pas pu être envoyé."
                header = gloutils.Headers.ERROR
                resp_payload = gloutils.ErrorPayload(reply)
            except socket.timeout :
                reply = "Le serveur SMTP est injoinable."
                header = gloutils.Headers.ERROR
                resp_payload = gloutils.ErrorPayload(reply)
        else :
            reply = "Le destinataire est externe et ne peut pas être joint."
            header = gloutils.Headers.ERROR
            resp_payload = gloutils.ErrorPayload(reply)
        return gloutils.GloMessage(header,resp_payload)
        """

    def run(self):
        """Point d'entrée du serveur."""
        waiters = []
        while True:
            # Select readable sockets
            result = select.select([self._server_socket] + self._client_socs, [], [])
            waiters = result[0]
            for waiter in waiters:
                # Handle sockets
                if waiter == self._server_socket:
                    self._accept_client()
                else:
                    self._handle_client(waiter)
                pass


def _main() -> int:
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt:
        server.cleanup()
        os.system('clear')
    return 0


if __name__ == '__main__':
    sys.exit(_main())
