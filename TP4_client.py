"""\
GLO-2000 Travail pratique 4 - Client
Noms et numéros étudiants:
-
-
-
"""

import argparse
import getpass
import json
import socket
import sys
import os

import glosocket
import gloutils




class Client:
    """Client pour le serveur mail @glo2000.ca."""

    def __init__(self, destination: str) -> None:
        """
        Prépare et connecte le socket du client `_socket`.

        Prépare un attribut `_username` pour stocker le nom d'utilisateur
        courant. Laissé vide quand l'utilisateur n'est pas connecté.
        """

        self._username = ""
        try:
            adresse = (destination, gloutils.APP_PORT)
            self._user_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._user_socket.connect(adresse)
        except glosocket.GLOSocketError:
            sys.exit("Erreur lors de la connexion")

        print(f"Connection au port {self._user_socket.getsockname()[1]}")

    def _register(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_REGISTER`.

        Si la création du compte s'est effectuée avec succès, l'attribut
        `_username` est mis à jour, sinon l'erreur est affichée.
        """
        #creation du message d'authentication
        username = input("Entrez un nom d'utilisateur: ")

        message = gloutils.GloMessage()
        message["header"] = gloutils.Headers.AUTH_REGISTER
        payload = gloutils.AuthPayload()
        payload["username"] = username
        payload["password"] = getpass.getpass("Entrez un mot de passe: ")
        message["payload"] = payload

        #envoi du msg
        try:
            glosocket.snd_mesg(self._user_socket,json.dumps(message))
        except glosocket.GLOSocketError:
            print("Erreur lors de l'envoi de l'authentication")

        #reception de la reponse
        try:
            reply = json.loads(glosocket.recv_mesg(self._user_socket))
            if reply["header"] == gloutils.Headers.OK:
                self._username = username
            elif reply["header"] == gloutils.Headers.ERROR:
                print(reply["payload"]["error_message"])
        except glosocket.GLOSocketError:
            print("Erreur lors de la reception de l'authentication")

    def _login(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_LOGIN`.

        Si la connexion est effectuée avec succès, l'attribut `_username`
        est mis à jour, sinon l'erreur est affichée.
        """
        #creation du message d'authentication
        username = input("Entrez un nom d'utilisateur: ")

        message = gloutils.GloMessage()
        message["header"] = gloutils.Headers.AUTH_LOGIN
        payload = gloutils.AuthPayload()
        payload["username"] = username
        payload["password"] = getpass.getpass("Entrez un mot de passe: ")
        message["payload"] = payload

        #envoi du msg
        try:
            glosocket.snd_mesg(self._user_socket,json.dumps(message))
        except glosocket.GLOSocketError:
            print("Erreur lors de l'envoi de l'authentication")

        #reception de la reponse
        try:
            reply = json.loads(glosocket.recv_mesg(self._user_socket))
            if reply["header"] == gloutils.Headers.OK:
                self._username = username
            elif reply["header"] == gloutils.Headers.ERROR:
                print(reply["payload"]["error_message"])
        except glosocket.GLOSocketError:
            print("Erreur lors de la reception de l'authentication")

    def _quit(self) -> None:
        """
        Préviens le serveur de la déconnexion avec l'entête `BYE` et ferme le
        socket du client.

        """

        #creation du message de bye
        message = gloutils.GloMessage()
        message["header"] = gloutils.Headers.BYE

        #envoi du msg
        try:
            glosocket.snd_mesg(self._user_socket,json.dumps(message))
        except glosocket.GLOSocketError:
            print("Erreur lors de l'envoi de l'authentication")

    def _read_email(self) -> None:
        """
        Demande au serveur la liste de ses courriels avec l'entête
        `INBOX_READING_REQUEST`.

        Affiche la liste des courriels puis transmet le choix de l'utilisateur
        avec l'entête `INBOX_READING_CHOICE`.

        Affiche le courriel à l'aide du gabarit `EMAIL_DISPLAY`.

        S'il n'y a pas de courriel à lire, l'utilisateur est averti avant de
        retourner au menu principal.
        """
        message1 = gloutils.GloMessage()
        message1["header"] = gloutils.Headers.INBOX_READING_REQUEST
        #envoi du msg
        try:
            glosocket.snd_mesg(self._user_socket,json.dumps(message1))
        except glosocket.GLOSocketError:
            print("Erreur lors de la demande de courriels")
            return
        #reception de la reponse
        try:
            reply1 = json.loads(glosocket.recv_mesg(self._user_socket))
        except glosocket.GLOSocketError:
            print("Erreur lors de la reception de la liste de courriels")
            return

        if reply1["header"] == gloutils.Headers.OK:
            email_list_length = len(reply1["payload"]["email_list"])
            if email_list_length != 0:
                for i in range(email_list_length):
                    print(reply1["payload"]["email_list"][i])

                try:
                    choix = int(input(f"Entrez votre choix [1-{email_list_length}]: "))
                except ValueError:
                    print("erreur, veuillez entrer un nombre valide")
                    return
                if (choix <=0 or choix > email_list_length):
                    print("Choix invalide")
                    return

                message2 = gloutils.GloMessage()
                message2["header"] = gloutils.Headers.INBOX_READING_CHOICE
                payload2 = gloutils.EmailChoicePayload()
                payload2["choice"] = choix
                message2["payload"] = payload2

                try:
                    glosocket.snd_mesg(self._user_socket,json.dumps(message2))
                except glosocket.GLOSocketError:
                    print("Erreur lors de la demande du courriel")
                    return
                try:
                    reply2 = json.loads(glosocket.recv_mesg(self._user_socket))
                except glosocket.GLOSocketError:
                    print("Erreur lors de la reception du courriel")
                    return

                email = reply2["payload"]
                print(gloutils.EMAIL_DISPLAY.format(sender=email["sender"],to=email["destination"],subject=email["subject"], date=email["date"],body=email["content"]))
                return
            else:
                print("Aucun email")

            return

        elif reply["header"] == gloutils.Headers.ERROR:
            print(reply["payload"])
            return


    def _send_email(self) -> None:
        """
        Demande à l'utilisateur respectivement:
        - l'adresse email du destinataire,
        - le sujet du message,
        - le corps du message.

        La saisie du corps se termine par un point seul sur une ligne.

        Transmet ces informations avec l'entête `EMAIL_SENDING`.
        """
        try:
            dest_adr: str = input("Entrez l'adresse du destinataire :  ")
            subject: str = input("Entrez le sujet du courriel :  ")
            print("Body: (enter '.' sur une ligne simple pour finir la saisi du message)")
            body = ""
            buffer = ""
            while(buffer != ".\n"):
                body += buffer
                buffer = input() + '\n'

            date = gloutils.get_current_utc_time()
            email = gloutils.EmailContentPayload(sender = (self._username + '@' + gloutils.SERVER_DOMAIN), destination = dest_adr, subject = subject, date = date, content = body)
            message = gloutils.GloMessage()
            message["header"] = gloutils.Headers.EMAIL_SENDING
            message["payload"] = email
            data_send = json.dumps(message)
            glosocket.snd_mesg(self._user_socket, data_send)
            data_rcvd = glosocket.recv_mesg(self._user_socket)
            
            message_rcvd = json.loads(data_rcvd)
            if message_rcvd["header"] != gloutils.Headers.OK:
                print(message_rcvd["payload"]["error_message"])
            else:
                print("Email envoyé avec succès !")
        except glosocket.GLOSocketError as e:
            sys.exit(e)


    def _check_stats(self) -> None:
        """
        Demande les statistiques au serveur avec l'entête `STATS_REQUEST`.

        Affiche les statistiques à l'aide du gabarit `STATS_DISPLAY`.
        """
        try:
            message = gloutils.GloMessage()
            message["header"] = gloutils.Headers.STATS_REQUEST
            data_send = json.dumps(message)
            glosocket.snd_mesg(self._user_socket, data_send)
            reply = json.loads(glosocket.recv_mesg(self._user_socket))
            stats = gloutils.STATS_DISPLAY.format(count = reply["payload"]["count"], size =  reply["payload"]["size"])
            print(stats)
        except glosocket.GLOSocketError as e:
            sys.exit(e)

    def _logout(self) -> None:
        """
        Préviens le serveur avec l'entête `AUTH_LOGOUT`.

        Met à jour l'attribut `_username`.
        """
        message = gloutils.GloMessage()
        message["header"] = gloutils.Headers.AUTH_LOGOUT
        try:
            glosocket.snd_mesg(self._user_socket,json.dumps(message))
        except glosocket.GLOSocketError:
            print("Erreur lors de la deconnexion")
            return
        self._username = ""
        return

    def run(self) -> None:
        """Point d'entrée du client."""
        should_quit = False

        while not should_quit:
            if not self._username:
                # Authentication menu
                print(gloutils.CLIENT_AUTH_CHOICE)
                choice = input("Entrez votre choix [1-3]: ")
                match choice:
                    case '1':
                        self._register()
                    case '2':
                        self._login()
                    case '3':
                        self._quit()
                        should_quit = True
                    case _:
                        print("Choix invalide")
            else:
                # Main menu
                print(gloutils.CLIENT_USE_CHOICE)
                choice = input("Entrez votre choix [1-4]: ")
                match choice:
                    case '1':
                        self._read_email()
                    case '2':
                        self._send_email()
                    case '3':
                        self._check_stats()
                        #print("Pas encore fait ;)")
                    case '4':
                        self._logout()
                    case _:
                        print("Choix invalide")



def _main() -> int:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--destination", action="store",
                            dest="dest", required=True,
                            help="Adresse IP/URL du serveur.")
        args = parser.parse_args(sys.argv[1:])
        client = Client(args.dest)
        client.run()
    except KeyboardInterrupt:
        os.system('clear')
    return 0


if __name__ == '__main__':
    sys.exit(_main())
