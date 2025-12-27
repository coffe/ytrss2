#!/bin/bash
set -e  # Avsluta direkt om något steg misslyckas

# Färger för output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Bygger YT-RSS Discovery ===${NC}"

# Funktion för att visa installationshjälp
show_install_help() {
    echo -e "${YELLOW}Tips för installation:${NC}"
    echo "  Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora:        sudo dnf install python3"
    echo "  Arch Linux:    sudo pacman -S python"
}

# 1. Kontrollera att Python finns
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Fel: Python 3 krävs men hittades inte.${NC}"
    show_install_help
    exit 1
fi

# 2. Kontrollera att venv-modulen finns (vissa distros separerar den)
if ! python3 -c "import venv" &> /dev/null; then
    echo -e "${RED}Fel: Python venv-modulen saknas.${NC}"
    show_install_help
    exit 1
fi

# 3. Kontrollera att källkoden finns
if [ ! -f "ytrss.py" ]; then
    echo -e "${RED}Fel: Hittar inte ytrss.py. Kör skriptet från projektmappen.${NC}"
    exit 1
fi

# 4. Skapa tillfällig byggmiljö
echo -e "${BLUE}> Skapar tillfällig virtuell miljö (.build_venv)...${NC}"
rm -rf .build_venv
python3 -m venv .build_venv
source .build_venv/bin/activate

# 5. Installera beroenden
echo -e "${BLUE}> Installerar beroenden...${NC}"

# Säkerställ att pip finns
if ! command -v pip &> /dev/null; then
    echo -e "${RED}Fel: pip hittades inte i den virtuella miljön.${NC}"
    show_install_help
    exit 1
fi

pip install --upgrade pip > /dev/null
pip install feedparser aiohttp simple-term-menu pyinstaller

# 6. Bygg binären med PyInstaller

echo -e "${BLUE}> Bygger binärfil med PyInstaller...${NC}"

pyinstaller --clean --onefile --name ytrss --log-level ERROR ytrss.py



# 7. Städa upp

echo -e "${BLUE}> Städar upp byggfiler...${NC}"

deactivate

rm -rf .build_venv

rm -rf build

rm -f ytrss.spec



echo -e "${GREEN}=== Bygget klart! ===${NC}"

echo -e "Din körbara fil finns här: ${GREEN}./dist/ytrss${NC}"

echo ""

echo "Du kan installera den till din bin-mapp med:"

echo "  cp dist/ytrss ~/bin/"

echo "Eller systembrett:"

echo "  sudo cp dist/ytrss /usr/local/bin/"
