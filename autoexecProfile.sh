#!/bin/bash

cd /opt
echo Tentando baixar ultima versao do Multiseater...
rm -r -f /tmp/MultiseaterDownloaded
git clone https://github.com/endoedgar/Multiseater.git -b stable /tmp/MultiseaterDownloaded

if [ $? -eq  0 ]
then
	rm -r -f Multiseater
	mv /tmp/MultiseaterDownloaded Multiseater
else
	echo Houve uma falha ao tentar baixar a ultima versao do Multiseater.
fi

chmod 755 Multiseater/multiseater.py
sudo ./Multiseater/multiseater.py

