#!/usr/bin/env bash
# exec $SHELL
# source ~/.bashrc
source ~/.profile

set -e #errors will cause script to exit immediately

#change directory to location of this bash script
cd "`dirname -- "$0"`"


echo ""
echo ""

#check if the venv folder already exists
if [[ -d "../venv" ]];
then
	echo '[AXEM] Folder "venv" found, starting app...' 
	# # hack from: https://aarongorka.com/blog/portable-virtualenv/
	# sed -i '43s/.*/VIRTUAL_ENV="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}" )")" \&\& pwd)"/' venv/bin/activate
	# sed -i '1s/.*/#!\/usr\/bin\/env python/' venv/bin/pip*
	# activate & run
	pyenv shell 3.12.7
	source ../venv/bin/activate
	python main.py
	echo "[AXEM] App terminated. You may now close this window." 
	read -p "" x && exit
fi

echo '[AXEM] Folder "venv" not found, checking dependencies...' 

sudo nala update
sudo nala install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev \
libusb-dev p7zip-full


# eyelink display software
sudo apt-key adv --fetch-keys https://apt.sr-research.com/SRResearch_key
sudo add-apt-repository 'deb [arch=amd64] https://apt.sr-research.com SRResearch main'
sudo apt install eyelink-display-software


# no need to install sdl2 packages as they are provided by the pysdl2-dll python package
# sudo apt install -y libsdl2-2.0-0 libsdl2-gfx-1.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 

sudo nala install -y libportaudio2 libsndfile1

#set up high-priority group (required for pylink)
sudo groupadd --force expgrp
sudo usermod -a -G expgrp $USER
echo "@expgrp - nice -20" | sudo tee /etc/security/limits.d/99-expgrplimits.conf
echo "@expgrp - rtprio 99" | sudo tee -a /etc/security/limits.d/99-expgrplimits.conf
echo "@expgrp - memlock unlimited" | sudo tee -a /etc/security/limits.d/99-expgrplimits.conf
# id_vendor_product='057e:2009' # Gulikit KK3 Max in "Switch" mode
id_vendor_product='045e:028e' # xbox 360 controller
#split out the vendor portion
id_vendor=$(echo $id_vendor_product | cut -d':' -f1)
#split out the product portion
id_product=$(echo $id_vendor_product | cut -d':' -f2)
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="'$id_vendor'", ATTR{idProduct}=="'$id_product'", MODE="0660", GROUP="expgrp"' | sudo tee /etc/udev/rules.d/99-usb-expgrp.rules
echo 'ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="'$id_vendor'", ATTR{idProduct}=="'$id_product'", TEST=="power/control", ATTR{power/control}="off"' | sudo tee /etc/udev/rules.d/99-usb-power.rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# if [[ -d ~/.pyenv ]];
if [[ $(which pyenv) ]];
then
	echo '[AXEM] found pyenv.'
else
	# #we're on linux, so install dependencies
	# #python (from https://github.com/pyenv/pyenv/wiki#suggested-build-environment)
	# sudo nala update
	# sudo nala install -y build-essential
	echo '[AXEM] Installing pyenv...' 
	curl https://pyenv.run | bash
	echo 'export PYENV_ROOT="$HOME/.pyenv"' | tee -a ~/.profile ~/.bashrc
	echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' | tee -a ~/.profile ~/.bashrc
	echo 'eval "$(pyenv init -)"' | tee -a ~/.profile ~/.bashrc
	# source ~/.bashrc
	source ~/.profile
	echo '[AXEM] pyenv installed.' 
fi
# curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh
# sudo install.sh
# rm install.sh

# brew install pyenv 

echo '[AXEM] Installing Python 3.12 ... ' 
pyenv update
export PYVER=$(pyenv install --list | grep "^  3.12" | tail -n 1)
env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install -s --verbose $PYVER
echo '[AXEM] Python 3.12 Installed.' 
pyenv local $PYVER
pyenv shell 3.12.7

echo "[AXEM] Creating venv..." 
python -m venv --copies venv
#hack from: https://aarongorka.com/blog/portable-virtualenv/
sed -i '43s/.*/VIRTUAL_ENV="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}" )")" \&\& pwd)"/' venv/bin/activate
sed -i '1s/.*/#!\/usr\/bin\/env python/' venv/bin/pip*
# move to directory above for easier selective compression of the project
mv venv ../
source ../venv/bin/activate
echo "[AXEM] Installing python packages..." 
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install --index-url=https://pypi.sr-support.com sr-research-pylink
sed -i '1s/.*python$/#!\/usr\/bin\/env python/' ../venv/bin/*


echo "[AXEM] Starting app..." 
python main.py
echo "[AXEM] App terminated. You may now close this window." 
read -p "" x && exit
