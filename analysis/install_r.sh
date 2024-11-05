# Update and install prerequisites
sudo apt update -qq && sudo apt install --yes --no-install-recommends wget ca-certificates gnupg

# Add the first GPG key and repository for r2u
wget -q -O- https://eddelbuettel.github.io/r2u/assets/dirk_eddelbuettel_key.asc | sudo gpg --dearmor -o /usr/share/keyrings/r2u-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/r2u-keyring.gpg] https://r2u.stat.illinois.edu/ubuntu noble main" | sudo tee /etc/apt/sources.list.d/cranapt.list

# Add the CRAN GPG key and repository
wget -q -O- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | sudo gpg --dearmor -o /usr/share/keyrings/cran-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cran-keyring.gpg] https://cloud.r-project.org/bin/linux/ubuntu noble-cran40/" | sudo tee /etc/apt/sources.list.d/cran_r.list

# Fetch additional keys with gpg (for apt-key adv keys previously)
gpg --keyserver keyserver.ubuntu.com --recv-keys 67C2D66C4B1D4339
gpg --export --armor 67C2D66C4B1D4339 | sudo tee /usr/share/keyrings/cranapt-keyring.gpg > /dev/null
gpg --keyserver keyserver.ubuntu.com --recv-keys 51716619E084DAB9
gpg --export --armor 51716619E084DAB9 | sudo tee -a /usr/share/keyrings/cranapt-keyring.gpg > /dev/null

# Update package lists and install R
sudo apt update -qq
DEBIAN_FRONTEND=noninteractive sudo apt install --yes --no-install-recommends r-base-core

# Add pinning for CRAN-Apt
echo "Package: *" | sudo tee /etc/apt/preferences.d/99cranapt
echo "Pin: release o=CRAN-Apt Project" | sudo tee -a /etc/apt/preferences.d/99cranapt
echo "Pin: release l=CRAN-Apt Packages" | sudo tee -a /etc/apt/preferences.d/99cranapt
echo "Pin-Priority: 700" | sudo tee -a /etc/apt/preferences.d/99cranapt

# Install bspm and related tools, enable it in R
sudo apt install --yes --no-install-recommends python3-dbus python3-gi python3-apt make
# sudo Rscript -e 'install.packages("bspm", repos="https://cran.r-project.org")' # original instructions, but encountered dbus issues with it
wget https://cloud.r-project.org/src/contrib/bspm_latest.tar.gz
sudo R CMD INSTALL bspm_0.5.7.tar.gz
rm bspm_0.5.7.tar.gz

RHOME=$(R RHOME)
echo "suppressMessages(bspm::enable())" | sudo tee -a ${RHOME}/etc/Rprofile.site
echo "options(bspm.version.check=FALSE)" | sudo tee -a ${RHOME}/etc/Rprofile.site
Rscript -e 'install.packages("tidyverse")'


$ echo "bspm::enable()" | sudo tee -a /etc/R/Rprofile.site


# Ensure /tmp is RAMDISK
echo "tmpfs   /tmp    tmpfs   defaults,noatime,mode=1777  0  0" | sudo tee -a /etc/fstab

wget https://s3.amazonaws.com/rstudio-ide-build/electron/jammy/amd64/rstudio-2024.09.1-394-amd64.deb
sudo nala install ./rstudio-2024.09.1-394-amd64.deb
rm rstudio-2024.09.1-394-amd64.deb