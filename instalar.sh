#!/bin/bash
if [[ $EUID -ne 0 ]]; then
	echo "Este script precisa ser executado no como root"
	exit 1
fi

# inserirLinhaSeNaoExistirNoArquivo(linha, arquivo)
function inserirLinhaSeNaoExistirNoArquivo {
	grep -qF -- "$1" "$2" || echo "$1" >> "$2"
}

read -p "Informe o nome do usuário a ser instalado o Multiseater: " NOME_USUARIO

inserirLinhaSeNaoExistirNoArquivo "/opt/Multiseater/autoexecProfile.sh" "/home/$NOME_USUARIO/.profile"
inserirLinhaSeNaoExistirNoArquivo "$NOME_USUARIO  ALL=(ALL)  NOPASSWD:  /opt/Multiseater/multiseater.py" "/etc/sudoers"
