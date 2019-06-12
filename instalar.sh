#!/bin/bash
if [[ $EUID -ne 0 ]]; then
	echo "Este script precisa ser executado no como root"
	exit 1
fi

# inserirLinhaSeNaoExistirNoArquivo(linha, arquivo)
function inserirLinhaSeNaoExistirNoArquivo {
	grep -qF -- "$1" "$2" || echo "$1" >> "$2"
}

apt update
apt install python python-gtk2 python-pyudev

read -p "Informe o nome do usuário a ser instalado o Multiseater: " NOME_USUARIO

mv /opt/Multiseater/autoexecProfile.sh /opt/Multiseater_autoexecProfile.sh
chmod 755 /opt/Multiseater_autoexecProfile.sh
chown -R $NOMEUSUARIO:$NOMEUSUARIO /opt/Multiseater

inserirLinhaSeNaoExistirNoArquivo "/opt/Multiseater_autoexecProfile.sh" "/home/$NOME_USUARIO/.profile"
inserirLinhaSeNaoExistirNoArquivo "$NOME_USUARIO  ALL=(ALL)  NOPASSWD:  /opt/Multiseater/multiseater.py" "/etc/sudoers"
